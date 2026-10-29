#!/usr/bin/env python3
"""Development-only physics baselines and grouped BDT ablations.

Opens train/validation caches only. Test, calibration and SIBYLL challenge labels
remain unused. This unit-weight diagnostic is not a physical flux prediction.
"""
import argparse
import csv
import json
import resource
import time
from pathlib import Path

import numpy as np
import xgboost as xgb
import yaml


def write_table(path, rows):
    with path.open('w') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)


def check_features(names, allowed):
    forbidden=('truth','ML_truth','t_','GenWeight','CrossSection','run','eventID','isFiducial')
    if len(set(names))!=len(names) or any(n not in allowed or n.startswith(forbidden) or 'fudged' in n for n in names):
        raise ValueError('Feature whitelist violation')


def load(rows, cfg, partition):
    columns=sum(cfg['feature_groups'].values(),[])+[cfg['target'],'LeadTrack_pz0','run','eventID',
              'ML_truth_px_MeV','ML_truth_py_MeV','ML_truth_pz_MeV','truth_dec_x_nu','truth_dec_y_nu','truth_dec_z_nu']
    consolidated=Path(rows[0]['cache']).parents[1]/'dataset'/f'{partition}.npz'
    if consolidated.exists():
        with np.load(consolidated) as data:
            if json.loads(str(data['config_json']))!=cfg:
                raise RuntimeError('Consolidated cache/config mismatch')
            values={c:data[c] for c in columns}
            groups=data['group']
        expected=sum(int(r['expected_selected']) for r in rows if r['partition']==partition)
        if len(groups)!=expected: raise RuntimeError('Consolidated partition count mismatch')
        return values,groups
    values={c:[] for c in columns}; groups=[]
    for row in rows:
        if row['partition']!=partition: continue
        with np.load(row['cache']) as data:
            metadata=json.loads(str(data['metadata_json']))
            if metadata['config']!=cfg:
                raise RuntimeError('Cache and training configuration differ; regenerate or use matching frozen config')
            if len(data[cfg['target']])!=int(row['expected_selected']):
                raise RuntimeError('Cache/manifest count mismatch')
            for c in columns: values[c].append(data[c])
            groups.extend([row['group']]*len(data[cfg['target']]))
    return {k:np.concatenate(v) for k,v in values.items()},np.array(groups)


def metric_values(y,pred,mask):
    y=y[mask]; pred=pred[mask]
    if len(y)==0: return None
    r=pred/y-1
    q=np.quantile(r,[.025,.16,.5,.84,.975])
    return dict(N=len(y),Neff=float(len(y)),median_bias=float(q[2]),mean_bias=float(r.mean()),
                R68=float((q[3]-q[1])/2),log_RMSE=float(np.sqrt(np.mean(np.log(pred/y)**2))),
                relative_RMS=float(np.sqrt(np.mean(r*r))),tail_0p5=float(np.mean(np.abs(r)>.5)),
                tail_1=float(np.mean(np.abs(r)>1)),r_q025=float(q[0]),r_q975=float(q[4]))


def macro_score(y,pred,bins):
    pieces=[np.mean(np.log(pred[m]/y[m])**2) for m in bins if m.sum()>=100]
    return float(np.sqrt(np.mean(pieces))) if pieces else float('nan')


def bootstrap_scores(y,predictions,groups,bins,repeats,seed):
    """Same source groups and resamples for all models; group/bin sufficient sums."""
    group_names,group_id=np.unique(groups,return_inverse=True)
    counts=np.stack([np.bincount(group_id[m],minlength=len(group_names)) for m in bins],axis=1)
    active=counts.sum(axis=0)>=100
    rng=np.random.default_rng(seed)
    multiplicities=rng.multinomial(len(group_names),np.full(len(group_names),1/len(group_names)),size=repeats)
    denominator=multiplicities@counts[:,active]
    scores={}
    for name,pred in predictions.items():
        errors=np.log(pred/y)**2
        sums=np.stack([np.bincount(group_id[m],weights=errors[m],minlength=len(group_names)) for m in bins],axis=1)
        # Sparse resamples with no events in a registered bin are excluded jointly.
        valid=np.all(denominator>0,axis=1)
        scores[name]=np.sqrt(np.mean((multiplicities@sums[:,active])[valid]/denominator[valid],axis=1))
    return scores


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--model-dir',type=Path,required=True)
    args=parser.parse_args()
    begin=time.perf_counter(); cpu_start=time.process_time()
    repo=args.repo.resolve(); output=args.output_dir; output.mkdir(parents=True,exist_ok=True)
    args.model_dir.mkdir(parents=True,exist_ok=True)
    cfg=yaml.safe_load((repo/'ml/configs/baseline.yaml').read_text())
    rows=list(csv.DictReader((repo/'ml/configs/files.tsv').open(),delimiter='\t'))
    train,train_groups=load(rows,cfg,'train'); val,val_groups=load(rows,cfg,'validation')
    assert not set(train_groups)&set(val_groups)
    for data in [train,val]:
        if len(np.unique(np.column_stack([data['run'],data['eventID']]),axis=0))!=len(data['run']):
            raise RuntimeError('Duplicate run/eventID')
    # Detect exact repeated incoming kinematics + vertex across train/validation.
    # Campaign lineage beyond exact equality is conservatively grouped in files.tsv.
    truth_columns=['ML_truth_px_MeV','ML_truth_py_MeV','ML_truth_pz_MeV','truth_dec_x_nu','truth_dec_y_nu','truth_dec_z_nu']
    fingerprints=lambda d:set(map(tuple,np.column_stack([d[c] for c in truth_columns])))
    if fingerprints(train)&fingerprints(val):
        raise RuntimeError('Repeated truth kinematics/vertex crosses development partitions')
    ytrain=train[cfg['target']]; y=val[cfg['target']]
    ptrain=train['ML_mu_p_GeV']; p=val['ML_mu_p_GeV']
    edges=np.array(cfg['energy_edges_GeV'])
    bins=[(y>=lo)&(y<hi) for lo,hi in zip(edges[:-1],edges[1:])]
    scale=float(np.exp(np.mean(np.log(ytrain/ptrain))))
    predictions={'mu_p':p,'mu_p_over_0p8':p/.8,'existing_pz_over_0p8':val['LeadTrack_pz0']/.8,'train_scaled_p':scale*p}
    costs=[]; models=[]
    allowed=sum(cfg['feature_groups'].values(),[])
    for version,group_names in cfg['feature_versions'].items():
        models.append((version,group_names,'direct'))
        models.append((version,group_names,'residual'))
    full=cfg['feature_versions']['F5']
    for group in full:
        if group!='mu': models.append((f'F5_without_{group}',[g for g in full if g!=group],'direct'))
    for version,group_names,target in models:
        names=sum([cfg['feature_groups'][g] for g in group_names],[])
        check_features(names,allowed)
        preprocessing_start=time.perf_counter()
        xtrain=np.column_stack([train[c] for c in names]); xval=np.column_stack([val[c] for c in names])
        label=np.log(ytrain) if target=='direct' else np.log(ytrain/ptrain)
        eval_label=np.log(y) if target=='direct' else np.log(y/p)
        params=dict(cfg['xgboost'])
        rounds=params.pop('n_estimators')
        patience=params.pop('early_stopping_rounds')
        params['nthread']=params.pop('n_jobs')
        params.update(objective='reg:squarederror',seed=cfg['seed'])
        training=xgb.DMatrix(xtrain,label=label,feature_names=names,nthread=1)
        validation=xgb.DMatrix(xval,label=eval_label,feature_names=names,nthread=1)
        preprocessing_wall=time.perf_counter()-preprocessing_start
        model_name=f'{version}_{target}'
        started=time.perf_counter(); cpu=time.process_time()
        model=xgb.train(params,training,num_boost_round=rounds,evals=[(validation,'validation')],early_stopping_rounds=patience,verbose_eval=False)
        wall=time.perf_counter()-started; train_cpu=time.process_time()-cpu
        # inplace_predict avoids the DMatrix prediction cache in repeated timing.
        costs_for_inference=[]
        for repeat in range(6):
            tick=time.perf_counter()
            raw=model.inplace_predict(xval,iteration_range=(0,model.best_iteration+1))
            if repeat>0: costs_for_inference.append(time.perf_counter()-tick)
        inference=float(np.median(costs_for_inference))
        prediction=np.exp(raw)*(1 if target=='direct' else p)
        predictions[model_name]=prediction
        model_path=args.model_dir/f'{model_name}.ubj'; model.save_model(model_path)
        (args.model_dir/f'{model_name}.features.json').write_text(json.dumps(names,indent=2)+'\n')
        costs.append(dict(model=model_name,features=len(names),best_iteration=model.best_iteration,
                          preprocessing_wall_s=preprocessing_wall,train_wall_s=wall,train_cpu_s=train_cpu,inference_wall_s=inference,
                          inference_events_per_s=len(y)/inference,model_bytes=model_path.stat().st_size))
        print(json.dumps(costs[-1]),flush=True)
    summaries=[]; per_bin=[];strata=[]
    for name,pred in predictions.items():
        for run in np.unique(val['run']):
            mask=val['run']==run
            strata.append(dict(model=name,stratum='run',value=int(run),**metric_values(y,pred,mask)))
        for charge in [-1,1]:
            mask=val['LeadTrack_charge']==charge
            if mask.any():strata.append(dict(model=name,stratum='mu_charge',value=charge,**metric_values(y,pred,mask)))
    bootstrap=bootstrap_scores(y,predictions,val_groups,bins,cfg['bootstrap_replicates'],cfg['seed'])
    for name,pred in predictions.items():
        m=metric_values(y,pred,np.ones(len(y),dtype=bool))
        ci=np.quantile(bootstrap[name],[.025,.975])
        summaries.append(dict(model=name,partition='validation',weight_mode='unit_diagnostic',**m,
                              macro_log_RMSE=macro_score(y,pred,bins),macro_CI025=ci[0],macro_CI975=ci[1]))
        for lo,hi,mask in zip(edges[:-1],edges[1:],bins):
            m=metric_values(y,pred,mask)
            if m: per_bin.append(dict(model=name,energy_low_GeV=lo,energy_high_GeV=hi,primary_bin=int(mask.sum()>=100),**m))
        overflow=(y<edges[0])|(y>=edges[-1])
        if overflow.any():
            per_bin.append(dict(model=name,energy_low_GeV=edges[-1],energy_high_GeV='inf',primary_bin=0,**metric_values(y,pred,overflow)))
    differences=[]
    comparisons=[('F0_direct',f'F{i}_direct') for i in range(1,6)]
    comparisons += [(f'F{i-1}_direct',f'F{i}_direct') for i in range(1,6)]
    comparisons += [(f'F5_without_{g}_direct','F5_direct') for g in full if g!='mu']
    for left,right in comparisons:
        delta=bootstrap[right]-bootstrap[left]; ci=np.quantile(delta,[.025,.975])
        differences.append(dict(reference=left,model=right,delta_macro_log_RMSE=macro_score(y,predictions[right],bins)-macro_score(y,predictions[left],bins),CI025=ci[0],CI975=ci[1],bootstrap_replicates=len(delta)))
    write_table(output/'validation_metrics.tsv',summaries)
    write_table(output/'validation_energy_bins.tsv',per_bin)
    write_table(output/'paired_ablation.tsv',differences)
    write_table(output/'costs.tsv',costs)
    write_table(output/'validation_strata.tsv',strata)
    report=dict(xgboost_version=xgb.__version__,train_events=len(ytrain),validation_events=len(y),
                train_groups=len(np.unique(train_groups)),validation_groups=len(np.unique(val_groups)),
                fitted_scale=scale,physical_weighting='not measured; all rows have unit weight',
                calibration_and_test_used=False,features=cfg['feature_groups'],energy_edges_GeV=edges.tolist(),
                validation_counts_per_energy_bin=[int(m.sum()) for m in bins],
                train_energy_range_GeV=[float(ytrain.min()),float(ytrain.max())],
                validation_energy_range_GeV=[float(y.min()),float(y.max())],
                validation_outside_primary_energy_range=int(((y<edges[0])|(y>=edges[-1])).sum()),
                bootstrap_replicates=cfg['bootstrap_replicates'],
                total_wall_s=time.perf_counter()-begin,total_cpu_s=time.process_time()-cpu_start,
                peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                caveat='Validation is used for early stopping and ablation development; bootstrap intervals are conditional on fitted models, not unbiased final test intervals.')
    (output/'training_summary.json').write_text(json.dumps(report,indent=2)+'\n')
    np.savez_compressed(args.model_dir/'validation_predictions.npz',truth_E_GeV=y,run=val['run'],eventID=val['eventID'],group=val_groups,**predictions)
    (args.model_dir/'config.yaml').write_text(yaml.safe_dump(cfg,sort_keys=False))
    print(json.dumps(report),flush=True)


if __name__=='__main__':
    main()
