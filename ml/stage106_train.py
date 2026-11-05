"""Exactly one masked pretraining run and three preregistered energy fits."""
import argparse
import json
import math
import time

import numpy as np
import torch

from stage106_geometry import ROOT,OUT,CACHE,SEED,arrays,save,table,cost
from stage106_model import PointData,initialized,settings,predict
from retrain_accurate_posterior import reconstruct
from compare_energy_architectures import representation

ART=ROOT/'ml/artifacts/stage106'


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
        for group in data.microbatches(batch,epoch):
            ids,x=data.pack(group,'cuda',epoch is not None)
            pred=model(**x);weight=torch.as_tensor(w[ids],dtype=torch.float32,device='cuda')
            if epoch is None:
                target=torch.as_tensor(y[ids],dtype=torch.float32,device='cuda')
                values=(pred-target).square()
            else:
                values=(pred-x['target']*pred.log()).mean(1)
            value=(values*weight).sum()/weightden
            assert torch.isfinite(value)
            value.backward();num+=float((values.detach()*weight).sum());den+=float(weight.sum())
        torch.nn.utils.clip_grad_norm_(model.parameters(),10,error_if_nonfinite=True)
        opt.step();steps+=1
    return num/den,steps


def audit_full_inputs(d,data):
    tick=time.perf_counter(),time.process_time()
    tr=np.flatnonzero(d['role']==1)
    counts=np.diff(data.c['offsets']);edgecounts=np.zeros(len(counts),np.int64)
    for i in range(len(counts)):edgecounts[i]=len(data.get(i)['edges'])
    q=json.loads((OUT/'model_QA.json').read_text());a=json.loads((OUT/'admission.json').read_text())
    # Actual full-role input counts only; never test geometry/energy risk.
    old=json.loads((ROOT/'workbook/stage105_energy_ml/complete.json').read_text())
    nodefactor=float(counts[tr].sum()/(old['total_points']/40*len(tr)))
    edgefactor=float(edgecounts[tr].sum()/(old['total_edges']/40*len(tr)))
    factor=max(1.,nodefactor,edgefactor)
    gpu_projection=(a['projected_GPU_task_wall_s']-600)*factor+600
    host_projection=a['projected_GPU_host_CPU_s']*factor+a['projected_extraction_plus_reserve_CPU_s']
    # Actual largest complete event forward/backward is a memory QA, no optimizer/risk.
    largest=int(np.argmax(counts+edgecounts))
    model=initialized('B');torch.cuda.reset_peak_memory_stats()
    with torch.no_grad():model.head.weight.fill_(.001)
    ids,x=data.pack([(largest,data.get(largest))],'cuda');z=model(**x);z.square().mean().backward();torch.cuda.synchronize()
    peak=torch.cuda.max_memory_allocated()/1024**2
    deviceMiB=torch.cuda.get_device_properties(0).total_memory/1024**2
    del model,x,z;torch.cuda.empty_cache()
    passed=gpu_projection<=7200 and host_projection<=21600 and peak<=.75*deviceMiB
    report=dict(passed=bool(passed),train_cal_records=len(counts),train_records=len(tr),
        role_records={str(r):int((d['role']==r).sum()) for r in [1,2]},
        available=int(data.c['available'].sum()),missing=int((~data.c['available']).sum()),
        original_points=int(counts.sum()),directed_edges=int(edgecounts.sum()),
        max_points=int(counts.max()),max_edges=int(edgecounts.max()),largest_QA_row=int(d['row'][largest]),
        largest_event_GPU_peak_MiB=peak,node_factor_over_QA=nodefactor,edge_factor_over_QA=edgefactor,
        projected_GPU_task_wall_s=gpu_projection,projected_total_CPU_s=host_projection,
        test_payload_records=0,optimizer_steps=0,**cost(tick))
    save('full_input_admission.json',report);print(json.dumps(report),flush=True)
    assert passed,'Full input costs/memory not admitted; no optimizer permitted'


def fit():
    start=time.perf_counter(),time.process_time();settings()
    assert json.loads((OUT/'admission.json').read_text())['passed']
    assert not (OUT/'optimizer_started.json').exists()
    d,data=inputs('train_cal');assert len(d['row'])==58187 and not np.any(d['role']==3)
    audit_full_inputs(d,data)
    tr=np.flatnonzero(d['role']==1);cal=np.flatnonzero(d['role']==2)
    part=arrays(ROOT/'ntuples/energy_ml_stage94/cal_partition.npz')
    ii=np.searchsorted(part['row'],d['row'][cal]);np.testing.assert_array_equal(part['row'][ii],d['row'][cal])
    select=cal[part['subrole'][ii]==1];post=cal[part['subrole'][ii]==2]
    sw=part['weight'][ii][part['subrole'][ii]==1];pw=part['weight'][ii][part['subrole'][ii]==2]
    assert len(select)==5443 and len(post)==5746
    y=np.log(d['truth_E_GeV']);w=d['weight'];center=float(np.average(y[tr],weights=w[tr]))
    save('optimizer_started.json',dict(seed=SEED,supervised_fits=3,pretraining_runs=1,test_payload_records=0))
    pre=initialized('B',center);opt=torch.optim.Adam(pre.parameters(),lr=.001)
    indices=tr[data.c['available'][tr]];rng=np.random.default_rng(SEED)
    history=[];psteps=0;pretick=time.perf_counter(),time.process_time()
    for epoch in range(1,21):
        value,steps=optimize_epoch(pre,data,indices,None,w,opt,rng,epoch)
        psteps+=steps;history.append(dict(epoch=epoch,train_count_Poisson_NLL_without_constant=value,optimizer_steps=psteps,**cost(pretick)))
        table('learning_pretraining.tsv',history)
        print('pretraining',epoch,'loss',value,flush=True)
    pretrained={k:v.detach().cpu().clone() for k,v in pre.state_dict().items() if k.startswith(('point.','message.','update.'))}
    save('pretraining.json',dict(completed=True,epochs=20,optimizer_steps=psteps,
        train_available_records=len(indices),cal_test_records=0,seed=SEED,**cost(pretick)))
    del pre,opt;torch.cuda.empty_cache()
    predictions={'row':d['row']};offsets=[]
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
            assert time.perf_counter()-start[0]<6700,'Training wall budget stop'
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
    table('offsets.tsv',offsets);np.savez_compressed(ART/'train_cal_predictions.npz',**predictions)
    save('before_test.json',dict(checkpoints_and_offsets_frozen=True,new_fits=3,
        pretraining_runs=1,pretraining_epochs=20,seed=SEED,new_test_predictions=0,
        test_payload_records=0,train_cal_records=len(y),offsets=offsets,**cost(start)))


def infer():
    start=time.perf_counter(),time.process_time();settings()
    before=json.loads((OUT/'before_test.json').read_text());assert before['checkpoints_and_offsets_frozen']
    d,data=inputs('test');assert len(d['row'])==13189 and np.all(d['role']==3)
    old=arrays(ART/'train_cal_predictions.npz');pred={'row':np.r_[old['row'],d['row']]}
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
    np.savez_compressed(ART/'predictions.npz',**pred)
    save('inference.json',dict(completed=True,records=71376,test_records=13189,
         new_fits=0,previous_fits=3,checkpoints_frozen_before_test=True,**cost(start)))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['fit','infer']);a=p.parse_args()
    fit() if a.mode=='fit' else infer()
