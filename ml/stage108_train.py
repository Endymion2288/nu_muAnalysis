"""Exactly one masked pretraining run and three preregistered energy fits."""
import argparse
import json
import math
import time

import numpy as np
import torch

from stage106_geometry import ROOT,SEED,arrays,cost
import stage106_geometry as geometry
from stage107_device_data import DevicePointData
OUT=ROOT/'workbook/stage108_energy_ml'
CACHE=ROOT/'ntuples/energy_ml_stage108'
geometry.OUT=OUT
save=geometry.save
table=geometry.table
from stage106_model import PointData,initialized,settings
from retrain_accurate_posterior import reconstruct
from compare_energy_architectures import representation

ART=ROOT/'ml/artifacts/stage108'


def inputs(prefix):
    c=arrays(CACHE/(prefix+'_coordinates.npz'))
    d=reconstruct(c['row'])
    np.testing.assert_array_equal(c['role'],d['role'])
    s=json.loads((ROOT/'workbook/stage94_energy_ml/preprocessing.json').read_text())['C']
    summary,_,_=representation(d,'C',s)
    return d,PointData(c,summary,d['key_id'])


def optimize_epoch(model,data,indices,y,w,opt,rng,epoch=None):
    order=rng.permutation(indices);num=den=0.;steps=0
    for begin in range(0,len(order),256):
        batch=order[begin:begin+256];weightden=float(w[batch].sum())
        opt.zero_grad(set_to_none=True)
        for ids in data.groups(batch,epoch):
            x,target=data.pack(ids,epoch)
            pred=model(**x);weight=torch.as_tensor(w[ids],dtype=torch.float32,device='cuda')
            if epoch is None:
                target=torch.as_tensor(y[ids],dtype=torch.float32,device='cuda')
                values=(pred-target).square()
            else:
                values=(pred-target*pred.log()).mean(1)
            value=(values*weight).sum()/weightden
            assert torch.isfinite(value)
            value.backward();num+=float((values.detach()*weight).sum());den+=float(weight.sum())
        torch.nn.utils.clip_grad_norm_(model.parameters(),10,error_if_nonfinite=True)
        opt.step();steps+=1
    return num/den,steps


def predict(model,data,indices,device='cuda'):
    out=np.empty(len(data.base.key),np.float64)
    with torch.no_grad():
        for begin in range(0,len(indices),256):
            for ids in data.groups(indices[begin:begin+256]):
                x,_=data.pack(ids);out[ids]=model(**x).cpu().numpy()
    return out


def adapter_QA(d,data):
    plan=json.loads((ROOT/'workbook/stage105_energy_ml/identities.json').read_text())
    rows=np.array(sorted(r['row'] for r in plan['records']))
    ids=np.searchsorted(d['row'],rows);np.testing.assert_array_equal(d['row'][ids],rows)
    model=initialized('B');ref=initialized('B')
    with torch.no_grad():
        for m in [model,ref]:m.head.weight.copy_(torch.linspace(-.01,.01,64,device='cuda')[None,:])
    class NoUpdate:
        def zero_grad(self,set_to_none=True):model.zero_grad(set_to_none=set_to_none)
        def step(self):pass
    original={k:v.detach().clone() for k,v in model.state_dict().items()}
    value,steps=optimize_epoch(model,data,ids,np.log(d['truth_E_GeV']),d['weight'],NoUpdate(),np.random.default_rng(SEED))
    den=float(d['weight'][ids].sum())
    for group in data.base.microbatches(ids):
        ix,x=data.base.pack(group,'cuda');pred=ref(**x)
        w=torch.as_tensor(d['weight'][ix],dtype=torch.float32,device='cuda')
        target=torch.as_tensor(np.log(d['truth_E_GeV'][ix]),dtype=torch.float32,device='cuda')
        ((w*(pred-target).square()).sum()/den).backward()
    torch.nn.utils.clip_grad_norm_(ref.parameters(),10,error_if_nonfinite=True)
    maximum=0.
    for a,b in zip(model.parameters(),ref.parameters()):
        assert (a.grad is None)==(b.grad is None)
        if a.grad is not None:
            torch.testing.assert_close(a.grad,b.grad,rtol=1e-5,atol=3e-6)
            maximum=max(maximum,float(abs(a.grad-b.grad).max()))
    for k,v in model.state_dict().items():torch.testing.assert_close(v,original[k],rtol=0,atol=0)
    path=ART/'adapter_QA.tmp.pt';torch.save(original,path)
    loaded=torch.load(path,map_location='cuda',weights_only=True)
    for k,v in original.items():torch.testing.assert_close(v,loaded[k],rtol=0,atol=0)
    path.unlink()
    before=predict(model,data,ids);ref.load_state_dict(loaded);after=predict(ref,data,ids)
    np.testing.assert_array_equal(before[ids],after[ids])
    report=dict(passed=True,rows=len(ids),real_weights=True,optimizer_steps=0,no_update_adapter_calls=steps,
        clipped_gradient_max_abs=maximum,checkpoint_and_prediction_reload_exact=True,finite_loss=bool(np.isfinite(value)))
    save('adapter_QA.json',report);print('adapter_QA',json.dumps(report),flush=True)
    del model,ref,loaded,original


def audit_full_inputs(d,data,cold_cost):
    tick=time.perf_counter(),time.process_time()
    tr=np.flatnonzero(d['role']==1);counts=data.counts;edgecounts=data.edgecounts
    qa=json.loads((ROOT/'workbook/stage107_energy_ml/model_QA.json').read_text())
    old=json.loads((ROOT/'workbook/stage105_energy_ml/complete.json').read_text())
    nodefactor=float(counts[tr].sum()/(old['total_points']/40*len(tr)))
    edgefactor=float(edgecounts[tr].sum()/(old['total_edges']/40*len(tr)))
    factor=max(1.,nodefactor,edgefactor);batchfactor=math.ceil(46575/256)*620*3
    extraction=json.loads((OUT/'time_train_extract.json').read_text())
    oldCPU=36.048710;oldGPU=19.
    gpu=max(p['forward_backward_wall_s'] for p in qa['profile'])*batchfactor*factor+600+3*cold_cost['wall_s']+oldGPU
    host=max(p['CPU_s'] for p in qa['profile'])*batchfactor*factor+8118.7208401971475+3*cold_cost['CPU_s']+oldCPU+extraction['CPU_s']
    largest=int(np.argmax(counts+edgecounts));model=initialized('B')
    with torch.no_grad():model.head.weight.fill_(.001)
    x,_=data.pack([largest]);z=model(**x);z.square().mean().backward();torch.cuda.synchronize()
    peak=torch.cuda.max_memory_allocated()/1024**2;deviceMiB=torch.cuda.get_device_properties(0).total_memory/1024**2
    del model,x,z;torch.cuda.empty_cache()
    passed=gpu<=10800 and host<=21600 and peak<=.75*deviceMiB
    report=dict(passed=bool(passed),train_cal_records=len(counts),train_records=len(tr),
        role_records={str(r):int((d['role']==r).sum()) for r in [1,2]},
        available=int(data.base.c['available'].sum()),missing=int((~data.base.c['available']).sum()),
        original_points=int(np.diff(data.base.c['offsets']).sum()),effective_points=int(counts.sum()),directed_edges=int(edgecounts.sum()),
        max_points=int(counts.max()),max_edges=int(edgecounts.max()),largest_QA_row=int(d['row'][largest]),
        resident_plus_largest_event_GPU_peak_MiB=peak,node_factor_over_QA=nodefactor,edge_factor_over_QA=edgefactor,
        projected_GPU_task_wall_s=gpu,projected_total_CPU_s=host,cold_cost=cold_cost,
        GPU_cap_s=10800,CPU_cap_s=21600,test_payload_records=0,optimizer_steps=0,**cost(tick))
    save('full_input_admission.json',report);print('full_input_admission',json.dumps(report),flush=True)
    assert passed,'Full input costs/memory not admitted; no optimizer permitted'
    adapter_QA(d,data)


def fit():
    start=time.perf_counter(),time.process_time();settings()
    assert json.loads((OUT/'admission.json').read_text())['passed']
    assert not (OUT/'optimizer_started.json').exists()
    cold=time.perf_counter(),time.process_time()
    d,base=inputs('train_cal');assert len(d['row'])==58187 and not np.any(d['role']==3)
    torch.cuda.reset_peak_memory_stats()
    data=DevicePointData(base,d['role']);data.prepare_schedules(range(1,21));torch.cuda.synchronize()
    audit_full_inputs(d,data,cost(cold))
    tr=np.flatnonzero(d['role']==1);cal=np.flatnonzero(d['role']==2)
    extraction=json.loads((OUT/'time_train_extract.json').read_text())
    CPU_remaining=21600-36.048710-extraction['CPU_s']-1000
    def runtime_guard():
        assert time.perf_counter()-start[0]<9900 and time.process_time()-start[1]<CPU_remaining,'Cumulative budget stop'
    part=arrays(ROOT/'ntuples/energy_ml_stage94/cal_partition.npz')
    ii=np.searchsorted(part['row'],d['row'][cal]);np.testing.assert_array_equal(part['row'][ii],d['row'][cal])
    select=cal[part['subrole'][ii]==1];post=cal[part['subrole'][ii]==2]
    sw=part['weight'][ii][part['subrole'][ii]==1];pw=part['weight'][ii][part['subrole'][ii]==2]
    assert len(select)==5443 and len(post)==5746
    y=np.log(d['truth_E_GeV']);w=d['weight'];center=float(np.average(y[tr],weights=w[tr]))
    save('optimizer_started.json',dict(seed=SEED,supervised_fits=3,pretraining_runs=1,test_payload_records=0))
    pre=initialized('B',center);opt=torch.optim.Adam(pre.parameters(),lr=.001)
    indices=tr[data.base.c['available'][tr]];rng=np.random.default_rng(SEED)
    history=[];psteps=0;pretick=time.perf_counter(),time.process_time()
    for epoch in range(1,21):
        runtime_guard()
        value,steps=optimize_epoch(pre,data,indices,None,w,opt,rng,epoch)
        psteps+=steps;history.append(dict(epoch=epoch,train_count_Poisson_NLL_without_constant=value,optimizer_steps=psteps,**cost(pretick)))
        table('learning_pretraining.tsv',history)
        print('pretraining',epoch,'loss',value,flush=True)
    pretrained={k:v.detach().cpu().clone() for k,v in pre.state_dict().items() if k.startswith(('point.','message.','update.'))}
    save('pretraining.json',dict(completed=True,epochs=20,optimizer_steps=psteps,
        train_available_records=len(indices),cal_test_records=0,seed=SEED,**cost(pretick)))
    del pre,opt;torch.cuda.empty_cache()
    predictions={'row':d['row'],'geometry_available':data.base.c['available'],
        'point_count':np.diff(data.base.c['offsets']).astype(np.int32)};offsets=[]
    for cell in ['A','B','C']:
        model=initialized(cell,center)
        if cell=='C':
            state=model.state_dict();state.update(pretrained);model.load_state_dict(state)
        opt=torch.optim.Adam(model.parameters(),lr=.001);rng=np.random.default_rng(SEED)
        best=float('inf');best_epoch=0;best_state=None;history=[];total_steps=0
        tick=time.perf_counter(),time.process_time();torch.cuda.reset_peak_memory_stats()
        for epoch in range(1,201):
            model.train();value,steps=optimize_epoch(model,data,tr,y,w,opt,rng)
            total_steps+=steps
            if epoch%5==0:
                model.eval();p=predict(model,data,select)
                score=float(np.average((p[select]-y[select])**2,weights=sw))
                assert np.isfinite(score)
                history.append(dict(epoch=epoch,train_logMSE=value,cal_select_logMSE=score,optimizer_steps=total_steps,**cost(tick)))
                table(f'learning_{cell}.tsv',history)
                if score<best:
                    best=score;best_epoch=epoch;best_state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
                print(cell,epoch,'cal_select',score,'best',best_epoch,flush=True)
                if epoch-best_epoch>=30:break
            # Hard finite wall bound, never resume partial optimizers automatically.
            runtime_guard()
        model.load_state_dict(best_state);model.eval()
        p=predict(model,data,np.arange(len(y)))
        delta=float(np.average(y[post]-p[post],weights=pw))
        predictions[cell+'_raw']=p;predictions[cell+'_cal']=p+delta
        offsets.append(dict(cell=cell,offset_logE=delta,cal_post_records=len(post)))
        torch.save(dict(state=best_state,center=center,cell=cell,seed=SEED),ART/f'{cell}.pt')
        check=torch.load(ART/f'{cell}.pt',map_location='cpu',weights_only=True)
        for k in best_state:torch.testing.assert_close(check['state'][k],best_state[k],rtol=0,atol=0)
        save(f'fit_{cell}.json',dict(completed=True,cell=cell,seed=SEED,epochs=epoch,best_epoch=best_epoch,
             optimizer_steps=total_steps,parameters=sum(p.numel() for p in model.parameters()),
             GPU_peak_allocated_MiB=torch.cuda.max_memory_allocated()/1024**2,**cost(tick)))
        del model,opt;torch.cuda.empty_cache()
    table('offsets.tsv',offsets)
    temporary=ART/'train_cal_predictions.tmp.npz';np.savez_compressed(temporary,**predictions)
    reload=arrays(temporary)
    for k,v in predictions.items():np.testing.assert_array_equal(v,reload[k])
    temporary.replace(ART/'train_cal_predictions.npz')
    save('before_test.json',dict(checkpoints_and_offsets_frozen=True,new_fits=3,
        pretraining_runs=1,pretraining_epochs=20,seed=SEED,new_test_predictions=0,
        test_payload_records=0,train_cal_records=len(y),offsets=offsets,**cost(start)))


def infer():
    start=time.perf_counter(),time.process_time();settings()
    before=json.loads((OUT/'before_test.json').read_text());assert before['checkpoints_and_offsets_frozen']
    d,base=inputs('test');assert len(d['row'])==13189 and np.all(d['role']==3)
    data=DevicePointData(base,d['role'])
    old=arrays(ART/'train_cal_predictions.npz');pred={'row':np.r_[old['row'],d['row']],
        'geometry_available':np.r_[old['geometry_available'],data.base.c['available']],
        'point_count':np.r_[old['point_count'],np.diff(data.base.c['offsets']).astype(np.int32)]}
    for cell in ['A','B','C']:
        c=torch.load(ART/f'{cell}.pt',map_location='cpu',weights_only=True)
        model=initialized(cell,c['center']);model.load_state_dict(c['state']);model.eval()
        p=predict(model,data,np.arange(len(d['row'])))
        delta=next(r['offset_logE'] for r in before['offsets'] if r['cell']==cell)
        pred[cell+'_raw']=np.r_[old[cell+'_raw'],p]
        pred[cell+'_cal']=np.r_[old[cell+'_cal'],p+delta]
        del model;torch.cuda.empty_cache()
    order=np.argsort(pred['row']);pred={k:v[order] for k,v in pred.items()}
    assert len(pred['row'])==71376 and all(np.isfinite(v).all() for k,v in pred.items())
    temporary=ART/'predictions.tmp.npz';np.savez_compressed(temporary,**pred)
    reload=arrays(temporary)
    for k,v in pred.items():np.testing.assert_array_equal(v,reload[k])
    temporary.replace(ART/'predictions.npz')
    save('inference.json',dict(completed=True,records=71376,test_records=13189,
         new_fits=0,previous_fits=3,checkpoints_frozen_before_test=True,**cost(start)))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['fit','infer']);a=p.parse_args()
    fit() if a.mode=='fit' else infer()
