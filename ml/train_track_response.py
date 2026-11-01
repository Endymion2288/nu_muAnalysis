#!/usr/bin/env python3
"""Fixed-budget F5/F6 response recovery. Truth is a label only."""
import argparse,json,time,resource
from pathlib import Path
import numpy as np
import xgboost as xgb
from information_gap import inputs,split_groups,configuration as reference_config
from track_response import configuration
from train_information_gap import Limit
from train_bdt import write_table


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--seed-index',type=int,required=True);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--smoke',action='store_true');a=p.parse_args()
    cfg=configuration(a.repo);ref=reference_config(a.repo);tick=time.perf_counter();cpu=time.process_time()
    base,names,(train,val)=inputs(a.repo);extra=cfg['features'];aug=[]
    for part,d in zip(cfg['partitions'],[train,val]):
        with np.load(a.repo/f'ntuples/energy_ml_stage31/{part}_tracks.npz') as z:
            assert json.loads(str(z['config_json']))==cfg
            for k in ['run','eventID']:np.testing.assert_array_equal(d['truth'][k],z[k])
            aug.append(np.column_stack([d['x']]+[z[k] for k in extra]).astype('float32'))
    role,assignment=split_groups(train['groups'],ref);fit=role=='fit';stop=role=='stop'
    if a.smoke:
        rng=np.random.default_rng(42)
        for mask in [fit,stop]:
            idx=rng.choice(np.flatnonzero(mask),min(900,mask.sum()),replace=False);mask[:]=False;mask[idx]=True
    seed=cfg['seeds'][a.seed_index];out=a.output_dir;out.mkdir(parents=True,exist_ok=True);costs=[];traces={};pred={};importance=[]
    for model_name,features,target in [('nu_F6',names+extra,'nu'),('mu_F5',names,'mu'),('mu_F6',names+extra,'mu')]:
        xt=aug[0] if model_name.endswith('F6') else train['x'];xv=aug[1] if model_name.endswith('F6') else val['x']
        labels=np.log(train['y']) if target=='nu' else np.log(train['truth']['primary_p_GeV']/train['p'])
        dfit=xgb.DMatrix(xt[fit],label=labels[fit],feature_names=features,nthread=4)
        dstop=xgb.DMatrix(xt[stop],label=labels[stop],feature_names=features,nthread=4)
        params={k:v for k,v in base['xgboost'].items() if k not in ['n_estimators','early_stopping_rounds','n_jobs']}
        params.update(max_depth=ref['xgboost']['max_depth'],seed=seed,nthread=4,objective='reg:squarederror')
        limit=Limit(cfg['max_fit_wall_s']);history={};start=time.perf_counter();cstart=time.process_time()
        rounds=20 if a.smoke else ref['xgboost']['rounds']
        model=xgb.train(params,dfit,num_boost_round=rounds,evals=[(dfit,'fit'),(dstop,'stop')],
                        early_stopping_rounds=ref['xgboost']['patience'],callbacks=[limit],evals_result=history,verbose_eval=False)
        wall=time.perf_counter()-start;used=time.process_time()-cstart;ir=(0,model.best_iteration+1)
        times=[]
        for repeat in range(4):
            start=time.perf_counter();raw=model.inplace_predict(xv,iteration_range=ir)
            if repeat:times.append(time.perf_counter()-start)
        pred[model_name]=np.exp(raw)*(val['p'] if target=='mu' else 1)
        path=out/f'{model_name}.ubj';model.save_model(path);traces[model_name]=history
        costs.append(dict(model=model_name,seed=seed,features=len(features),best_iteration=model.best_iteration,
                          iterations=len(history['fit']['rmse']),stop_reason='time' if limit.hit else 'rounds' if model.num_boosted_rounds()==rounds else 'patience',
                          train_wall_s=wall,train_cpu_s=used,inference_wall_s=float(np.median(times)),
                          inference_events_per_s=len(val['y'])/float(np.median(times)),model_bytes=path.stat().st_size))
        importance += [dict(model=model_name,feature=f,gain=g) for f,g in model.get_score(importance_type='gain').items()]
        print(json.dumps(costs[-1]),flush=True)
    pred.update(run=val['truth']['run'],eventID=val['truth']['eventID'],group=val['groups'])
    np.savez_compressed(out/'predictions.npz',**pred);write_table(out/'costs.tsv',costs)
    write_table(out/'feature_gain.tsv',importance)
    (out/'learning_traces.json').write_text(json.dumps(traces)+'\n')
    summary=dict(cfg=cfg,reference_cfg=ref,features=names+extra,source_assignment=assignment,seed_index=a.seed_index,seed=seed,smoke=a.smoke,
                 split_counts={k:int((role==k).sum()) for k in ['fit','stop','map']},wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,
                 peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,calibration_test_challenge_evaluated=False)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))

if __name__=='__main__':main()
