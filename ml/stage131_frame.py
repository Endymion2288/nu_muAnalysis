"""Freeze a finite selected-parent frame before new G4 response or energy risks."""
import gzip
import hashlib
import json
import resource
import time
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage131_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage131'

def main():
    tick=time.perf_counter();sources=json.loads((ROOT/'workbook/stage130_energy_ml/source_protocol.json').read_text())['sources']
    with np.load(ROOT/'ntuples/energy_ml_stage130/new_input.npz') as z:d={k:z[k] for k in ['role','source','eventID','incoming','truth_E_GeV','y_lepton','pz','vertex_z_mm']}
    active=np.flatnonzero(np.isin(d['role'],[1,2,3]));seen=set();records=[]
    for row in active:
        key=d['incoming'][row].astype('<f4').tobytes()
        if key in seen:continue
        seen.add(key);i=int(d['source'][row]);s=sources[i];E=float(d['truth_E_GeV'][row]);pz=float(d['pz'][row]);y=float(d['y_lepton'][row])
        layer='E50_100' if E<100 else 'E100_200' if E<200 else 'lowpz_highE' if pz<100 else 'high_y' if np.isfinite(y) and y>.75 else 'transition' if E<1000 else 'highE'
        records.append(dict(row=int(row),source=i,run=s['run'],component=s['component'],role=int(d['role'][row]),EVNT=s['EVNT'],entry=int(d['eventID'][row]),incoming=d['incoming'][row].tolist(),truth_E_GeV=E,old_reco_pz_GeV=pz,y=y if np.isfinite(y) else None,vertex_z_mm=float(d['vertex_z_mm'][row]),stratum=layer,rank=hashlib.blake2b(key,digest_size=8,person=b'nuMu131').hexdigest()))
    records.sort(key=lambda r:r['rank'])
    for i,r in enumerate(records):r['frame_index']=i;r['seed']=2026110700+131000+i
    with gzip.open(CACHE/'frame.json.gz','wt') as f:json.dump(records,f,separators=(',',':'))
    counts={f'{role}:{layer}':sum(r['role']==role and r['stratum']==layer for r in records) for role in [1,2,3] for layer in sorted({r['stratum'] for r in records})}
    pilot=[]
    for layer in ['E50_100','E100_200','lowpz_highE','high_y','transition','highE']:
        pool=[r for r in records if r['role']==1 and r['stratum']==layer]
        pilot.extend(r['frame_index'] for r in pool[:2])
    contract=dict(stage=131,frame_N=len(records),counts=counts,pilot_indices=pilot,
        sampling='unique incoming float32 proxy; canonical first active source/row; hash order nuMu131; fixed2 train parents per6 disjoint strata',
        inclusion_probability={layer:min(2/counts[f'1:{layer}'],1) for layer in sorted({r['stratum'] for r in records})},
        pilot_only='cost/label completeness/migration; no model forward or fit; conditional on historical selected frame, not unbiased neutrino efficiency',
        roles='inherited Stage130 roles;0/4 and all old reserved excluded; no historical locked-test',
        boundary='actual EmulsionStationA logical envelope, first outward traversal per branch; suppress returns and daughters born after counted exit; transport KE separately from total energy; killed neutrino flow unmeasured',
        labels='root-primary-muon descendants vs other roots vs unknown; sensitive SD depositedMeV, prompt[0,1000)ns and all-time; no ADC additive claim, no H/E_nu identity',
        pilot_resources=dict(cpus=4,memory_MB=12000,parents=len(pilot),scheduler_wall_s=86400,application_timeout=None,aggregate_CPU_budget_s=30000),
        later='after cost/labels freeze matched same-support X/X+lineage-oracle/X+nonmu-boundary-oracle/proxy models; no new response risks before freeze',
        wall_s=time.perf_counter()-tick,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    (OUT/'pilot_contract.json').write_text(json.dumps(contract,indent=2)+'\n');print(json.dumps(contract,indent=2))

if __name__=='__main__':main()
