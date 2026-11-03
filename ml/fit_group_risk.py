#!/usr/bin/env python3
"""One matched C/R pair for a source fold or full training, exactly400 trees each."""
import argparse
import json
import traceback
import numpy as np
from group_risk import OUT,ART,inputs,masks,fit_pair,training_split,begin,resources,save


def main(job):
    start=begin();p=json.loads((OUT/'protocol.json').read_text());dest=ART/job;record=OUT/job
    assert not dest.exists() and not record.exists(),'No repeat successful pair'
    record.mkdir();d=inputs();use,held,purged=training_split(d,p,job)
    small={k:v[use] for k,v in d.items()};y=np.log(small['truth_E_GeV'])
    C,R,diag=fit_pair(small['x'],y,small['pz'],masks(small),p,dest)
    import xgboost as xgb
    arrays={}
    for role,take in ([('held',held)] if job!='final' else [(r,d['role']==r) for r in ['train','cal','eval']]):
        arrays[role+'_row']=d['row'][take]
        dm=xgb.DMatrix(d['x'][take],feature_names=p['features'],nthread=p['request_cpus'])
        for name,model in [('C',C),('R',R)]:arrays[role+'_'+name+'_raw_log']=model.predict(dm).astype(float)
    np.savez_compressed(dest/'predictions.npz',**arrays)
    diag.update(job=job,train_N=int(use.sum()),purged_train_N=int(purged.sum()),train_groups=sorted(set(d['group'][use])),
        held_N=int(held.sum()) if held is not None else 0,held_groups=sorted(set(d['group'][held])) if held is not None else [],
        energy_fits=2,truth_free_deployment=True,whole_job_resources=resources(start))
    save(record/'fit.json',diag);print(job,'C/R final risks',diag['C_low_MSE_ratios'],diag['final'],flush=True)


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--job',choices=['fold0','fold1','fold2','final'],required=True);args=a.parse_args()
    try:main(args.job)
    except Exception:
        (OUT/('failure_'+args.job+'.txt')).write_text(traceback.format_exc());raise
