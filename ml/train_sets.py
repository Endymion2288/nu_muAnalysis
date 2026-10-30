#!/usr/bin/env python3
"""Full-object Deep Sets with a matched summary encoder and association controls."""
import argparse
import json
import resource
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn
import yaml

from set_data import PointBatches,load_data
from train_bdt import metric_values,write_table
from train_tabular import ResidualBlock


class SetRegressor(nn.Module):
    def __init__(self,variant,dim,trial,cfg):
        super().__init__();self.variant=variant
        hidden=cfg['encoder']['hidden'];embedding=cfg['encoder']['output'];w=trial['width'];drop=trial['dropout']
        self.encoder=nn.Sequential(nn.Linear(10,hidden),nn.ReLU(),nn.Linear(hidden,embedding),nn.ReLU())
        self.head=nn.Sequential(nn.Linear(dim+4*embedding,w),*[ResidualBlock(w,drop) for _ in range(trial['blocks'])],
                                nn.LayerNorm(w),nn.ReLU(),nn.Linear(w,1))

    def forward(self,scalar,summary,points=None,counts=None):
        if self.variant=='summary':pooled=self.encoder(summary)
        else:
            encoded=self.encoder(points)
            summed=torch.segment_reduce(encoded,'sum',lengths=counts.reshape(-1)).reshape(len(scalar),4,-1)
            if self.variant=='global':
                pooled=(summed.sum(1)/counts.sum(1).clamp_min(1)[:,None])[:,None,:].expand(-1,4,-1)
            else:pooled=summed/counts.clamp_min(1)[:,:,None]
        return self.head(torch.cat([scalar,pooled.reshape(len(scalar),-1)],dim=1)).squeeze(1)


def tensors(part):
    return {k:torch.as_tensor(part[k],device='cuda') for k in ['scalar','summary','y']}


def predict(model,part,tensor,cloud,batch_size):
    output=[];model.eval()
    with torch.no_grad():
        for begin in range(0,len(part['y']),batch_size):
            ids=np.arange(begin,min(begin+batch_size,len(part['y'])));idx=torch.as_tensor(ids,device=tensor['scalar'].device)
            points,counts=(None,None) if cloud is None else cloud.batch(ids)
            output.append(model(tensor['scalar'][idx],tensor['summary'][idx],points,counts))
    return torch.cat(output)


def fit(variant,trial,cfg,parts,clouds,seed,smoke):
    torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
    model=SetRegressor(variant,parts[0]['scalar'].shape[1],trial,cfg).cuda()
    initial_encoder={k:v.detach().cpu().clone() for k,v in model.encoder.state_dict().items()}
    optimizer=torch.optim.AdamW(model.parameters(),lr=trial['lr'],weight_decay=trial['weight_decay'])
    ts=[tensors(p) for p in parts];rng=np.random.default_rng(seed);best=float('inf');state=None;best_epoch=-1;history=[];stop='epochs'
    for cloud in clouds:
        if cloud is not None:cloud.batch_points_max_seen=0
    torch.cuda.synchronize();torch.cuda.reset_peak_memory_stats();tick=time.perf_counter();cpu=time.process_time()
    for epoch in range(2 if smoke else cfg['epochs']):
        model.train();order=rng.permutation(len(parts[0]['y']));total=torch.zeros((),device='cuda')
        for begin in range(0,len(order),cfg['batch_size']):
            ids=order[begin:begin+cfg['batch_size']];idx=torch.as_tensor(ids,device='cuda')
            points,counts=(None,None) if clouds[0] is None else clouds[0].batch(ids)
            optimizer.zero_grad(set_to_none=True)
            pred=model(ts[0]['scalar'][idx],ts[0]['summary'][idx],points,counts)
            loss=(pred-ts[0]['y'][idx]).square().mean();loss.backward();optimizer.step();total+=loss.detach()*len(ids)
        pred=predict(model,parts[1],ts[1],clouds[1],cfg['validation_batch_size'])
        score=float((pred-ts[1]['y']).square().mean());train=float(total/len(order))
        if not np.isfinite(score) or not np.isfinite(train):raise RuntimeError('Non-finite objective')
        history.append(dict(epoch=epoch,train_mse=train,validation_mse=score))
        if score<best:
            best=score;best_epoch=epoch;state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
        if time.perf_counter()-tick>=cfg['max_fit_wall_s']:stop='time';break
        if epoch-best_epoch>=cfg['patience']:stop='patience';break
    torch.cuda.synchronize();wall=time.perf_counter()-tick;used=time.process_time()-cpu;peak=torch.cuda.max_memory_allocated()/1024**2
    model.load_state_dict(state);model.eval();pred=predict(model,parts[1],ts[1],clouds[1],cfg['validation_batch_size'])
    change=sum(float((v.detach().cpu()-initial_encoder[k]).square().sum()) for k,v in model.encoder.state_dict().items())
    norm=sum(float(v.square().sum()) for v in initial_encoder.values())
    cost=dict(train_wall_s=wall,train_cpu_s=used,best_epoch=best_epoch,epochs=len(history),stop_reason='smoke_epochs' if smoke else stop,
              gpu_peak_allocated_MiB=peak,parameters=sum(p.numel() for p in model.parameters()),encoder_relative_weight_change=np.sqrt(change/norm),
              max_batch_points=0 if clouds[0] is None else clouds[0].batch_points_max_seen)
    return pred.cpu().numpy(),state,cost,history


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--cache-root',type=Path);p.add_argument('--variant',choices=['summary','global','full','reassigned'],required=True)
    p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--smoke',action='store_true')
    args=p.parse_args();repo=args.repo;out=args.output_dir;out.mkdir(parents=True,exist_ok=True);tick=time.perf_counter();cpu=time.process_time()
    torch.set_num_threads(1);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    cfg=yaml.safe_load((repo/'ml/configs/sets.yaml').read_text());geo=yaml.safe_load((repo/cfg['geometry_config']).read_text())
    baseline=yaml.safe_load((repo/'ml/configs/baseline.yaml').read_text())
    parts,preprocessor=load_data(repo,args.cache_root or repo,cfg,baseline,args.smoke)
    predictions={};costs=[];traces={};winner=None;best=float('inf');cloud_seed=None;clouds=None;setup=[]
    def run(trial_index,seed_index,phase):
        nonlocal clouds,cloud_seed
        seed=cfg['seeds'][seed_index]
        required_seed=seed if args.variant=='reassigned' else cfg['seeds'][0]
        if cloud_seed!=required_seed:
            clouds=None;torch.cuda.empty_cache();t=time.perf_counter()
            clouds=[None,None] if args.variant=='summary' else [PointBatches(a['points'],a['counts'],a['metadata'],geo,args.variant,required_seed) for a in parts]
            setup.append(dict(seed_index=seed_index,wall_s=time.perf_counter()-t));cloud_seed=required_seed
        raw,state,cost,trace=fit(args.variant,cfg['trials'][trial_index],cfg,parts,clouds,seed,args.smoke)
        raw=raw.astype(float)*preprocessor['target_spread']+preprocessor['target_center'];prediction=np.exp(raw)
        score=float(np.mean((raw-np.log(parts[1]['target']))**2));key=f'{phase}_trial{trial_index}_seed{seed_index}'
        costs.append(dict(fit=key,seed_index=seed_index,seed=seed,trial=trial_index,phase=phase,validation_log_MSE=score,**cost))
        traces[key]=trace;print(json.dumps(costs[-1]),flush=True)
        return prediction,state,score
    for ti in range(1 if args.smoke else len(cfg['trials'])):
        pred,state,score=run(ti,0,'tune')
        if score<best:
            best=score;winner=ti;predictions['seed_0']=pred
            torch.save(dict(variant=args.variant,trial=cfg['trials'][ti],study=cfg,state_dict=state,preprocessing=preprocessor),out/'best.pt')
    if not args.smoke:
        for si in [1,2]:predictions[f'seed_{si}'],_,_=run(winner,si,'repeat')
    meta=parts[1]['metadata']
    np.savez_compressed(out/'predictions.npz',run=meta['run'],eventID=meta['eventID'],truth_E_GeV=parts[1]['target'],group=parts[1]['groups'],**predictions)
    write_table(out/'costs.tsv',costs);(out/'learning_traces.json').write_text(json.dumps(traces)+'\n')
    summary=dict(variant=args.variant,smoke=args.smoke,study=cfg,winner_trial=winner,train_events=len(parts[0]['y']),validation_events=len(parts[1]['y']),
                 point_events_train=int(sum(parts[0]['counts'].sum(2).sum(1)>0)),train_points=int(parts[0]['counts'].sum()),validation_points=int(parts[1]['counts'].sum()),
                 wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                 gpu=torch.cuda.get_device_name(0),torch_version=torch.__version__,cuda_version=torch.version.cuda,point_setup=setup,
                 calibration_test_challenge_evaluated=False)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
