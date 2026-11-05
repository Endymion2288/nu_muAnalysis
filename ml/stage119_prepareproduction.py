"""Batch-only pre-response truth superset and source-wide role freeze."""
import json
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage119_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage119'


def main():
    p=json.loads((OUT/'protocol.json').read_text());requests=[]
    for s in p['sources']:
        with np.load(CACHE/f'pilot_{s["index"]}.npz') as z:
            r=z['vertex_r'];v=z['vertex_z'].astype('float32');incoming=z['incoming']
            keep=(r<100)&(((v>-3000)&(v<-1950))|((v>np.float32(-1769.65))&(v<np.float32(-1619.65))))
            keep &= (abs(incoming[:,0])==14)&(incoming[:,3]>50000)
            assert not np.any(z['S50']&~keep)
            path=Path(s['input']);rdo=path.parents[2]/'rdo'/path.parent.name/path.name.replace('PHYS.root','RDO.root')
            assert rdo.is_file()
            req=dict(source=s,parent_N=len(keep),entries=np.flatnonzero(keep).tolist(),rdo=str(rdo),
                eventID=z['eventID'][keep].tolist(),incoming=z['incoming'][keep].tolist(),
                criterion='conservative original truth nu_mu/pz>50/r<100/fiducial z superset; no reco/effect/model selection')
            requests.append(req)
    # Freeze source blocks before compatible selected yields or any inference.
    # Hashing exact incoming across all response views is an additional purge.
    contract=dict(stage=119,requests=requests,scope='63 already uniformly frozen full parent files, no source replacement',
        policies='official d32 reco then merge noIFT; original fitted-charge cuts, audited62 raw/status; original calibration representation only after payload validation',
        roles='new-only highest available incoming proxy: fixed 70/15/15 train/development/reserved; all known old exposure excluded from new pool. Original roles unchanged. GENIE-parent and new blind certification pending.',
        role_seed=2026110519,confirmation='reserve only, no prediction/risk until final design and power; cannot claim independent blind with incomplete lineage',
        resources=dict(jobs=63,cpus_each=1,memory_MB_each=3000,disk_MB_each=8000,wall_s_each=28800,
            aggregate_CPU_s=252000,retained_selected_bytes=60000000),
        scale='freeze N/2N/4N after compatible producer yield, before model outcomes; one original strong policy, fixed composition/common support',
        exclusions='No low energy model-directed source additions; truth-rejected parents retained in denominator; sparse equivalence QA required before submit')
    (OUT/'production_contract.json').write_text(json.dumps(contract,indent=2)+'\n')
    print('Parents',sum(r['parent_N'] for r in requests),'truth superset',sum(len(r['entries']) for r in requests),flush=True)


if __name__=='__main__':main()
