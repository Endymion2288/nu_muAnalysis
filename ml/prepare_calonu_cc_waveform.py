#!/usr/bin/env python3
"""Freeze bounded CC waveform controls before native waveforms/HITS are inspected."""
import csv
import json
import resource
import time
from datetime import datetime,timezone
from pathlib import Path

import numpy as np

from calonu_inputs import manifest
from report_calonu_native import table


def main():
    tick,cpu=time.perf_counter(),time.process_time()
    repo=Path(__file__).resolve().parents[1]
    out=repo/'workbook/stage39_energy_ml';out.mkdir(exist_ok=True)
    cfgpath=repo/'ml/configs/calonu_cc_waveform.json'
    assert not cfgpath.exists(),'Already frozen'
    rows=manifest(repo)
    extracted={int(r['index']):r for r in csv.DictReader((repo/'workbook/stage35_energy_ml/extraction_files.tsv').open(),delimiter='\t')}
    inventory=[]
    for r in rows:
        phys=Path(r['input']);base=phys.parents[2];first,last=map(int,r['group'].split(':')[1].split('-'))
        stem=phys.name.split(f'-{r["run"]}-')[0]+f'-{r["run"]}-'
        rdo=base/'rdo/s0015'/phys.name.replace('-PHYS.root','-RDO.root')
        rec=base/'rec/s0015'/phys.name.replace('-PHYS.root','-xAOD.root')
        hits=[base/'sim/s0015'/f'{stem}{i:05}-s0015-HITS.root' for i in range(first,last+1)]
        inventory.append(dict(index=int(r['index']),group=r['group'],partition=r['partition'],
                              phys_entries=int(extracted[int(r['index'])]['input_events']),
                              PHYS_exists=phys.exists(),RDO_exists=rdo.exists(),rec_exists=rec.exists(),
                              nominal_HITS_files=len(hits),existing_HITS_files=sum(p.exists() for p in hits)))
    table(out/'lineage_inventory.tsv',inventory)
    indices=[]
    for component in ['pi','k','charm']:
        eligible=[int(r['index']) for r in rows if r['component']==component and r['partition']=='fit'
                  and extracted[int(r['index'])]['input_events']=='10000']
        indices.extend([eligible[1],eligible[-1]])
    cfg=dict(stage=39,starting_commit='d25c353',frozen_utc=datetime.now(timezone.utc).isoformat(),
             indices=indices,max_events=192,regular_per_group_per_p_bin=12,diagnostic_per_group=8,
             source_commit='1ec47efe',max_condor_jobs=8,new_ML_fits=0,new_G4_events=0,
             bootstrap_replicates=1000,bootstrap_seed=20261106,
             primary_readout='template_plus_constant',reference_readout='signed_saved',
             timing_controls_ns=[-2,2],baseline_controls_sigma=[-1,1],offpulse_samples=[100,176],
             high_signal_threshold_pC=1.,timing_fraction_tolerance=.05,
             gate='Native lineage and waveform checks; regular primary paired RMSE gain lower95>0 and lower offpulse RMS; no unsupported channel imputation; high-signal nominal-model timing loss >5% is a limitation requiring resolution before CC energy-model training',
             partition='Only existing stage35 fit groups; waveform confirmation with stage38 algorithm fixed, not a new independent neutrino-energy test',
             template_parameters=json.loads((repo/'ml/configs/calonu_repair_control.json').read_text())['template_parameters'])
    with np.load(repo/'ntuples/energy_ml_stage35/fit.npz') as z:
        d={k:z[k] for k in z.files if k!='metadata_json'}
    total_events,total_regular=0,0
    for index in cfg['indices']:
        r=rows[index];assert int(r['index'])==index and r['partition']=='fit'
        assert inventory[index]['phys_entries']==10000
        pool=np.flatnonzero(d['manifest_index']==index);p=d['reco_p_GeV']
        chosen=[]
        for lo,hi in [(100,250),(250,1000)]:
            ids=pool[(p[pool]>=lo)&(p[pool]<hi)]
            assert len(ids)>0,(index,lo,len(ids))
            ids=ids[np.argsort(d['eventID'][ids],kind='stable')]
            chosen += [(int(i),'regular') for i in ids[np.linspace(0,len(ids)-1,min(12,len(ids))).astype(int)]]
        status=np.column_stack([d[f'CaloNu{i}_status'] for i in range(4)]).astype(np.uint32)
        charge=np.column_stack([d[f'CaloNu{i}_charge'] for i in range(4)])
        raw=np.column_stack([d[f'CaloNu{i}_raw_charge'] for i in range(4)])
        diagnostics=[]
        conditions=[('nonfinite',(~np.isfinite(charge)).any(axis=1)),('saturated',(status&4!=0).any(axis=1)),
                    ('high_raw',raw.max(axis=1)>10),('negative',(charge<0).any(axis=1)),
                    ('fit_failed',(status&48!=0).any(axis=1)),('zero_readout',d['CaloNu_total_E_EM']==0),
                    ('high_y',d['y_lepton']>=.8)]
        for label,mask in conditions:
            ids=[int(i) for i in pool[mask[pool]] if i not in {q[0] for q in chosen+diagnostics}]
            diagnostics += [(i,label) for i in ids[:min(2,8-len(diagnostics))]]
        for i in pool:
            if len(diagnostics)==8:break
            if int(i) not in {q[0] for q in chosen+diagnostics}:diagnostics.append((int(i),'diagnostic_fill'))
        cases=[]
        for i,role in chosen+diagnostics:
            fp=dict(eventID=int(d['eventID'][i]),Track_p0=float(np.float32(d['reco_p_GeV'][i]*1000)),
                    Track_X_atVetoNu=float(d['ML_mu_X_atVetoNu_mm'][i]),Track_Y_atVetoNu=float(d['ML_mu_Y_atVetoNu_mm'][i]),
                    CaloNu0_raw_charge=float(d['CaloNu0_raw_charge'][i]))
            cases.append(dict(role=role,cache_row=i,fingerprint=fp,reco_p_GeV=float(p[i]),
                              truth_E_GeV=float(d['truth_E_GeV'][i]),y_lepton=float(d['y_lepton'][i]),
                              vertex_z_mm=float(d['vertex_z_mm'][i]),primary_kinematic_parent_proxy=bool(d['primary_kinematic_parent_proxy'][i])))
        phys=Path(r['input']);base=phys.parents[2];first=int(r['group'].split(':')[1].split('-')[0])
        stem=phys.name.split(f'-{r["run"]}-')[0]+f'-{r["run"]}-'
        request=dict(index=index,run=int(r['run']),group=r['group'].replace(':','_'),component=r['component'],
                     expected_phys_entries=10000,hits_events_per_file=1000,first_subfile=first,
                     hits_name_template=stem+'{subfile:05}-s0015-HITS.root',allow_missing_channels=True,verify_phys_truth=True,
                     input_phys=str(phys),input_rdo=str(base/'rdo/s0015'/phys.name.replace('-PHYS.root','-RDO.root')),
                     input_rec=str(base/'rec/s0015'/phys.name.replace('-PHYS.root','-xAOD.root')),
                     sim_directory=str(base/'sim/s0015'),cases=cases)
        (out/f'request_{index}.json').write_text(json.dumps(request,indent=2)+'\n')
        total_events+=len(cases);total_regular+=len(chosen)
    cfgpath.write_text(json.dumps(cfg,indent=2)+'\n')
    prep=dict(events=total_events,regular=total_regular,diagnostic=total_events-total_regular,indices=cfg['indices'],
              wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,
              peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    (out/'preparation.json').write_text(json.dumps(prep,indent=2)+'\n')
    print(json.dumps(cfg));print(json.dumps(prep))


if __name__=='__main__':main()
