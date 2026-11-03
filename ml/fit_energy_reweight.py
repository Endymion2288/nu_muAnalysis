#!/usr/bin/env python3
"""Three fixed, DMatrix-weighted squared-log-error fits per frozen split."""
import argparse
import json
import time
import numpy as np
import xgboost as xgb
from group_risk import training_split
from energy_reweight import *


class Budget(xgb.callback.TrainingCallback):
    def __init__(self,start):self.start=start
    def after_iteration(self,model,epoch,evals_log):
        if time.process_time()-self.start[1]>850 or time.perf_counter()-self.start[0]>1700:
            raise RuntimeError('stage73 hard budget; no retry/shortened candidate')
        return False


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--job',choices=['fold0','fold1','fold2','final'],required=True)
    parser.add_argument('--check-only',action='store_true')
    args=parser.parse_args();job=args.job;start=begin();p=json.loads((OUT/'protocol.json').read_text())
    assert xgb.__version__==p['xgboost_version']
    dest=ART/job;assert not dest.exists();dest.mkdir(parents=True);(OUT/job).mkdir(parents=True,exist_ok=True)
    (dest/'started.txt').write_text('no automatic restart\n')
    d=arrays(CACHE/'input.npz');use,held,purge=training_split(d,p,job)
    y=np.log(d['truth_E_GeV'][use]);base=float(y.mean());params=dict(p['xgboost'],seed=p['seed'],base_score=base,boost_from_average=0)
    roles={'held':held} if held is not None else {r:d['role']==r for r in ['train','cal','eval']}
    matrices={r:xgb.DMatrix(d['x'][m],feature_names=p['features'],nthread=1) for r,m in roles.items()}
    output={r+'_row':d['row'][m] for r,m in roles.items()};records=[];weight_rows=[]
    if args.check_only:
        print(json.dumps(dict(job=job,train_N=int(use.sum()),formal_fits=0,worker_directory_exists=True,**resources(start))))
        return
    for name,alpha in ARMS.items():
        w,bins,count=weights(d['truth_E_GeV'][use],alpha)
        assert abs(w.mean()-1)<1e-12
        dm=xgb.DMatrix(d['x'][use],label=y,weight=w,feature_names=p['features'],nthread=1)
        fit_start=begin();model=xgb.train(params,dm,num_boost_round=400,callbacks=[Budget(start)])
        assert model.num_boosted_rounds()==400
        model.set_attr(deployment_inputs=json.dumps(p['features']),stage73_arm=name,stage73_protocol=json.dumps(p))
        model.save_model(dest/(name+'.ubj'));restored=xgb.Booster(params={'nthread':1});restored.load_model(dest/(name+'.ubj'))
        for r,matrix in matrices.items():
            pred=model.predict(matrix);np.testing.assert_array_equal(pred,restored.predict(matrix))
            output[r+'_'+name+'_raw_log']=pred.astype(float)
        train_pred=model.predict(dm).astype(float);dd={k:v[use] for k,v in d.items()}
        risks={k:metrics(y[m],train_pred[m])['log_RMSE'] for k,m in masks(dd).items()}
        for b,n in enumerate(count):
            mb=bins==b;weight_rows.append(dict(job=job,arm=name,bin=b,raw_N=int(n),
                groups=len(np.unique(dd['group'][mb])),unique_incoming=len(np.unique(dd['incoming'][mb],axis=0)),
                weight_sum=float(w[mb].sum()),weight_per_event=float(w[mb][0]) if n else '未测量'))
        rec=dict(arm=name,alpha=alpha,base_score=base,params=params,train_N=int(use.sum()),
            purged_N=int(purge.sum()),held_N=int(held.sum()) if held is not None else 0,
            groups=len(np.unique(d['group'][use])),unique_incoming=len(np.unique(d['incoming'][use],axis=0)),
            weight_min=float(w.min()),weight_max=float(w.max()),weight_mean=float(w.mean()),
            Kish_ESS=float(w.sum()**2/(w@w)),train_log_RMSE=risks,model_reload_exact=True,**resources(fit_start))
        records.append(rec);print(json.dumps(rec),flush=True)
    np.savez_compressed(dest/'predictions.npz',**output);(dest/'started.txt').unlink()
    table(OUT/job/'weights.tsv',weight_rows)
    save(OUT/job/'fit.json',dict(job=job,formal_fits=3,records=records,**resources(start)))


if __name__=='__main__':main()
