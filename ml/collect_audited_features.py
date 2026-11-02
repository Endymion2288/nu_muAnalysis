#!/usr/bin/env python3
"""Join the full nominal cohort and count actual invalid/readout cases."""
import json
import resource
import time

import numpy as np

from audited_features import REPO, SCINTILLATORS, WAVE_INVALID, FIT_INVALID, build, configuration
from train_bdt import write_table

tick, cpu = time.perf_counter(), time.process_time()
cache=REPO/'ntuples/energy_ml_stage56';out=REPO/'workbook/stage56_energy_ml';cfg=configuration()
with np.load(REPO/'ntuples/energy_ml_stage55/dataset.npz') as z:d={k:z[k] for k in z.files}
parts=[];metadata=[]
for i in range(6):
    with np.load(cache/f'shards/{i}.npz') as z:
        md=json.loads(str(z['metadata_json']));assert md['batch']==i and not md['smoke']
        parts.append({k:z[k] for k in z.files if k!='metadata_json'});metadata.append(md)
s={k:np.concatenate([p[k] for p in parts]) for k in parts[0]}
order=np.argsort(s['row']);s={k:v[order] for k,v in s.items()}
np.testing.assert_array_equal(s['row'],np.flatnonzero(d['nominal']))
assert sum(len(m['files']) for m in metadata)==254
np.savez_compressed(cache/'readout.npz',**s,metadata_json=np.array(json.dumps(metadata)))
x=build(d,s);names=json.loads(str(d['metadata_json']))['features'];rows=s['row'];records=[]
for j,n in enumerate(SCINTILLATORS):
    q=s['raw_charge'][:,j];status=s['status'][:,j].astype(np.int64);fit=d['x'][rows,names.index(n+'_charge')]
    valid=np.isfinite(q)&((status&WAVE_INVALID)==0);usable=valid&(q>1)
    ratio=fit[usable]/q[usable]
    records.append(dict(channel=n,N=len(q),negative_raw_N=int((q<0).sum()),negative_fit_N=int((fit<0).sum()),
                        raw_min=float(np.nanmin(q)),raw_max=float(np.nanmax(q)),fit_max=float(np.nanmax(fit)),
                        baseline_missing_invalid_N=int(((status&WAVE_INVALID)!=0).sum()),
                        baseline_rms_minus1_N=int((s['baseline_rms'][:,j]==-1).sum()),
                        fit_failed_N=int(((status&48)!=0).sum()),fit_failed_raw_usable_N=int((((status&48)!=0)&valid).sum()),
                        overflow_N=int(((status&4)!=0).sum()),threshold_failed_N=int(((status&1)!=0).sum()),
                        raw_minus999_N=int((q==-999).sum()),raw_minus1_N=int((q==-1).sum()),
                        raw_gt1_N=int(usable.sum()),fit_over_raw_median=float(np.median(ratio)),fit_over_raw_max=float(np.max(ratio)),
                        fit_raw_diff_gt50pct_raw_gt1_N=int((abs(ratio-1)>.5).sum())))
write_table(out/'scintillator_readout.tsv',records)
calo=[]
for j in range(4):
    st=s['calo_status'][:,j].astype(np.int64)
    calo.append(dict(channel=f'Calo{j}',N=len(st),invalid_fitted_energy_N=int(((st&FIT_INVALID)!=0).sum()),
                     fit_failed_N=int(((st&48)!=0).sum()),overflow_N=int(((st&4)!=0).sum()),baseline_missing_invalid_N=int(((st&WAVE_INVALID)!=0).sum())))
write_table(out/'calorimeter_status.tsv',calo)
profile=[]
for j,name in enumerate(cfg['features']):
    v=x[:,j];finite=np.isfinite(v);q=np.quantile(v[finite],[0,.5,1]) if finite.any() else [np.nan]*3
    profile.append(dict(feature=name,domain=cfg['rules'][name]['domain'],N=len(v),missing_N=int((~finite).sum()),negative_N=int((v<0).sum()),min=q[0],median=q[1],max=q[2]))
write_table(out/'corrected_feature_profile.tsv',profile)
write_table(out/'extraction_files.tsv',[r for m in metadata for r in m['files']])
result=dict(files=254,N=len(rows),raw_N=sum(m['raw_N'] for m in metadata),features=x.shape[1],
            train_N=int(d['train_eligible'][rows].sum()),cal_N=int(d['cal_eligible'][rows].sum()),eval_N=int((d['partition'][rows]=='validation').sum()),
            missing_cells=int(np.isnan(x).sum()),events_with_missing=int(np.isnan(x).any(axis=1).sum()),
            extraction_wall_sum_s=sum(m['wall_s'] for m in metadata),extraction_cpu_sum_s=sum(m['cpu_s'] for m in metadata),
            extraction_requested_bytes=sum(m['requested_bytes'] for m in metadata),extraction_max_rss_MiB=max(m['peak_rss_MiB'] for m in metadata),
            wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
(out/'dataset_summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
