#!/usr/bin/env python3
"""Descriptive readback of the frozen features; never chooses radii or candidates."""
import json
from pathlib import Path
import numpy as np
from report_calonu_information import strata
from train_bdt import write_table

r=Path(__file__).resolve().parents[1];out=r/'workbook/stage44_energy_ml';cfg=json.loads((r/'ml/configs/local_activity.json').read_text())
with np.load(r/'ntuples/energy_ml_stage42/development.npz') as z:
    chosen=np.flatnonzero(z['selected']);d={k:z[k][chosen] for k in z.files}
with np.load(r/'ntuples/energy_ml_stage44/features.npz') as z:feat={k:z[k] for k in z.files}
rows=[];axis=[]
for label,mask in strata(d).items():
    if not mask.any():continue
    axis.append(dict(stratum=label,N=int(mask.sum()),donor_self_N=int((feat['donor_row'][mask]==np.flatnonzero(mask)).sum()),
                     **{f's{s}_valid_N':int(np.isfinite(feat['axes'][mask,j]).all(axis=1).sum()) for j,s in enumerate(cfg['local_stations'])}))
    if label not in ['all','focus','p100_250','p250_1000','focus_y0.8_1.01','focus_z-2300_-1950']:continue
    for candidate in ['local','null']:
        for j,name in enumerate(cfg['feature_names']):
            v=feat[candidate][mask,j];finite=np.isfinite(v);q=np.quantile(v[finite],[0,.5,.9,.99,1]) if finite.any() else [None]*5
            rows.append(dict(stratum=label,candidate=candidate,feature=name,N=int(mask.sum()),finite_N=int(finite.sum()),zero_N=int((v==0).sum()),
                             min=q[0],median=q[1],p90=q[2],p99=q[3],max=q[4]))
write_table(out/'feature_summary.tsv',rows);write_table(out/'axis_support.tsv',axis)
with np.load(r/'ntuples/energy_ml_stage44/features.npz') as z:
    m=json.loads(str(z['metadata_json']));(out/'extraction.json').write_text(json.dumps(m,indent=2)+'\n')
print(json.dumps(dict(events=len(chosen),feature_summary_rows=len(rows),axis_strata=len(axis))))

focus=(d['reco_p_GeV']>=100)&(d['reco_p_GeV']<1000)
c=feat['counts'][focus];total=c.sum(axis=1)
diag=dict(focus_events=int(focus.sum()),station_median_counts=np.median(c,axis=0).tolist(),station_zero_N=(c==0).sum(axis=0).tolist(),
          pooled_station_point_fraction=(c.sum(axis=0)/c.sum()).tolist(),
          log1p_IFT_vs_total_count_Pearson=float(np.corrcoef(np.log1p(c[:,0]),np.log1p(total))[0,1]),
          local_zero_nout10_N={str(st):int((feat['local'][focus,4+j*6]==0).sum()) for j,st in enumerate(cfg['local_stations'])})
(out/'activity_support.json').write_text(json.dumps(diag,indent=2)+'\n');print(json.dumps(diag))
