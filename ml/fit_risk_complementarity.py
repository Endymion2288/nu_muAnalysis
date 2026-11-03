#!/usr/bin/env python3
"""One complete outer nested pipeline or one final frozen head."""
import argparse,time
import scipy,sklearn,xgboost as xgb
from risk_complementarity import *


class Budget(xgb.callback.TrainingCallback):
    def __init__(self,start,p):self.start=start;self.p=p
    def after_iteration(self,model,epoch,evals_log):
        budget(self.start,self.p)
        return False


def budget(start,p):
    r=resources(start)
    if r['CPU_s']>p['callback_CPU_per_job_s'] or r['wall_s']>p['callback_wall_per_job_s']:
        raise RuntimeError('stage78 frozen hard budget; no retry or reduced candidate')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--job',choices=JOBS,required=True);ap.add_argument('--check-only',action='store_true')
    args=ap.parse_args();job=args.job;start=begin();p=json.loads((OUT/'protocol.json').read_text())
    assert xgb.__version__==p['xgboost_version'] and scipy.__version__==p['scipy_version'] and sklearn.__version__==p['sklearn_version']
    d=arrays(CACHE/'input.npz');outer,held,purge=training_split(d,p,job)
    dest=ART/job;assert not dest.exists();report=OUT/job;report.mkdir(parents=True,exist_ok=True)
    if args.check_only:
        splits=list(inner_splits(d,p,job)) if held is not None else []
        print(json.dumps(dict(job=job,outer_train_N=int(outer.sum()),inner_train_N=[int(it.sum()) for _,it,_,_ in splits],
            formal_base_fits=0,formal_partition_fits=0,solver_calls=0,**resources(start))))
        return
    dest.mkdir(parents=True);(dest/'started.txt').write_text('one attempt; no restart\n')
    records=[];trainrow=d['row'][outer];h=np.full((len(trainrow),3),np.nan)
    h[:,2]=np.log(d['pz'][outer]/.8)
    if held is None:h=d['old_oof_h'][outer].copy()
    else:
        seen=np.zeros(len(trainrow),int)
        for k,it,ih,ip in inner_splits(d,p,job):
            dmheld=xgb.DMatrix(d['x'][ih],feature_names=p['features'],nthread=1)
            idx=np.searchsorted(trainrow,d['row'][ih]);np.testing.assert_array_equal(trainrow[idx],d['row'][ih]);seen[idx]+=1
            y=np.log(d['truth_E_GeV'][it]);base=float(y.mean());params=dict(p['xgboost'],seed=p['seed'],base_score=base,boost_from_average=0)
            for j,arm in enumerate(['U','F']):
                budget(start,p);w,bins,count=weights(d['truth_E_GeV'][it],float(j));fitstart=begin()
                dm=xgb.DMatrix(d['x'][it],label=y,weight=w,feature_names=p['features'],nthread=1)
                booster=xgb.train(params,dm,num_boost_round=400,callbacks=[Budget(start,p)])
                booster.set_attr(stage78_outer=job,stage78_inner=str(k),stage78_arm=arm,deployment_inputs=json.dumps(p['features']))
                modelpath=dest/f'inner{k}_{arm}.ubj';booster.save_model(modelpath)
                restored=xgb.Booster(params={'nthread':1});restored.load_model(modelpath)
                pred=booster.predict(dmheld).astype(float);np.testing.assert_array_equal(pred,restored.predict(dmheld).astype(float))
                assert booster.num_boosted_rounds()==400;h[idx,j]=pred
                rec=dict(inner=k,arm=arm,train_N=int(it.sum()),held_N=int(ih.sum()),purged_N=int(ip.sum()),
                    groups=len(np.unique(d['group'][it])),unique_incoming=len(np.unique(d['incoming'][it],axis=0)),
                    params=params,base_score=base,bin_counts=count.tolist(),weight_mean=float(w.mean()),weight_max=float(w.max()),Kish_ESS=float(w.sum()**2/(w@w)),
                    source_overlap=0,known_incoming_overlap=0,outer_held_source_and_incoming_absent=True,model_reload_exact=True,**resources(fitstart))
                records.append(rec);print(json.dumps(rec),flush=True)
        assert np.all(seen==1)
    assert np.isfinite(h).all()
    dd=subset(d,outer);y=np.log(dd['truth_E_GeV'])
    np.savez_compressed(dest/'head_training.npz',row=trainrow,h=h)
    partstart=begin();part=fit_partition(dd['x'],h,y,p);partition_resources=resources(partstart)
    leaf=route(dd['x'],part);solutions={}
    for arm,loc in [('Q0',np.zeros(len(h),int)),('Q_local',leaf)]:
        budget(start,p);solutions[arm]=solve_combination(h,y,loc,dd,p)
        save(report/(arm+'_solver.json'),solutions[arm])
        if not solutions[arm]['solved']:raise RuntimeError('stage78 numerical solution unresolved; no solver retry or science conclusion')
    head=dict(partition=part,solutions=solutions,expert_order=['U_raw','F_raw','log(pz/.8)'],outer_job=job,features=p['features'])
    save(dest/'head.json',head)
    output={};roles={'held':held} if held is not None else {r:d['role']==r for r in ['train','cal','eval']}
    for role,m in roles.items():
        output[role+'_row']=d['row'][m]
        experts=d['old_oof_h'][m] if role=='held' else d['old_final_h'][m]
        for arm in ARMS:output[role+'_'+arm+'_raw_log']=predict_head(d['x'][m],experts,head,arm)
    # Separate head-training risk uses actual inner OOF (or final full OOF), not train-in predictions.
    for arm in ARMS:output['head_train_'+arm+'_raw_log']=predict_head(dd['x'],h,head,arm)
    output['head_train_row']=trainrow
    np.savez_compressed(dest/'predictions.npz',**output);budget(start,p);(dest/'started.txt').unlink()
    save(report/'fit.json',dict(job=job,formal_base_fits=len(records),formal_partition_fits=1,convex_problems=2,
        solver_calls=sum(v['solver_calls'] for v in solutions.values()),base_records=records,
        outer_train_N=int(outer.sum()),outer_held_N=int(held.sum()) if held is not None else 0,outer_purged_N=int(purge.sum()),
        partition_resources=partition_resources,leaf_counts=np.bincount(leaf).tolist(),**resources(start)))
    print((report/'fit.json').read_text())


if __name__=='__main__':main()
