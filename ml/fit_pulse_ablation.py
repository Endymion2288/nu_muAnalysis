"""Stage80: exactly two matched unit-risk regressors per frozen source split."""
import argparse
import json
import resource
import time
import numpy as np
import xgboost as xgb
from pulse_ablation import *


class Budget(xgb.callback.TrainingCallback):
    def __init__(self,start):self.start=start
    def after_iteration(self,model,epoch,evals_log):
        if time.process_time()-self.start[1]>790 or time.perf_counter()-self.start[0]>1700:
            raise RuntimeError('fixed stage80 budget, no retry or shortened candidate')
        return False


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--job',choices=JOBS,required=True);parser.add_argument('--check-only',action='store_true');a=parser.parse_args()
    start=begin();p=json.loads((OUT/'protocol.json').read_text());d=arrays(CACHE/'input.npz');assert xgb.__version__==p['xgboost_version']
    use,held,purge=training_split(d,p,a.job);y=np.log(d['truth_E_GeV'][use]);base=float(y.mean())
    params=dict(p['xgboost'],seed=p['seed'],base_score=base,boost_from_average=0)
    roles={'held':held} if held is not None else {r:d['role']==r for r in ['train','cal','eval']}
    dest=ART/a.job;dest.mkdir(parents=True);(OUT/a.job).mkdir(parents=True,exist_ok=True)
    if a.check_only:
        for arm in ARMS:
            dm=xgb.DMatrix(matrix(d,arm)[use][:40],label=y[:40],feature_names=p['features_by_arm'][arm],nthread=1)
            assert dm.num_col()==len(p['features_by_arm'][arm])
            booster=xgb.Booster(params=params,cache=[dm]);assert booster.num_boosted_rounds()==0
        print(json.dumps(dict(job=a.job,train_N=int(use.sum()),held_N=int(held.sum()) if held is not None else 0,
            energy_fits=0,features=[62,84],**resources(start))));return
    resource.setrlimit(resource.RLIMIT_CPU,(850,875));(dest/'started.txt').write_text('no automatic restart\n')
    output={r+'_row':d['row'][m] for r,m in roles.items()};records=[]
    for arm in ARMS:
        tick=begin();xx=matrix(d,arm);features=p['features_by_arm'][arm]
        dm=xgb.DMatrix(xx[use],label=y,feature_names=features,nthread=1)
        model=xgb.train(params,dm,num_boost_round=400,callbacks=[Budget(start)])
        model.set_attr(deployment_inputs=json.dumps(features),stage80_arm=arm,feature_policy='F7_pz0_raw_v1+shape22' if arm=='P' else 'F7_pz0_raw_v1')
        model.save_model(dest/(arm+'.ubj'));restored=xgb.Booster(params={'nthread':1});restored.load_model(dest/(arm+'.ubj'))
        for role,m in roles.items():
            matrix_role=xgb.DMatrix(xx[m],feature_names=features,nthread=1);pred=model.predict(matrix_role)
            np.testing.assert_array_equal(pred,restored.predict(matrix_role));output[role+'_'+arm+'_raw_log']=pred.astype(float)
        pred=model.predict(dm).astype(float);dd={k:v[use] for k,v in d.items()}
        risk={k:metrics(y[m],pred[m])['log_RMSE'] for k,m in diagnostic_masks(dd).items()}
        records.append(dict(arm=arm,train_N=int(use.sum()),held_N=int(held.sum()) if held is not None else 0,purged_N=int(purge.sum()),
            train_groups=len(np.unique(d['group'][use])),base_score=base,params=params,features=len(features),rounds=400,
            train_log_RMSE=risk,model_reload_exact=True,**resources(tick)))
    np.savez_compressed(dest/'predictions.npz',**output);(dest/'started.txt').unlink()
    save(OUT/a.job/'fit.json',dict(job=a.job,formal_fits=2,records=records,**resources(start)))
    print(json.dumps(dict(job=a.job,formal_fits=2,records=records,**resources(start))),flush=True)


if __name__=='__main__':main()
