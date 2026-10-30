#!/usr/bin/env python3
"""Separate training weights from early-stopping weights at fixed F5 capacity."""
import argparse
import csv
import json
import resource
import time
from pathlib import Path

import numpy as np
import torch
import xgboost as xgb
import yaml

from robustness import bin_weights
from train_bdt import check_features, load, write_table
from train_tabular import TimeLimit, fit_bdt, fit_nn, make_model, preprocess


def weighted_nn(trial, study, seed, xt, xv, yt, yv, wt, wv, flat_train, flat_monitor, smoke):
    torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
    model=make_model('tabm',xt.shape[1],trial,study).cuda()
    optimizer=torch.optim.AdamW(model.parameters(),lr=trial['lr'],weight_decay=trial['weight_decay'])
    best=float('inf');best_epoch=-1;state=None;history=[];stop='epochs'
    torch.cuda.synchronize();torch.cuda.reset_peak_memory_stats();tick=time.perf_counter();cpu=time.process_time()
    for epoch in range(2 if smoke else study['nn_max_epochs']):
        model.train();order=torch.randperm(len(xt),device='cuda');total=torch.zeros((),device='cuda')
        for idx in order.split(study['batch_size']):
            optimizer.zero_grad(set_to_none=True)
            raw=model(xt[idx]).reshape(len(idx),-1);error=(raw-yt[idx,None]).square()
            loss=(error*wt[idx,None]).mean() if flat_train else error.mean()
            loss.backward();optimizer.step();total+=loss.detach()*len(idx)
        model.eval()
        with torch.no_grad():
            pred=torch.cat([model(a).reshape(len(a),-1).mean(1) for a in xv.split(study['validation_batch_size'])])
            error=(pred-yv).square()
            score=float((error*wv).sum()/wv.sum()) if flat_monitor else float(error.mean())
        history.append(dict(epoch=epoch,train_mse=float(total/len(xt)),validation_mse=score))
        if not np.isfinite(score):raise RuntimeError('Non-finite weighted objective')
        if score<best:
            best=score;best_epoch=epoch;state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
        if time.perf_counter()-tick>=study['max_trial_wall_s']:stop='time';break
        if epoch-best_epoch>=study['patience_epochs']:stop='patience';break
    torch.cuda.synchronize();wall=time.perf_counter()-tick;used=time.process_time()-cpu
    peak=torch.cuda.max_memory_allocated()/1024**2;model.load_state_dict(state);model.eval()
    with torch.no_grad():
        pred=torch.cat([model(a).reshape(len(a),-1).mean(1) for a in xv.split(study['validation_batch_size'])])
    cost=dict(train_wall_s=wall,train_cpu_s=used,gpu_peak_allocated_MiB=peak,parameters=sum(p.numel() for p in model.parameters()),
              best_iteration=best_epoch,iterations=len(history),stop_reason=stop)
    return pred.cpu().numpy(),cost,history,state


def weighted_bdt(trial, base, study, seed, xt, xv, yt, yv, wt, wv, smoke):
    params=dict(base['xgboost'])
    for k in ['n_estimators','early_stopping_rounds','n_jobs']:params.pop(k)
    params.update(max_depth=trial['max_depth'],device='cuda',objective='reg:squarederror',seed=seed,nthread=1)
    train=xgb.DMatrix(xt,label=yt,weight=wt,nthread=1);val=xgb.DMatrix(xv,label=yv,weight=wv,nthread=1)
    limit=TimeLimit(study['max_trial_wall_s']);history={};tick=time.perf_counter();cpu=time.process_time()
    model=xgb.train(params,train,num_boost_round=20 if smoke else trial['rounds'],evals=[(train,'train'),(val,'validation')],
                    early_stopping_rounds=study['bdt_patience'],callbacks=[limit],evals_result=history,verbose_eval=False)
    wall=time.perf_counter()-tick;used=time.process_time()-cpu
    pred=model.predict(val,iteration_range=(0,model.best_iteration+1))
    cost=dict(train_wall_s=wall,train_cpu_s=used,gpu_peak_allocated_MiB='unmeasured',parameters='',best_iteration=model.best_iteration,
              iterations=len(history['train']['rmse']),stop_reason='time' if limit.hit else 'rounds' if len(history['train']['rmse'])==trial['rounds'] else 'patience')
    return pred,cost,history,model


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--architecture',choices=['bdt','tabm'],required=True);p.add_argument('--mode',choices=['UU','FU','UF','FF'],required=True)
    p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--smoke',action='store_true');args=p.parse_args()
    repo=args.repo;out=args.output_dir;out.mkdir(parents=True,exist_ok=True);tick=time.perf_counter();cpu=time.process_time()
    torch.set_num_threads(1);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    cfg=yaml.safe_load((repo/'ml/configs/prior.yaml').read_text());study=yaml.safe_load((repo/cfg['reference_study']).read_text())
    base=yaml.safe_load((repo/'ml/configs/baseline.yaml').read_text());assert study['max_trial_wall_s']==cfg['max_fit_wall_s']
    rows=list(csv.DictReader((repo/'ml/configs/files.tsv').open(),delimiter='\t'));train,tgroups=load(rows,base,'train');val,groups=load(rows,base,'validation')
    assert not set(tgroups)&set(groups)
    names=sum([base['feature_groups'][g] for g in base['feature_versions'][cfg['feature_version']]],[]);check_features(names,sum(base['feature_groups'].values(),[]))
    wt,counts,mapping=bin_weights(train[base['target']],train[base['target']],cfg['energy_edges_GeV'])
    wv,_,_=bin_weights(train[base['target']],val[base['target']],cfg['energy_edges_GeV'])
    weights=dict(counts=counts.tolist(),mapping=mapping.tolist(),train_sumw=float(wt.sum()),train_sumw2=float((wt**2).sum()),train_Neff=float(wt.sum()**2/(wt**2).sum()))
    xt,xv,pre=preprocess(np.column_stack([train[k] for k in names]),np.column_stack([val[k] for k in names]))
    log_train=np.log(train[base['target']]);center=float(log_train.mean());spread=float(log_train.std())
    yt=((log_train-center)/spread).astype('float32');yv=((np.log(val[base['target']])-center)/spread).astype('float32')
    if args.smoke:
        xt,xv,yt,yv,wt,wv=xt[:1200],xv[:400],yt[:1200],yv[:400],wt[:1200],wv[:400]
        val={k:v[:400] for k,v in val.items()};groups=groups[:400]
    setting=cfg['modes'][args.mode];flat_train=setting['train']=='flat'
    wt=wt if flat_train else np.ones(len(yt));wv=wv if setting['monitor']=='flat' else np.ones(len(yv))
    if args.architecture=='tabm':xt,xv,yt,yv,wt,wv=[torch.as_tensor(a.astype('float32'),device='cuda') for a in [xt,xv,yt,yv,wt,wv]]
    trial=cfg['fixed_trials'][args.architecture];assert trial in study['bdt_trials' if args.architecture=='bdt' else 'nn_trials']
    predictions={};costs=[];traces={}
    preprocessing=dict(features=names,preprocessor=pre,target_center=center,target_spread=spread)
    for si,seed in enumerate(cfg['seeds'][:1] if args.smoke else cfg['seeds']):
        if args.mode=='UU':
            fit=fit_bdt if args.architecture=='bdt' else fit_nn
            fit_args=(trial,base,study,seed,xt,xv,yt,yv,args.smoke) if args.architecture=='bdt' else ('tabm',trial,study,seed,xt,xv,yt,yv,args.smoke)
            raw,cost,trace,state=fit(*fit_args)
        elif args.architecture=='bdt':raw,cost,trace,state=weighted_bdt(trial,base,study,seed,xt,xv,yt,yv,wt,wv,args.smoke)
        else:raw,cost,trace,state=weighted_nn(trial,study,seed,xt,xv,yt,yv,wt,wv,flat_train,setting['monitor']=='flat',args.smoke)
        raw=raw.astype(float)*spread+center;prediction=np.exp(raw);predictions[f'seed_{si}']=prediction;traces[f'seed_{si}']=trace
        costs.append(dict(seed_index=si,seed=seed,validation_unit_log_MSE=float(np.mean((raw-np.log(val[base['target']]))**2)),**cost))
        if si==0:
            if args.architecture=='bdt':state.save_model(out/'best.ubj')
            else:torch.save(dict(architecture='tabm',trial=trial,state_dict=state,study=study,prior_study=cfg,mode=args.mode,**preprocessing),out/'best.pt')
        print(json.dumps(costs[-1]),flush=True)
    np.savez_compressed(out/'predictions.npz',run=val['run'],eventID=val['eventID'],truth_E_GeV=val[base['target']],group=groups,**predictions)
    write_table(out/'costs.tsv',costs);(out/'learning_traces.json').write_text(json.dumps(traces)+'\n')
    (out/'preprocessing.json').write_text(json.dumps(preprocessing,indent=2)+'\n')
    summary=dict(architecture=args.architecture,mode=args.mode,smoke=args.smoke,study=cfg,weights=weights,train_events=len(yt),validation_events=len(yv),
                 wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                 gpu=torch.cuda.get_device_name(0),torch_version=torch.__version__,xgboost_version=xgb.__version__,calibration_test_challenge_evaluated=False)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
