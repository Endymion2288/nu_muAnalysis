#!/usr/bin/env python3
"""Quarantined truth-muon oracle; never a deployment feature configuration."""
import argparse
import csv
import json
import resource
import time
from pathlib import Path

import numpy as np
import xgboost as xgb
import yaml

from train_bdt import check_features, load, macro_score, metric_values, write_table


def inputs(repo,rows,baseline,study,partition):
    data,groups=load(rows,baseline,partition)
    # This file contains development truth only; no held-out partition is accessed.
    with np.load(repo/f'ntuples/energy_ml_stage15/{partition}_truth.npz') as d:
        if json.loads(str(d['config_json']))!=study:raise RuntimeError('Truth config mismatch')
        truth={k:d[k] for k in d.files if not k.endswith('_json')}
    for k in ['run','eventID']:np.testing.assert_array_equal(data[k],truth[k])
    oracle={k:truth[k] for k in study['oracle_features'] if k in truth}
    oracle['primary_log_p_GeV']=np.log(truth['primary_p_GeV'])
    oracle['primary_slope_x']=truth['primary_px']/truth['primary_pz']
    oracle['primary_slope_y']=truth['primary_py']/truth['primary_pz']
    # Explicit common oracle support: no filling invalid truth, no cut to deploy results.
    support=truth['primary_valid'] & np.all(np.isfinite(np.column_stack([oracle[k] for k in study['oracle_features']])),axis=1)
    return data,groups,truth,oracle,support


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--seed-index',type=int,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--smoke',action='store_true')
    args=p.parse_args(); repo=args.repo; out=args.output_dir; out.mkdir(parents=True,exist_ok=True)
    tick=time.perf_counter(); cpu=time.process_time()
    study=yaml.safe_load((repo/'ml/configs/physics_decomposition.yaml').read_text())
    base=yaml.safe_load((repo/'ml/configs/baseline.yaml').read_text())
    rows=list(csv.DictReader((repo/'ml/configs/files.tsv').open(),delimiter='\t'))
    sets=[inputs(repo,rows,base,study,part) for part in study['partitions']]
    train,tgroups,ttruth,toracle,tsupport=sets[0]; val,groups,truth,oracle,support=sets[1]
    if set(tgroups)&set(groups):raise RuntimeError('Source leakage')
    if args.smoke:
        tsupport=tsupport & (np.arange(len(tsupport))<1200)
        support=support & (np.arange(len(support))<400)
    ytrain=train[base['target']][tsupport]; y=val[base['target']][support]
    seed=study['seeds'][args.seed_index]; predictions={}; costs=[]; traces={}; metrics=[]
    edges=np.array(study['energy_edges_GeV']); bins=[(y>=a)&(y<b) for a,b in zip(edges[:-1],edges[1:])]
    for version,added in study['oracle_groups'].items():
        names=sum([base['feature_groups'][g] for g in added],[])
        check_features(names,sum(base['feature_groups'].values(),[]))
        # Only the declared oracle whitelist may supply truth. Target/y/transfer excluded.
        declared=study['oracle_features']
        if declared!=['primary_log_p_GeV','primary_slope_x','primary_slope_y','primary_pdg','vertex_x_mm','vertex_y_mm','vertex_z_mm']:
            raise RuntimeError('Oracle whitelist changed: review target leakage')
        names=declared+names
        xt=np.column_stack([(toracle[k] if k in declared else train[k])[tsupport] for k in names])
        xv=np.column_stack([(oracle[k] if k in declared else val[k])[support] for k in names])
        training=xgb.DMatrix(xt,label=np.log(ytrain),feature_names=names,nthread=1)
        validation=xgb.DMatrix(xv,label=np.log(y),feature_names=names,nthread=1)
        params=dict(base['xgboost'])
        for k in ['n_estimators','early_stopping_rounds','n_jobs']:params.pop(k)
        params.update(max_depth=study['xgboost']['max_depth'],seed=seed,nthread=1,objective='reg:squarederror')
        history={}; start=time.perf_counter(); startcpu=time.process_time()
        model=xgb.train(params,training,num_boost_round=20 if args.smoke else study['xgboost']['rounds'],
                        evals=[(training,'train'),(validation,'validation')],early_stopping_rounds=study['xgboost']['patience'],
                        evals_result=history,verbose_eval=False)
        wall=time.perf_counter()-start; used=time.process_time()-startcpu
        times=[]
        for repeat in range(6):
            start=time.perf_counter(); raw=model.inplace_predict(xv,iteration_range=(0,model.best_iteration+1))
            if repeat:times.append(time.perf_counter()-start)
        predictions[version]=np.exp(raw); traces[version]=history
        modelpath=out/f'{version}.ubj';model.save_model(modelpath)
        (out/f'{version}.features.json').write_text(json.dumps(names,indent=2)+'\n')
        costs.append(dict(model=version,seed=seed,features=len(names),train_events=len(ytrain),validation_events=len(y),
                          best_iteration=model.best_iteration,iterations=len(history['train']['rmse']),
                          train_wall_s=wall,train_cpu_s=used,inference_wall_s=float(np.median(times)),
                          inference_events_per_s=len(y)/float(np.median(times)),model_bytes=modelpath.stat().st_size))
        metrics.append(dict(model=version,seed=seed,macro_log_RMSE=macro_score(y,predictions[version],bins),
                            **metric_values(y,predictions[version],np.ones(len(y),dtype=bool))))
        print(json.dumps(costs[-1]),flush=True)
    np.savez_compressed(out/'predictions.npz',run=val['run'][support],eventID=val['eventID'][support],
                        truth_E_GeV=y,group=groups[support],**predictions)
    write_table(out/'costs.tsv',costs);write_table(out/'metrics.tsv',metrics)
    (out/'learning_traces.json').write_text(json.dumps(traces)+'\n')
    summary=dict(seed=seed,study=study,baseline=base,smoke=args.smoke,
                 train_oracle_support=int(tsupport.sum()),validation_oracle_support=int(support.sum()),
                 train_oracle_excluded=int((~tsupport).sum()),validation_oracle_excluded=int((~support).sum()),
                 calibration_test_challenge_evaluated=False,wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,
                 peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
