"""Stage97: two fixed fits adding a constant or paired candidate-edge message.

Input transforms and point-fitting loop are inherited verbatim from Stage96;
this module owns its outputs and uses the frozen Stage96 train-only state.
"""
import argparse
import json
import math
import time

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from prepare_candidate_ablation import REPO, CACHE, arrays, cost
from train_candidate_ablation import input_arrays, subset, tensors, take, CandidateModel
from retrain_accurate_posterior import reconstruct

OUT = REPO / 'workbook/stage97_energy_ml'
ART = REPO / 'ml/artifacts/stage97'
SEED = 2026110497


def save(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def table(name, rows):
    import csv
    with (OUT/name).open('w') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter='\t', lineterminator='\n')
        w.writeheader(); w.writerows(rows)


def state():
    return json.loads((REPO/'workbook/stage96_energy_ml/preprocessing.json').read_text())


class JointModel(nn.Module):
    pool = staticmethod(CandidateModel.pool)

    def __init__(self, center=6., cell='B'):
        super().__init__()
        assert cell in ['A', 'B']
        self.cell = cell
        self.nodes = nn.Sequential(nn.Linear(44,32),nn.SiLU(),nn.Linear(32,32),nn.SiLU())
        self.edges = nn.Sequential(nn.Linear(10,16),nn.SiLU(),nn.Linear(16,16),nn.SiLU())
        self.messages = nn.Sequential(nn.Linear(80,32),nn.SiLU(),nn.Linear(32,32),nn.SiLU())
        self.body = nn.Sequential(nn.Linear(259+64,64),nn.SiLU(),nn.Linear(64,64),nn.SiLU())
        self.head = nn.Linear(64,1)
        nn.init.zeros_(self.head.weight); nn.init.constant_(self.head.bias,center)

    def joint(self, h, e, edge_mask):
        if self.cell == 'A':
            # Fixed one valid dummy, independent of true count/pairing/padding.
            constant = self.messages(h.new_zeros((1,1,80)))
            return torch.cat([constant[:,0],constant[:,0]],1).expand(len(h),-1)
        other = h[:,1:]
        if other.shape[1] < e.shape[1]:
            other = F.pad(other,(0,0,0,e.shape[1]-other.shape[1]))
        assert other.shape[1] == e.shape[1]
        leading = h[:,0,None,:].expand(-1,e.shape[1],-1)
        messages = self.messages(torch.cat([leading,other,e],2))
        mean, maximum = self.pool(messages,edge_mask)
        return torch.cat([mean,maximum],1)

    def forward(self, summary, node, node_mask, edge, edge_mask, meta):
        h = self.nodes(node); e = self.edges(edge)
        a,b = self.pool(h,node_mask); u,v = self.pool(e,edge_mask)
        lead = h[:,0]*node_mask[:,0,None]
        joint = self.joint(h,e,edge_mask)
        return self.head(self.body(torch.cat([summary,a,b,lead,u,v,meta,joint],1))).squeeze(1)


def settings():
    torch.set_num_threads(1)
    torch.backends.cuda.matmul.allow_tf32=False
    torch.backends.cudnn.allow_tf32=False


def qa():
    start = time.perf_counter(),time.process_time(); settings()
    c = arrays(CACHE/'QA_candidates.npz'); d = reconstruct(c['row'])
    assert len(d['row']) == len(np.unique(d['key_id'])) == 40
    assert np.isin(d['role'],[1,2]).all()
    x,_ = input_arrays(d,c,state())
    # Max padding already certified by Stage96; inspect counts only, no test risk.
    validation = json.loads((REPO/'workbook/stage96_energy_ml/input_validation.json').read_text())
    for name,mask,size in [('node','node_mask',validation['max_candidates']),('edge','edge_mask',validation['max_edges'])]:
        pad=size-x[name].shape[1]
        x[name]=np.pad(x[name],((0,0),(0,pad),(0,0)))
        x[mask]=np.pad(x[mask],((0,0),(0,pad)))
    assert np.array_equal(x['edge_mask'],x['node_mask'][:,1:])
    checks=[]; initial=[]; predictions={}
    for cell in ['A','B']:
        for device in ['cpu','cuda']:
            torch.manual_seed(SEED); model=JointModel(cell=cell).to(device)
            if device=='cpu':initial.append({k:v.detach().clone() for k,v in model.state_dict().items()})
            with torch.no_grad():model.head.weight.copy_(torch.linspace(-.03,.03,64,device=device)[None,:])
            xt=tensors(x,device); y=torch.tensor(np.log(d['truth_E_GeV']),dtype=torch.float32,device=device)
            w=torch.tensor(d['weight'],dtype=torch.float32,device=device)
            prediction=model(**xt);predictions[cell,device]=prediction.detach().cpu().numpy()
            loss=((prediction-y).square()*w).sum()/w.sum(); loss.backward()
            assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())
            gradient=float(model.messages[0].weight.grad.norm())
            changed={k:v.clone() for k,v in xt.items()}
            changed['node'][:,1:]=xt['node'][:,1:].flip(1)
            changed['node_mask'][:,1:]=xt['node_mask'][:,1:].flip(1)
            changed['edge']=xt['edge'].flip(1); changed['edge_mask']=xt['edge_mask'].flip(1)
            with torch.no_grad():delta=float(abs(model(**xt)-model(**changed)).max())
            assert delta<3e-6
            synthetic={k:v[:2].clone() for k,v in xt.items()}
            synthetic['node_mask'][:]=False; synthetic['edge_mask'][:]=False
            synthetic['meta']=torch.tensor([[1,1,0,0],[0,0,0,0]],device=device,dtype=torch.float32)
            model.zero_grad(set_to_none=True); z=model(**synthetic); z.sum().backward()
            assert torch.isfinite(z).all() and all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None)
            # Algebraic pairing probe from these same40 transformed values only.
            nv=xt['node'][xt['node_mask']]; ev=xt['edge'][xt['edge_mask']]
            assert len(ev)>=2
            sn=torch.stack([nv[0],nv[1],nv[-1]])[None,:]
            se=torch.stack([ev[0],ev[-1]])[None,:]
            h=model.nodes(sn);e=model.edges(se);mask=torch.ones((1,2),dtype=torch.bool,device=device)
            with torch.no_grad():
                j1=model.joint(h,e,mask); j2=model.joint(h,e.flip(1),mask)
                pairing=float(abs(j1-j2).max())
            assert pairing==0 if cell=='A' else pairing>1e-8
            # A joint output identical under changed counts/shape/content.
            if cell=='A':
                with torch.no_grad():
                    other=model.joint(h[:,:1],e[:,:1]*77,mask[:,:1]*False)
                torch.testing.assert_close(j1,other,rtol=0,atol=0)
            batch={k:np.tile(v,(26,)+(1,)*(v.ndim-1))[:1024] for k,v in x.items()}
            values=[]; cpu=[]; transfer=[]
            if device=='cuda':torch.cuda.reset_peak_memory_stats()
            for repeat in range(4):
                model.zero_grad(set_to_none=True)
                if device=='cuda':torch.cuda.synchronize()
                tick=time.perf_counter(),time.process_time()
                tx=tensors(batch,device)
                if device=='cuda':torch.cuda.synchronize()
                moved=time.perf_counter()-tick[0]
                z=model(**tx); z.square().mean().backward()
                # Include result copy and synchronization in timing.
                result=z.detach().cpu().numpy()
                if device=='cuda':torch.cuda.synchronize()
                assert np.isfinite(result).all()
                values.append(time.perf_counter()-tick[0]);cpu.append(time.process_time()-tick[1]);transfer.append(moved)
            checks.append(dict(cell=cell,device=device,parameters=sum(p.numel() for p in model.parameters()),
                 node_max=10,edge_max=9,batch=1024,optimizer_steps=0,finite_VJP=True,
                 message_input_weight_gradient_norm=gradient,permutation_max_logE_delta=delta,
                 synthetic_pairing_max_joint_delta=pairing,
                 end_to_end_forward_backward_wall_s=float(np.median(values[1:])),
                 end_to_end_CPU_s=float(np.median(cpu[1:])),input_transfer_wall_s=float(np.median(transfer[1:])),
                 GPU_peak_allocated_MiB=torch.cuda.max_memory_allocated()/1024**2 if device=='cuda' else None))
    for name in initial[0]:torch.testing.assert_close(initial[0][name],initial[1][name],rtol=0,atol=0)
    agreement=max(float(abs(predictions[cell,'cpu']-predictions[cell,'cuda']).max()) for cell in ['A','B'])
    assert agreement<3e-6
    save('model_QA.json',dict(CPU_GPU_max_logE_difference=agreement,passed=True,identities=40,original_train_cal_only=True,new_fits=0,optimizer_steps=0,
         checks=checks,same_initialization=True,pairing_probe='Synthetic three-node/two-edge tensor made solely from the same40; no physical risk or new events',
         GPU=torch.cuda.get_device_name(),preprocessing='Frozen Stage96 train-only state; no refit',**cost(start)))
    print((OUT/'model_QA.json').read_text(),flush=True)


def freeze():
    q=json.loads((OUT/'model_QA.json').read_text());assert q['passed']
    gpu=max(v['end_to_end_forward_backward_wall_s'] for v in q['checks'] if v['device']=='cuda')
    projection=gpu*46*300*2*5+180
    cpu_projection=projection+1000
    assert projection<3600 and cpu_projection<7200
    parameters=q['checks'][0]['parameters']
    assert all(v['parameters']==parameters for v in q['checks'])
    save('admission.json',dict(passed=True,GPU_projected_wall_s=projection,CPU_projected_s=cpu_projection,
         projection_rule='slowest local padded1024 end-to-end GPU F/B*46*300*2*5+180; reserve1000CPU for evaluation/QA; estimate not guarantee',
         CPU_cap_s=7200,GPU_task_wall_cap_s=3600,retained_cap_bytes=20000000))
    save('protocol.json',dict(stage=97,seed=SEED,new_fits_exactly=2,frozen_before_test_payload=True,
         architecture='Stage96 B real marginal nodes/edges/summary/meta in both cells; added80->32SiLU->32SiLU messages,mean/max64;323->64SiLU->64SiLU->1',
         parameters=parameters,A='constant one-dummy added-message branch; all original marginal inputs retained',
         B='leading32+corresponding secondary32+edge16, then masked message pool; no edges ->0',
         capacity_limit='same declared architecture is not identical effective function capacity',
         input='same Stage96 cache, no PHYS/truth/hitSet/new information',preprocessing='byte-identical Stage96 frozen train-only node/edge/count/summary state',
         loss='incomingweighted logMSE',optimizer='Adam lr.001/default betas/no decay/clip10',batch=1024,
         max_epochs=300,validation_every=5,patience=30,checkpoint='strict minimum original Stage94 cal_select weighted pointMSE',
         postprocessing='one original cal_post weighted mean log-offset per cell; raw/offset reported',
         roles=dict(train=46575,cal=11612,test=13189,quarantine=17657),additional_K_retained=1016,
         constraints='pz0-only first-power momentum; px/py/qOverP/bends allowed; raw11/status; typed NaN and legitimate signed values',
         test='new predictions only after both fits and offsets fixed; developed pool, not blind',
         limits=dict(CPU_s=7200,GPU_task_wall_s=3600,GPU_concurrency=1,retained_bytes=20000000),
         evaluation='original8RMSE and total/positive/negative tail gates;500 component-incoming conditional draws; source95/systematics/retraining not covered',
         model_promotion=False))
    print((OUT/'admission.json').read_text(),flush=True)


def fit(d,x,cell,part):
    start=time.perf_counter(),time.process_time();y=np.log(d['truth_E_GeV']);tr=np.flatnonzero(d['role']==1);cal=np.flatnonzero(d['role']==2)
    i=np.searchsorted(part['row'],d['row'][cal]);np.testing.assert_array_equal(part['row'][i],d['row'][cal])
    val=cal[part['subrole'][i]==1];vw=part['weight'][i][part['subrole'][i]==1]
    center=float(np.average(y[tr],weights=d['weight'][tr]));torch.manual_seed(SEED);torch.cuda.manual_seed_all(SEED)
    model=JointModel(center,cell).cuda();opt=torch.optim.Adam(model.parameters(),lr=.001)
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
    (ART/'started.txt').write_text('stage97 exactly two preregistered fits\n')
    split=arrays(REPO/'ntuples/energy_ml_stage87/split.npz');tc=np.flatnonzero(np.isin(split['role'],[1,2]));c=arrays(CACHE/'candidates.npz')
    d=reconstruct(tc);x,preprocessing=input_arrays(d,subset(c,tc),state());save('preprocessing.json',preprocessing)
    part=arrays(REPO/'ntuples/energy_ml_stage94/cal_partition.npz');cal=np.flatnonzero(d['role']==2);ip=np.searchsorted(part['row'],d['row'][cal]);post=cal[part['subrole'][ip]==2];pw=part['weight'][ip][part['subrole'][ip]==2]
    models={};preds={};offsets=[]
    for cell in ['A','B']:
        model,p=fit(d,x,cell,part);models[cell]=model;preds[cell]=p
        delta=float(np.average(np.log(d['truth_E_GeV'][post])-p[post],weights=pw));offsets.append(dict(cell=cell,offset_logE=delta,N=len(post),incoming_weight_sum=float(pw.sum())))
    table('offsets.tsv',offsets);save('before_test.json',dict(two_fits_completed=True,offsets_frozen=True,new_test_predictions=0,seed=SEED,new_fits=2))
    test=np.flatnonzero(split['role']==3);dt=reconstruct(test);xt,_=input_arrays(dt,subset(c,test),preprocessing)
    predictions={};allrows=np.r_[tc,test];order=np.argsort(allrows)
    for cell in ['A','B']:
        tx=tensors(xt,'cuda');model=models[cell]
        with torch.no_grad():pt=np.concatenate([model(**take(tx,ii)).cpu().numpy() for ii in np.array_split(np.arange(len(test)),math.ceil(len(test)/2048))])
        predictions[cell+'_raw']=np.r_[preds[cell],pt][order].astype(float)
        delta=next(r['offset_logE'] for r in offsets if r['cell']==cell);predictions[cell+'_cal']=predictions[cell+'_raw']+delta
    np.savez_compressed(ART/'predictions.npz',row=allrows[order],**predictions)
    save('worker_completion.json',dict(passed=True,new_fits=2,seed=SEED,train_N=46575,cal_N=11612,test_N=13189,
         cal_offsets_before_test=True,torch_threads=torch.get_num_threads(),GPU=torch.cuda.get_device_name(),**cost(start)))
    print((OUT/'worker_completion.json').read_text(),flush=True)


def replay():
    settings()
    q=arrays(CACHE/'QA_candidates.npz');d=reconstruct(q['row'])
    assert len(d['row'])==40 and np.isin(d['role'],[1,2]).all()
    x,_=input_arrays(d,q,state())
    p=arrays(ART/'predictions.npz');ix=np.searchsorted(p['row'],d['row'])
    np.testing.assert_array_equal(p['row'][ix],d['row'])
    checks=[]
    for cell in ['A','B']:
        saved=torch.load(ART/f'{cell}.pt',map_location='cpu',weights_only=True)
        model=JointModel(saved['center'],cell).cuda();model.load_state_dict(saved['state_dict']);model.eval()
        with torch.no_grad():z=model(**tensors(x,'cuda')).cpu().numpy()
        delta=float(abs(z-p[cell+'_raw'][ix]).max());assert delta<3e-6
        checks.append(dict(cell=cell,max_logE_difference=delta))
    save('checkpoint_QA.json',dict(passed=True,identities=40,new_fits=0,new_test_predictions=0,checks=checks))
    print((OUT/'checkpoint_QA.json').read_text(),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['qa','freeze','worker','replay'])
    args=parser.parse_args();globals()[args.action]()
