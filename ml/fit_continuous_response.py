#!/usr/bin/env python3
"""One immutable stage62 fit and bounded chunked inference, run through Condor."""
import argparse
from datetime import datetime, timezone
import json
import socket
import time

import numpy as np
import torch
from torch import nn

from continuous_response import (OUT, ART, MODELS, inputs, transform, pair_indices,
    pair_matrix, network, training_weights, scan, density, summarize_scan,
    begin, resources, save, subset)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--model',choices=MODELS,required=True)
    args=parser.parse_args();start=begin()
    p=json.loads((OUT/'protocol.json').read_text())
    work=OUT/args.model;art=ART/args.model
    work.mkdir(exist_ok=True);art.mkdir(parents=True,exist_ok=True)
    assert not (work/'fit.json').exists() and not (art/'model.pt').exists(), 'Never repeat a started/completed fit'
    save(work/'fit.json',dict(status='started',model=args.model,formal_fit_calls=1,utc=datetime.now(timezone.utc).isoformat()))
    torch.set_num_threads(p['cpu_threads']);torch.use_deterministic_algorithms(True);torch.manual_seed(p['seed'])
    d=inputs();tr=subset(d,d['role']=='train');mu=args.model=='C_mu_unit'
    x,lp=transform(tr['x'],p['feature_state'],mu);t=np.log(tr['truth_E_GeV'])
    w,_=training_weights(t,p,args.model=='B_full_flat');n=len(t)
    ix,it=pair_indices(n,w,p['negative_seed'])
    positive=pair_matrix(x,lp,t,np.arange(n),np.arange(n),p)
    negative=pair_matrix(x,lp,t,ix,it,p)
    xx=torch.from_numpy(np.concatenate([positive,negative]))
    yy=torch.from_numpy(np.r_[np.ones(n),np.zeros(2*n)].astype('float32'))
    ww=torch.from_numpy(np.r_[w,np.full(2*n,.5)].astype('float32'))
    model=network(xx.shape[1]);optimizer=torch.optim.AdamW(model.parameters(),lr=p['learning_rate'],weight_decay=p['weight_decay'])
    loss_fn=nn.BCEWithLogitsLoss(reduction='none')
    order_rng=torch.Generator().manual_seed(p['seed']+1)
    history=[];tick=time.perf_counter();cpu=time.process_time()
    for epoch in range(p['epochs']):
        model.train();order=torch.randperm(len(xx),generator=order_rng);total=0.
        for idx in order.split(p['batch_size']):
            optimizer.zero_grad(set_to_none=True)
            loss=(loss_fn(model(xx[idx]).ravel(),yy[idx])*ww[idx]).mean()*1.5
            assert torch.isfinite(loss)
            loss.backward();optimizer.step();total+=float(loss.detach())*len(idx)
        history.append(dict(epoch=epoch+1,weighted_binary_loss=total/len(xx),wall_s=time.perf_counter()-tick))
        if epoch%20==19:print(args.model,history[-1],flush=True)
        assert time.perf_counter()-start[0]<p['per_job_wall_budget_s']
        assert time.process_time()-start[1]<p['per_job_cpu_budget_s']
    fit_wall=time.perf_counter()-tick;fit_cpu=time.process_time()-cpu
    model.eval()
    frozen=datetime.now(timezone.utc).isoformat()
    torch.save(dict(state_dict=model.state_dict(),input_dim=xx.shape[1],model=args.model,seed=p['seed'],frozen_before_eval_utc=frozen),art/'model.pt')
    # Final model is persisted before evaluation; no held-out checkpoint selection.
    del xx,yy,ww,positive,negative
    arrays={};offset=None;scan_tick=time.perf_counter()
    for role in ['cal','eval']:
        dd=subset(d,d['role']==role);rx,rlp=transform(dd['x'],p['feature_state'],mu)
        summary=summarize_scan(model,rx,rlp,p,np.log(dd['truth_E_GeV']))
        if role=='cal':offset=float(np.mean(np.log(dd['truth_E_GeV'])-summary['point_raw_log']))
        summary['point_cal_log']=summary['point_raw_log']+offset
        arrays[role+'_row']=dd['row']
        arrays.update({role+'_'+key:value for key,value in summary.items()})
    np.savez_compressed(art/'predictions.npz',**arrays)
    curves=[]
    for role in ['train','cal']:
        ids=[c['row'] for c in p['curve_rows'] if c['role']==role]
        dd=subset(d,np.isin(d['row'],ids));rx,rlp=transform(dd['x'],p['feature_state'],mu)
        curves.append(dict(role=role,row=dd['row'].tolist(),truth_E_GeV=dd['truth_E_GeV'].tolist(),
            pz_GeV=dd['pz'].tolist(),logits=scan(model,rx,rlp,p).tolist()))
    save(work/'curves.json',curves)
    cal=subset(d,d['role']=='cal');rx,rlp=transform(cal['x'][:16],p['feature_state'],mu)
    y=np.log(cal['truth_E_GeV'][:16]);coarse=density(scan(model,rx,rlp,p),p,y)
    refined=dict(p,scan_log_grid=np.linspace(p['scan_log_grid'][0],p['scan_log_grid'][-1],257).tolist())
    fine=density(scan(model,rx,rlp,refined),refined,y)
    refinement={key:float(np.max(abs(coarse[key]-fine[key]))) for key in ['point_raw_log','log_density','crps_logE','probabilities']}
    result=dict(**resources(start),status='completed',model=args.model,formal_fit_calls=1,epochs=len(history),
        train_N=n,training_pair_N=3*n,parameter_count=sum(v.numel() for v in model.parameters()),input_dim=model[0].in_features,
        fit_wall_s=fit_wall,fit_cpu_s=fit_cpu,inference_and_diagnostics_wall_s=time.perf_counter()-scan_tick,
        global_cal_offset_log=offset,frozen_before_eval_utc=frozen,history=history,
        numerical_refinement_first16cal=refinement,host=socket.getfqdn(),torch_version=torch.__version__,
        cpu_threads=torch.get_num_threads(),negative_unique_X=int(len(np.unique(ix))),negative_unique_t=int(len(np.unique(it))),
        retained_bytes=sum(f.stat().st_size for f in art.iterdir()))
    assert result['cpu_s']<p['per_job_cpu_budget_s']
    assert result['peak_rss_MiB']<p['request_memory_MB']*1e6/1024**2
    save(work/'fit.json',result);print(json.dumps({k:v for k,v in result.items() if k!='history'},indent=2),flush=True)


if __name__=='__main__':main()
