#!/usr/bin/env python3
"""Fixed-information GPU comparison; truth is never an input to these models."""
import argparse
import csv
import json
import resource
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn
import xgboost as xgb
import yaml

from train_bdt import check_features, load, metric_values, write_table


class ResidualBlock(nn.Module):
    def __init__(self,width,dropout):
        super().__init__()
        self.branch=nn.Sequential(nn.LayerNorm(width),nn.Linear(width,2*width),nn.ReLU(),
                                  nn.Dropout(dropout),nn.Linear(2*width,width),nn.Dropout(dropout))

    def forward(self,x):return x+self.branch(x)


def make_model(architecture,dim,trial,study):
    w=trial['width']; blocks=trial['blocks']; drop=trial['dropout']
    if architecture=='mlp':
        layers=[]
        for i in range(blocks):layers += [nn.Linear(dim if i==0 else w,w),nn.ReLU(),nn.Dropout(drop)]
        return nn.Sequential(*layers,nn.Linear(w,1))
    if architecture=='resnet':
        return nn.Sequential(nn.Linear(dim,w),*[ResidualBlock(w,drop) for _ in range(blocks)],
                             nn.LayerNorm(w),nn.ReLU(),nn.Linear(w,1))
    if architecture=='tabm':
        from tabm import TabM
        from rtdl_num_embeddings import LinearReLUEmbeddings
        return TabM.make(n_num_features=dim,cat_cardinalities=None,d_out=1,
                         n_blocks=blocks,d_block=w,dropout=drop,k=study['tabm']['k'],
                         num_embeddings=LinearReLUEmbeddings(dim,study['tabm']['d_embedding']))
    raise ValueError(architecture)


def preprocess(xt,xv):
    xt=np.where(np.isfinite(xt),xt,np.nan);xv=np.where(np.isfinite(xv),xv,np.nan)
    scale=np.nanmedian(abs(xt),axis=0);scale=np.where(np.isfinite(scale)&(scale>1e-6),scale,1.)
    a=np.arcsinh(xt/scale);b=np.arcsinh(xv/scale)
    fill=np.nanmedian(a,axis=0);fill=np.where(np.isfinite(fill),fill,0.)
    missing_t=~np.isfinite(a);missing_v=~np.isfinite(b)
    a=np.where(missing_t,fill,a);b=np.where(missing_v,fill,b)
    mean=a.mean(axis=0);std=a.std(axis=0);std=np.where(std>1e-8,std,1.)
    a=np.column_stack([(a-mean)/std,missing_t]);b=np.column_stack([(b-mean)/std,missing_v])
    state={k:v.tolist() for k,v in dict(scale=scale,fill=fill,mean=mean,std=std).items()}
    return a.astype('float32'),b.astype('float32'),state


class TimeLimit(xgb.callback.TrainingCallback):
    def __init__(self,seconds):self.seconds=seconds;self.started=time.perf_counter();self.hit=False
    def after_iteration(self,model,epoch,evals_log):
        self.hit=time.perf_counter()-self.started>=self.seconds
        return self.hit


def fit_nn(arch,trial,study,seed,xt,xv,yt,yv,smoke):
    torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
    model=make_model(arch,xt.shape[1],trial,study).cuda()
    optimizer=torch.optim.AdamW(model.parameters(),lr=trial['lr'],weight_decay=trial['weight_decay'])
    batch=study['batch_size'];eval_batch=study['validation_batch_size']
    best=float('inf');state=None;best_epoch=-1;history=[];stopped='epochs'
    torch.cuda.synchronize();torch.cuda.reset_peak_memory_stats();tick=time.perf_counter();cpu=time.process_time()
    for epoch in range(2 if smoke else study['nn_max_epochs']):
        model.train();order=torch.randperm(len(xt),device='cuda');total=torch.zeros((),device='cuda')
        for idx in order.split(batch):
            optimizer.zero_grad(set_to_none=True)
            raw=model(xt[idx]).reshape(len(idx),-1)
            # Each TabM member learns the target separately (paper's loss).
            loss=(raw-yt[idx,None]).square().mean()
            loss.backward();optimizer.step();total+=loss.detach()*len(idx)
        model.eval()
        with torch.no_grad():
            pred=torch.cat([model(a).reshape(len(a),-1).mean(1) for a in xv.split(eval_batch)])
            score=float((pred-yv).square().mean())
        history.append(dict(epoch=epoch,train_mse=float(total/len(xt)),validation_mse=score))
        if not np.isfinite(score):raise RuntimeError('Non-finite validation loss')
        if score<best:
            best=score;best_epoch=epoch;state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
        if time.perf_counter()-tick>=study['max_trial_wall_s']:
            stopped='time';break
        if epoch-best_epoch>=study['patience_epochs']:
            stopped='patience';break
    torch.cuda.synchronize();wall=time.perf_counter()-tick;used=time.process_time()-cpu
    peak=torch.cuda.max_memory_allocated()/1024**2;model.load_state_dict(state);model.eval()
    times=[]
    with torch.no_grad():
        for repeat in range(6):
            torch.cuda.synchronize();start=time.perf_counter()
            pred=torch.cat([model(a).reshape(len(a),-1).mean(1) for a in xv.split(eval_batch)])
            torch.cuda.synchronize()
            if repeat:times.append(time.perf_counter()-start)
    cost=dict(train_wall_s=wall,train_cpu_s=used,inference_wall_s=float(np.median(times)),
              gpu_peak_allocated_MiB=peak,parameters=sum(p.numel() for p in model.parameters()),
              best_iteration=best_epoch,iterations=len(history),stop_reason=stopped)
    return pred.cpu().numpy(),cost,history,state


def fit_bdt(trial,base,study,seed,xt,xv,yt,yv,smoke):
    import cupy as cp
    params=dict(base['xgboost'])
    for k in ['n_estimators','early_stopping_rounds','n_jobs']:params.pop(k)
    params.update(max_depth=trial['max_depth'],device='cuda',objective='reg:squarederror',seed=seed,nthread=1)
    train=xgb.DMatrix(xt,label=yt,nthread=1);val=xgb.DMatrix(xv,label=yv,nthread=1)
    limit=TimeLimit(study['max_trial_wall_s']);history={};tick=time.perf_counter();cpu=time.process_time()
    model=xgb.train(params,train,num_boost_round=20 if smoke else trial['rounds'],
                    evals=[(train,'train'),(val,'validation')],early_stopping_rounds=study['bdt_patience'],
                    callbacks=[limit],evals_result=history,verbose_eval=False)
    wall=time.perf_counter()-tick;used=time.process_time()-cpu;times=[]
    gpu_xv=cp.asarray(xv)
    for repeat in range(6):
        # A persistent DMatrix can cache predictions; inplace_predict measures work.
        # Like NN timing, inputs are already on the GPU; transfers are excluded.
        cp.cuda.get_current_stream().synchronize();start=time.perf_counter()
        pred=model.inplace_predict(gpu_xv,iteration_range=(0,model.best_iteration+1))
        cp.cuda.get_current_stream().synchronize()
        if repeat:times.append(time.perf_counter()-start)
    cost=dict(train_wall_s=wall,train_cpu_s=used,inference_wall_s=float(np.median(times)),gpu_peak_allocated_MiB='unmeasured',parameters='',
              best_iteration=model.best_iteration,iterations=len(history['train']['rmse']),
              stop_reason='time' if limit.hit else 'rounds' if len(history['train']['rmse'])==trial['rounds'] else 'patience')
    return cp.asnumpy(pred),cost,history,model


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--architecture',choices=['bdt','mlp','resnet','tabm'],required=True)
    p.add_argument('--version',choices=['F3','F5'],required=True)
    p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--smoke',action='store_true')
    args=p.parse_args();repo=args.repo;out=args.output_dir;out.mkdir(parents=True,exist_ok=True)
    started=time.perf_counter();cpu=time.process_time();torch.set_num_threads(1)
    if not torch.cuda.is_available():raise RuntimeError('GPU requested but unavailable')
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    study=yaml.safe_load((repo/'ml/configs/tabular.yaml').read_text());base=yaml.safe_load((repo/'ml/configs/baseline.yaml').read_text())
    rows=list(csv.DictReader((repo/'ml/configs/files.tsv').open(),delimiter='\t'))
    train,tgroups=load(rows,base,'train');val,groups=load(rows,base,'validation')
    if set(tgroups)&set(groups):raise RuntimeError('Source leakage')
    if args.smoke:
        train={k:v[:1200] for k,v in train.items()};val={k:v[:400] for k,v in val.items()};groups=groups[:400]
    names=sum([base['feature_groups'][g] for g in base['feature_versions'][args.version]],[])
    check_features(names,sum(base['feature_groups'].values(),[]))
    pre=time.perf_counter();xt,xv,preprocessor=preprocess(np.column_stack([train[k] for k in names]),np.column_stack([val[k] for k in names]))
    ytrain=np.log(train[base['target']]);y=np.log(val[base['target']]);center=float(ytrain.mean());spread=float(ytrain.std())
    yt=((ytrain-center)/spread).astype('float32');yv=((y-center)/spread).astype('float32');prewall=time.perf_counter()-pre
    if args.architecture!='bdt':xt,xv,yt,yv=[torch.as_tensor(a,device='cuda') for a in [xt,xv,yt,yv]]
    trials=study['bdt_trials' if args.architecture=='bdt' else 'nn_trials']
    costs=[];metrics=[];traces={};predictions={};best=float('inf');winner=None
    def fit(trial_index,seed_index,phase):
        trial=trials[trial_index];seed=study['seeds'][seed_index]
        if args.architecture=='bdt':raw,cost,trace,state=fit_bdt(trial,base,study,seed,xt,xv,yt,yv,args.smoke)
        else:raw,cost,trace,state=fit_nn(args.architecture,trial,study,seed,xt,xv,yt,yv,args.smoke)
        raw=raw.astype(float)*spread+center;prediction=np.exp(raw);score=float(np.mean((raw-y)**2))
        key=f'{phase}_trial{trial_index}_seed{seed_index}'
        costs.append(dict(fit=key,trial=trial_index,seed_index=seed_index,seed=seed,phase=phase,validation_log_MSE=score,
                          **cost,inference_events_per_s=len(y)/cost['inference_wall_s']))
        metrics.append(dict(fit=key,**metric_values(np.exp(y),prediction,np.ones(len(y),dtype=bool))))
        traces[key]=trace;print(json.dumps(costs[-1]),flush=True)
        return prediction,score,state
    for i in range(1 if args.smoke else len(trials)):
        prediction,score,state=fit(i,0,'tune')
        if score<best:
            best=score;winner=i;predictions['seed_0']=prediction
            if args.architecture=='bdt':state.save_model(out/'best.ubj')
            else:torch.save(dict(architecture=args.architecture,trial=trials[i],state_dict=state,study=study,features=names,
                                 preprocessor=preprocessor,target_center=center,target_spread=spread),out/'best.pt')
    if not args.smoke:
        for si in [1,2]:predictions[f'seed_{si}'],_,_=fit(winner,si,'repeat')
    np.savez_compressed(out/'predictions.npz',run=val['run'],eventID=val['eventID'],truth_E_GeV=val[base['target']],group=groups,**predictions)
    write_table(out/'costs.tsv',costs);write_table(out/'metrics.tsv',metrics)
    (out/'learning_traces.json').write_text(json.dumps(traces)+'\n')
    (out/'preprocessing.json').write_text(json.dumps(dict(features=names,preprocessor=preprocessor,target_center=center,target_spread=spread),indent=2)+'\n')
    summary=dict(architecture=args.architecture,version=args.version,study=study,baseline=base,smoke=args.smoke,
                 winner_trial=winner,trial_count=1 if args.smoke else len(trials),train_events=len(yt),validation_events=len(yv),
                 raw_features=len(names),expanded_features=xt.shape[1],preprocessing_wall_s=prewall,
                 wall_s=time.perf_counter()-started,cpu_s=time.process_time()-cpu,
                 peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,gpu=torch.cuda.get_device_name(0),
                 torch_version=torch.__version__,cuda_version=torch.version.cuda,xgboost_version=xgb.__version__,
                 calibration_test_challenge_evaluated=False)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
