"""Stage96 two preregistered point fits: constant versus measured candidate branch."""
import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn

from prepare_candidate_ablation import REPO, OUT, CACHE, SEED, NODE_NAMES, EDGE_NAMES, save, cost, arrays
from retrain_accurate_posterior import reconstruct
from compare_energy_architectures import representation

ART=REPO/'ml/artifacts/stage96'


def table(name,rows):
    import csv
    with (OUT/name).open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n');w.writeheader();w.writerows(rows)


def transforms(values,kinds,state=None):
    missing=~np.isfinite(values);v=values.astype(float).copy()
    if state is None:
        scale=np.nanmedian(abs(v),axis=0);scale=np.where(np.isfinite(scale)&(scale>1e-8),scale,1.)
        state=dict(kinds=kinds,scale=scale.tolist())
    for j,(kind,scale) in enumerate(zip(state['kinds'],state['scale'])):
        if kind=='log':v[:,j]=np.log(v[:,j]/scale)
        elif kind=='log1p':v[:,j]=np.log1p(v[:,j]/scale)
        elif kind=='asinh':v[:,j]=np.arcsinh(v[:,j]/scale)
    if 'median' not in state:
        med=np.nanmedian(v,axis=0);med=np.where(np.isfinite(med),med,0.)
        q=np.nanquantile(v,[.25,.75],axis=0);iqr=q[1]-q[0];iqr=np.where(np.isfinite(iqr)&(iqr>0),iqr,1.)
        state.update(median=med.tolist(),IQR=iqr.tolist())
    z=(np.where(missing,state['median'],v)-state['median'])/state['IQR']
    result=np.column_stack([z,missing]).astype('float32');assert np.isfinite(result).all()
    return result,state


def node_kinds():
    return ['log' if k=='pz0_GeV' else 'log1p' if k in ['chi2ndof','nLayers','nDoF'] else 'identity'
            if k in ['charge','module_eta0','module_phi0','station_mask'] else 'asinh' for k in NODE_NAMES]


def input_arrays(d,c,state=None):
    np.testing.assert_array_equal(d['row'],c['row'])
    counts=np.diff(c['offsets']);ec=np.diff(c['edge_offsets']);N=len(counts)
    maxn=max(1,int(counts.max()));maxe=max(1,int(ec.max()))
    nr=np.repeat(np.arange(N),counts);er=np.repeat(np.arange(N),ec)
    tr=d['role']==1
    if state is None:
        _,ns=transforms(c['nodes'][tr[nr]],node_kinds())
        _,es=transforms(c['edges'][tr[er]],['log1p']*4+['identity'])
        traincounts=np.log1p(counts[tr]);med=float(np.median(traincounts));q=np.quantile(traincounts,[.25,.75]);iqr=float(q[1]-q[0]) or 1.
        state=dict(nodes=ns,edges=es,count_median=med,count_IQR=iqr,summary=json.loads((REPO/'workbook/stage94_energy_ml/preprocessing.json').read_text())['C'])
    xn,_=transforms(c['nodes'],node_kinds(),state['nodes']);xe,_=transforms(c['edges'],['log1p']*4+['identity'],state['edges'])
    node=np.zeros((N,maxn,44),np.float32);edge=np.zeros((N,maxe,10),np.float32)
    mask=np.arange(maxn)[None,:]<counts[:,None];em=np.arange(maxe)[None,:]<ec[:,None]
    node[mask]=xn;edge[em]=xe
    summary,_,_=representation(d,'C',state['summary'])
    meta=np.column_stack([c['available'],c['available']&(counts==0),
                          (np.log1p(counts)-state['count_median'])/state['count_IQR'],ec>0]).astype('float32')
    result=dict(summary=summary,node=node,node_mask=mask,edge=edge,edge_mask=em,meta=meta)
    assert all(np.isfinite(a).all() for a in result.values())
    return result,state


def subset(c,rows):
    idx=np.searchsorted(c['row'],rows);np.testing.assert_array_equal(c['row'][idx],rows)
    nodes=[c['nodes'][c['offsets'][i]:c['offsets'][i+1]] for i in idx]
    edges=[c['edges'][c['edge_offsets'][i]:c['edge_offsets'][i+1]] for i in idx]
    return dict(row=rows,available=c['available'][idx],nodes=np.concatenate(nodes),edges=np.concatenate(edges),
                offsets=np.r_[0,np.cumsum([len(a) for a in nodes])],edge_offsets=np.r_[0,np.cumsum([len(a) for a in edges])])


def constant_branch(x):
    # Fixed one-node dummy and no edges: independent of actual shape/count/availability.
    N=len(x['summary'])
    return dict(summary=x['summary'],node=np.zeros((N,1,44),np.float32),node_mask=np.ones((N,1),bool),
                edge=np.zeros((N,1,10),np.float32),edge_mask=np.zeros((N,1),bool),
                meta=np.tile(np.array([1,0,0,0],np.float32),(N,1)))


class CandidateModel(nn.Module):
    def __init__(self,center=6.):
        super().__init__()
        self.nodes=nn.Sequential(nn.Linear(44,32),nn.SiLU(),nn.Linear(32,32),nn.SiLU())
        self.edges=nn.Sequential(nn.Linear(10,16),nn.SiLU(),nn.Linear(16,16),nn.SiLU())
        self.body=nn.Sequential(nn.Linear(127+96+32+4,64),nn.SiLU(),nn.Linear(64,64),nn.SiLU())
        self.head=nn.Linear(64,1);nn.init.zeros_(self.head.weight);nn.init.constant_(self.head.bias,center)
    @staticmethod
    def pool(h,m):
        mean=(h*m[:,:,None]).sum(1)/m.sum(1).clamp_min(1)[:,None]
        maximum=h.masked_fill(~m[:,:,None],-torch.inf).amax(1)
        maximum=torch.where(m.any(1)[:,None],maximum,torch.zeros_like(maximum))
        return mean,maximum
    def forward(self,summary,node,node_mask,edge,edge_mask,meta):
        h=self.nodes(node);a,b=self.pool(h,node_mask);lead=h[:,0]*node_mask[:,0,None]
        u,v=self.pool(self.edges(edge),edge_mask)
        return self.head(self.body(torch.cat([summary,a,b,lead,u,v,meta],1))).squeeze(1)


def tensors(x,device):return {k:torch.as_tensor(v,device=device) for k,v in x.items()}
def take(x,idx):return {k:v[idx] for k,v in x.items()}


def qa():
    start=time.perf_counter(),time.process_time();torch.set_num_threads(1)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    c=arrays(CACHE/'QA_candidates.npz');d=reconstruct(c['row']);assert len(d['row'])==len(np.unique(d['key_id']))==40 and np.isin(d['role'],[1,2]).all()
    x,state=input_arrays(d,c);y=torch.tensor(np.log(d['truth_E_GeV']),dtype=torch.float32,device='cuda');w=torch.tensor(d['weight'],dtype=torch.float32,device='cuda')
    # A post-extraction package QA may repeat these same40 at the full input padding size.
    # Only input counts are used; no extra candidate values or target diagnostics enter QA.
    if (CACHE/'candidates.npz').exists():
        with np.load(CACHE/'candidates.npz') as full:
            sizes=[max(1,int(np.diff(full[k]).max())) for k in ['offsets','edge_offsets']]
        for name,mask,size in zip(['node','edge'],['node_mask','edge_mask'],sizes):
            pad=size-x[name].shape[1]
            if pad>0:
                x[name]=np.pad(x[name],((0,0),(0,pad),(0,0)))
                x[mask]=np.pad(x[mask],((0,0),(0,pad)))
    checks=[];invariance=[]
    for cell,xx in [('A',constant_branch(x)),('B',x)]:
        torch.manual_seed(SEED);model=CandidateModel().cuda();xt=tensors(xx,'cuda')
        # Nonzero head verifies body/node VJP without taking an optimizer step.
        with torch.no_grad():model.head.weight.copy_(torch.linspace(-.03,.03,64,device='cuda')[None,:])
        prediction=model(**xt);loss=((prediction-y).square()*w).sum()/w.sum();loss.backward()
        assert torch.isfinite(loss) and all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())
        costs=[];repeat=torch.arange(1024,device='cuda')%40
        for _ in range(4):
            model.zero_grad(set_to_none=True);torch.cuda.synchronize();tick=time.perf_counter()
            pp=model(**take(xt,repeat));ll=((pp-y[repeat]).square()*w[repeat]).sum()/w[repeat].sum();ll.backward();torch.cuda.synchronize();costs.append(time.perf_counter()-tick)
        # Reorder nonleading candidates and their leading-relative edges together.
        altered={k:v.clone() for k,v in xt.items()}
        if altered['node'].shape[1]>2:
            altered['node'][:,1:]=xt['node'][:,1:].flip(1);altered['node_mask'][:,1:]=xt['node_mask'][:,1:].flip(1)
            altered['edge']=xt['edge'].flip(1);altered['edge_mask']=xt['edge_mask'].flip(1)
        with torch.no_grad():delta=float((model(**altered)-model(**xt)).abs().max())
        assert delta<2e-6;invariance.append(dict(cell=cell,permutation_max_logE_delta=delta))
        checks.append(dict(cell=cell,parameters=sum(p.numel() for p in model.parameters()),summary_dimensions=127,
                           node_input=44,edge_input=10,event_meta=4,node_max=xx['node'].shape[1],edge_max=xx['edge'].shape[1],
                           batch1024_forward_backward_wall_s=float(np.median(costs[1:])),loss=float(loss.detach()),optimizer_steps=0,
                           finite_body_VJP=True,node_gradient_norm=float(model.nodes[0].weight.grad.norm())))
    # Constant branch must be identical when the measured candidate arrays are destroyed.
    damaged={k:v.copy() for k,v in x.items()};damaged['node'][:]=77;damaged['meta'][:]=-12
    for k,v in constant_branch(x).items():np.testing.assert_array_equal(v,constant_branch(damaged)[k])
    # Explicitly test empty and unavailable states, including all-masked pooling backward.
    synthetic={k:v[:2].copy() for k,v in x.items()};synthetic['node_mask'][:]=False;synthetic['edge_mask'][:]=False
    synthetic['meta']=np.array([[1,1,0,0],[0,0,0,0]],np.float32)
    model.zero_grad(set_to_none=True);v=model(**tensors(synthetic,'cuda'));v.sum().backward()
    assert torch.isfinite(v).all() and all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None)
    save('model_QA.json',dict(passed=True,unique_incoming=40,new_fits=0,optimizer_steps=0,checks=checks,
          permutation=invariance,control_has_no_new_information=True,empty_and_unavailable_finite=True,GPU=torch.cuda.get_device_name(),**cost(start)))
    print((OUT/'model_QA.json').read_text(),flush=True)


def freeze():
    q=json.loads((OUT/'model_QA.json').read_text());e=json.loads((OUT/'QA_extraction.json').read_text());assert q['passed'] and e['passed']
    perf=json.loads((OUT/'QA_performance.json').read_text());available=[p for p in perf if p['available_N']]
    payload=sum(p['payload_CPU_s'] for p in available)/sum(p['available_N'] for p in available)
    fixed=sum(p['CPU_s']-p['payload_CPU_s'] for p in available)/len(available)
    sources=json.loads((OUT/'sources.json').read_text());m=arrays(CACHE/'manifest.npz');n=sum(sources[i]['file_exists'] for i in m['source'])
    extract_projection=2*(payload*n+fixed*sum(s['file_exists'] for s in sources))+300
    fit_projection=max(r['batch1024_forward_backward_wall_s'] for r in q['checks'])*46*300*2*5+180
    passed=extract_projection+2000<21600 and fit_projection<7200
    save('admission.json',dict(passed=bool(passed),QA_unique_incoming=40,extraction_projected_CPU_s=extract_projection,
         mean_QA_payload_CPU_s=payload,mean_QA_fixed_source_CPU_s=fixed,extraction_projection='2*(per_payload_CPU*expected_available_rows + per_file_fixed_CPU*available_files)+300; not a measured guarantee',
         GPU_projected_wall_s=fit_projection,GPU_projection='slowest local 1024 F/B *46*300*2*5 +180; no optimizer trial',reserved_other_CPU_s=2000,stage_CPU_cap_s=21600,GPU_wall_cap_s=7200))
    assert passed,'Projected resources do not qualify; keep all identities, do not start fits or test payload'
    save('protocol.json',dict(stage=96,seed=SEED,cells=['A','B'],new_fits_exactly=2,frozen_before_test_payload=True,
         node_features=NODE_NAMES,edge_features=EDGE_NAMES,summary='original stage94 C typed62/train-only state,127 dimensions',
         node_transform=node_kinds(),edge_transform=['log1p']*4+['identity'],new_scales='train-only medianabs then transformed median/IQR; no clipping; separate missing masks',
         architecture='nodes44->32SiLU->32SiLU,mean/max/leading; edges10->16SiLU->16SiLU,mean/max; summary127+96+32+4->64SiLU->64SiLU->1',
         parameters=q['checks'][0]['parameters'],event_meta=['available','available_and_empty','train_standardized_log1p_count','has_edges'],
         control='A fixed one-node zero dummy/validmask, zero masked edge, fixedmeta[1,0,0,0]; no true count/availability/padding information',
         candidate='B all candidates sorted finite pz0 decreasing/stable original index; all leading edges; no hitSet/truth/truncation/dedup',
         loss='incomingweighted logMSE',optimizer='Adam lr.001/default betas/no decay/clip10',batch=1024,max_epochs=300,validation_every=5,patience=30,
         checkpoint='strict minimum original stage94 cal_select weighted pointMSE every5; single seed, no extra candidates',
         postprocessing='one original stage94 cal_post weighted mean(logtruth-point) offset per model; raw and shifted both reported',
         test='candidate payload after this protocol; new truth/prediction/stratum diagnostics only after both fits and offsets frozen',
         roles='original46575/11612/13189,17657quarantine excluded; all1016K,missing21/6/5 retained',
         limits=dict(CPU_s=21600,GPU_task_wall_s=7200,GPU_concurrency=1,retained_bytes=20000000),
         inference_target='point logE only; no new density/PIT/coverage or neutrino-energy oracle',model_promotion=False))
    print((OUT/'admission.json').read_text(),flush=True)


def fit(d,x,cell,part):
    start=time.perf_counter(),time.process_time();y=np.log(d['truth_E_GeV']);tr=np.flatnonzero(d['role']==1);cal=np.flatnonzero(d['role']==2)
    i=np.searchsorted(part['row'],d['row'][cal]);np.testing.assert_array_equal(part['row'][i],d['row'][cal])
    val=cal[part['subrole'][i]==1];vw=part['weight'][i][part['subrole'][i]==1]
    center=float(np.average(y[tr],weights=d['weight'][tr]));torch.manual_seed(SEED);torch.cuda.manual_seed_all(SEED)
    model=CandidateModel(center).cuda();opt=torch.optim.Adam(model.parameters(),lr=.001)
    xx=tensors(x,'cuda');yt=torch.tensor(y,dtype=torch.float32,device='cuda');wt=torch.tensor(d['weight'],dtype=torch.float32,device='cuda');wv=torch.tensor(vw,dtype=torch.float32,device='cuda')
    best=float('inf');best_epoch=0;best_state=None;history=[];rng=np.random.default_rng(SEED);steps=0
    torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize()
    for epoch in range(1,301):
        model.train();total=0.;den=0.
        # One seeded permutation per epoch, identical across the two cells.
        order=rng.permutation(len(tr))
        for j in range(0,len(tr),1024):
            index=tr[order[j:j+1024]];opt.zero_grad(set_to_none=True)
            pred=model(**take(xx,index));loss=((pred-yt[index]).square()*wt[index]).sum()/wt[index].sum()
            assert torch.isfinite(loss);loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),10,error_if_nonfinite=True);opt.step();steps+=1
            total+=float(loss.detach())*float(wt[index].sum());den+=float(wt[index].sum())
        if epoch%5==0:
            model.eval()
            with torch.no_grad():
                p=model(**take(xx,val));score=float(((p-yt[val]).square()*wv).sum()/wv.sum())
            history.append(dict(epoch=epoch,train_logMSE=total/den,cal_select_logMSE=score,**cost(start)))
            if score<best:best=score;best_epoch=epoch;best_state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
            table(f'learning_{cell}.tsv',history)
            if epoch-best_epoch>=30:break
    model.load_state_dict(best_state);model.eval();torch.cuda.synchronize()
    stats=dict(cell=cell,seed=SEED,epochs=epoch,best_epoch=best_epoch,optimizer_steps=steps,
               parameters=sum(p.numel() for p in model.parameters()),GPU_peak_allocated_MiB=torch.cuda.max_memory_allocated()/1024**2,**cost(start))
    torch.save(dict(state_dict=best_state,cell=cell,seed=SEED,center=center),ART/f'{cell}.pt')
    save(f'fit_{cell}.json',stats);print(json.dumps(stats),flush=True)
    with torch.no_grad():pred=np.concatenate([model(**take(xx,ii)).cpu().numpy() for ii in np.array_split(np.arange(len(y)),math.ceil(len(y)/2048))])
    del xx,yt,wt,wv;torch.cuda.empty_cache()
    return model,pred


def worker():
    start=time.perf_counter(),time.process_time();torch.set_num_threads(1);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    protocol=json.loads((OUT/'protocol.json').read_text());assert protocol['frozen_before_test_payload'] and protocol['new_fits_exactly']==2
    ART.mkdir(parents=True,exist_ok=True);assert not (ART/'started.txt').exists()
    (ART/'started.txt').write_text('stage96 exactly two preregistered fits\n')
    split=arrays(REPO/'ntuples/energy_ml_stage87/split.npz');tc=np.flatnonzero(np.isin(split['role'],[1,2]));c=arrays(CACHE/'candidates.npz')
    d=reconstruct(tc);x,state=input_arrays(d,subset(c,tc));save('preprocessing.json',state)
    part=arrays(REPO/'ntuples/energy_ml_stage94/cal_partition.npz');cal=np.flatnonzero(d['role']==2);ip=np.searchsorted(part['row'],d['row'][cal]);post=cal[part['subrole'][ip]==2];pw=part['weight'][ip][part['subrole'][ip]==2]
    models={};preds={};offsets=[]
    for cell in ['A','B']:
        model,p=fit(d,constant_branch(x) if cell=='A' else x,cell,part);models[cell]=model;preds[cell]=p
        delta=float(np.average(np.log(d['truth_E_GeV'][post])-p[post],weights=pw));offsets.append(dict(cell=cell,offset_logE=delta,N=len(post),incoming_weight_sum=float(pw.sum())))
    table('offsets.tsv',offsets);save('before_test.json',dict(two_fits_completed=True,offsets_frozen=True,new_test_predictions=0,seed=SEED,new_fits=2))
    test=np.flatnonzero(split['role']==3);dt=reconstruct(test);xt,_=input_arrays(dt,subset(c,test),state)
    predictions={};allrows=np.r_[tc,test];order=np.argsort(allrows)
    for cell in ['A','B']:
        tx=tensors(constant_branch(xt) if cell=='A' else xt,'cuda');model=models[cell]
        with torch.no_grad():pt=np.concatenate([model(**take(tx,ii)).cpu().numpy() for ii in np.array_split(np.arange(len(test)),math.ceil(len(test)/2048))])
        predictions[cell+'_raw']=np.r_[preds[cell],pt][order].astype(float)
        delta=next(r['offset_logE'] for r in offsets if r['cell']==cell);predictions[cell+'_cal']=predictions[cell+'_raw']+delta
    np.savez_compressed(ART/'predictions.npz',row=allrows[order],**predictions)
    save('worker_completion.json',dict(passed=True,new_fits=2,seed=SEED,train_N=46575,cal_N=11612,test_N=13189,
         cal_offsets_before_test=True,torch_threads=torch.get_num_threads(),GPU=torch.cuda.get_device_name(),**cost(start)))
    print((OUT/'worker_completion.json').read_text(),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['qa','freeze','worker']);a=p.parse_args()
    {'qa':qa,'freeze':freeze,'worker':worker}[a.action]()
