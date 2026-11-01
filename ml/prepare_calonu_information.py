#!/usr/bin/env python3
"""Freeze source folds and bounded HITS requests, using stage35 fit only."""
import json
import resource
import time
from pathlib import Path
import numpy as np
from calonu_inputs import feature_names, manifest
from train_bdt import write_table


def main():
    tick, cpu = time.perf_counter(), time.process_time()
    repo = Path(__file__).resolve().parents[1]
    cfg = json.loads((repo/'ml/configs/calonu_information.json').read_text())
    out = repo/'workbook/stage42_energy_ml'; cache = repo/'ntuples/energy_ml_stage42'
    with np.load(repo/cfg['development_input']) as z:
        d = {k:z[k] for k in z.files if k != 'metadata_json'}
    names, extra = feature_names(repo); names += extra
    assert len(names)==65
    rows = manifest(repo); assignment = {}; records = []
    for comp in ['pi','k','charm']:
        selected = [i for i in cfg['indices'] if rows[i]['component']==comp]
        remaining = [int(r['index']) for r in rows if r['partition']=='fit' and r['component']==comp and int(r['index']) not in selected]
        counts = np.zeros(3,int)
        for i in selected + remaining:
            f = int(np.argmin(counts)); counts[f] += 1; assignment[i] = f
    fold = np.array([assignment[int(i)] for i in d['manifest_index']],np.int8)
    selected = np.isin(d['manifest_index'],cfg['indices'])
    calo = np.column_stack([d['ML_calonu'+i+'_E_EM_GeV'] for i in ['0','1','2','3','_total']])
    zero = (np.isfinite(calo)&(calo==0)).all(1)
    x = np.column_stack([d[k] for k in names]).astype('float32'); x[~np.isfinite(x)] = np.nan
    meta = ['run','eventID','group','component','manifest_index','truth_E_GeV','reco_p_GeV','y_lepton',
            'vertex_z_mm','primary_kinematic_parent_proxy','primary_valid']
    np.savez_compressed(cache/'development.npz',**{k:d[k] for k in meta},x=x,calo=calo.astype('float32'),zero=zero,fold=fold,selected=selected)
    for i in sorted(assignment):
        pool = np.flatnonzero(d['manifest_index']==i)
        records.append(dict(index=i,group=rows[i]['group'],component=rows[i]['component'],fold=assignment[i],N=len(pool),selected_B=i in cfg['indices']))
        if i not in cfg['indices']: continue
        r = rows[i]; phys = Path(r['input']); base=phys.parents[2]; first=int(r['group'].split(':')[1].split('-')[0])
        stem=phys.name.split(f'-{r["run"]}-')[0]+f'-{r["run"]}-'
        cases=[]
        for j in pool:
            fp=dict(eventID=int(d['eventID'][j]),Track_p0=float(np.float32(d['reco_p_GeV'][j]*1000)),
                    Track_X_atVetoNu=float(d['ML_mu_X_atVetoNu_mm'][j]),Track_Y_atVetoNu=float(d['ML_mu_Y_atVetoNu_mm'][j]),
                    CaloNu0_raw_charge=float(d['CaloNu0_raw_charge'][j]))
            cases.append(dict(cache_row=int(j),role='representative_development',fingerprint=fp))
        request=dict(index=i,run=int(r['run']),group=r['group'],component=r['component'],expected_phys_entries=10000,
                     hits_events_per_file=1000,first_subfile=first,hits_name_template=stem+'{subfile:05}-s0015-HITS.root',
                     verify_phys_truth=True,input_phys=str(phys),sim_directory=str(base/'sim/s0015'),cases=cases)
        (cache/f'requests/request_{i}.json').write_text(json.dumps(request)+'\n')
    write_table(out/'source_folds.tsv',records)
    summary=dict(events=len(x),sources=len(assignment),B_events=int(selected.sum()),B_sources=len(cfg['indices']),
                 zero_events=int(zero.sum()),zero_total_disagreement=int((zero!=(calo[:,-1]==0)).sum()),
                 feature_names=names,wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,
                 peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    assert selected.sum()<=cfg['max_HITS_events']
    (out/'preparation.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary))

if __name__=='__main__': main()
