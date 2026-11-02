#!/usr/bin/env python3
"""Audit the actual persisted F6 matrix, without retraining or ROOT re-reading."""
import json
import resource
import time

import numpy as np

from audited_features import REPO, configuration
from train_bdt import write_table

tick, cpu = time.perf_counter(), time.process_time()
out = REPO/'workbook/stage56_energy_ml'
with np.load(REPO/'ntuples/energy_ml_stage55/dataset.npz') as z:
    names = json.loads(str(z['metadata_json']))['features']
    x = z['x']; p0 = z['reco_p_GeV']; pz0 = z['reco_pz_GeV']
cfg = configuration()
mapped = {r['old_feature']:r['new_feature'] for r in cfg['mapping']}
rows = []
for j, name in enumerate(names):
    v = x[:,j]; finite = np.isfinite(v)
    q = np.quantile(v[finite], [0,.16,.5,.84,1]) if finite.any() else np.full(5,np.nan)
    new = mapped.get(name, '')
    rule = cfg['rules'].get(new, {})
    rows.append(dict(feature=name,action='remove' if not new else 'replace' if new!=name else 'retain',
                     new_feature=new,domain=rule.get('domain','removed'),N=len(v),nonfinite=int((~finite).sum()),negative=int((v<0).sum()),
                     minus1=int((v==-1).sum()),minus999=int((v==-999).sum()),minus9999=int((v==-9999).sum()),
                     scaled_minus999_MeV=int((v==np.float32(-.999)).sum()),scaled_minus1_MeV=int((v==np.float32(-.001)).sum()),
                     plus999999=int((v==999999).sum()),wrapped_uint32=int((v>=4294967295).sum()),
                     min=q[0],q16=q[1],median=q[2],q84=q[3],max=q[4]))
write_table(out/'feature_inventory.tsv',rows)
comparisons=[]
for name,v in [('p0_over_pz0_minus1',p0/pz0-1),('p1_over_p0_minus1',x[:,names.index('ML_track_p1_GeV')]/p0-1),
               ('pz1_over_pz0_minus1',x[:,names.index('ML_track_pz1_GeV')]/pz0-1),
               ('log_p1_over_p0',x[:,names.index('ML_track_log_p1_over_p0')])]:
    q=np.nanquantile(v,[0,.16,.5,.84,1])
    comparisons.append(dict(quantity=name,N=len(v),min=q[0],q16=q[1],median=q[2],q84=q[3],max=q[4],abs_gt1pct_N=int((abs(v)>.01).sum())))
write_table(out/'momentum_redundancy.tsv',comparisons)
result=dict(N=len(x),old_features=len(names),new_features=len(cfg['features']),
            scalar_momentum='pz0 only; permitted transverse/inverse momentum and bend parameterizations retained',
            old_preprocessing='nonfinite -> NaN; track_response.derive only recognizes 999999, no typed negative/count handling',
            signed_markers='-1 is valid charge sign/module_eta; negative coordinates, transverse/inverse momentum and baseline-subtracted readouts are not missing by sign',
            wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
(out/'audit_resources.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
