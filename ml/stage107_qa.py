"""One implementation-only equivalence and unchanged resource gate; no optimizer."""
import json
import math
import time
from pathlib import Path

import numpy as np
import torch

from stage106_geometry import ROOT,arrays,cost
from stage106_model import PointData,initialized,settings,event_from_xyz,hidden_plane
from stage107_device_data import DevicePointData
from retrain_accurate_posterior import reconstruct
from compare_energy_architectures import representation
from stage105_point_feasibility import CENTERS,OFFSETS

OUT=ROOT/'workbook/stage107_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage107'


def save(name,value):
    (OUT/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def model_probe(cell):
    model=initialized(cell)
    with torch.no_grad():model.head.weight.copy_(torch.linspace(-.01,.01,64,device='cuda')[None,:])
    return model


def forward_loss(model,x,target,weight,den,pretrain):
    pred=model(**x)
    values=(pred-target*pred.log()).mean(1) if pretrain else (pred-target).square()
    loss=(values*weight).sum()/den
    assert torch.isfinite(loss)
    loss.backward()
    return pred.detach()


def main():
    settings();start=time.perf_counter(),time.process_time()
    c=arrays(CACHE/'QA_coordinates.npz');d=reconstruct(c['row'])
    assert len(c['row'])==len(np.unique(d['key_id']))==40 and np.isin(d['role'],[1,2]).all()
    state=json.loads((ROOT/'workbook/stage94_energy_ml/preprocessing.json').read_text())['C']
    summary,_,_=representation(d,'C',state)
    base=PointData(c,summary,d['key_id'])
    torch.cuda.reset_peak_memory_stats();cold=time.perf_counter(),time.process_time()
    resident=DevicePointData(base,d['role']);resident.prepare_schedules(range(1,21))
    torch.cuda.synchronize();cold_cost=cost(cold)
    equality=[]
    for epoch in [None,1,7,20]:
        indices=np.arange(40) if epoch is None else np.flatnonzero((d['role']==1)&c['available'])
        expected=[[i for i,_ in g] for g in base.microbatches(indices,epoch)]
        actual=list(resident.groups(indices,epoch));assert expected==[g.tolist() for g in actual]
        for ids in actual:
            ref_ids,ref=base.pack([(int(i),base.get(i,epoch)) for i in ids],'cpu',epoch is not None)
            got,targets=resident.pack(ids,epoch)
            for k in ['x','edges','ef','pool','meta']+(['summary'] if epoch is None else ['hidden']):
                np.testing.assert_array_equal(ref[k].numpy(),got[k].cpu().numpy())
            if epoch is not None:
                np.testing.assert_array_equal(ref['target'].numpy(),targets.cpu().numpy())
                assert 'summary' not in got and 'target' not in got
            assert torch.equal(got['pool'][got['edges'][0]]//12,got['pool'][got['edges'][1]]//12)
        equality.append(dict(epoch=epoch,events=len(indices),exact=True))
    # Masked coordinate and count changes, with resident offsets rebuilt, cannot alter visible input.
    first=int(np.flatnonzero(c['available']&(d['role']==1))[0]);h=hidden_plane(d['key_id'][first],1)
    a,b=c['offsets'][first:first+2];xyz=c['xyz'][a:b].copy()
    from stage106_geometry import planes
    p,_=planes(xyz);xyz[p==h,:2]+=[17,-29]
    changed=np.r_[xyz,[[1.,2.,CENTERS[h//3]+OFFSETS[h%3]]]*2].astype('float32')
    cc=dict(row=c['row'][first:first+1],role=np.array([1]),xyz=changed,offsets=np.array([0,len(changed)]),available=np.array([True]))
    other=DevicePointData(PointData(cc,summary[first:first+1],d['key_id'][first:first+1]),np.array([1]))
    before,_=resident.pack([first],1);after,_=other.pack([0],1)
    for k in ['x','edges','ef','pool','meta','hidden']:torch.testing.assert_close(before[k],after[k],rtol=0,atol=0)
    del other,before,after
    gradients=[]
    for pretrain in [False,True]:
        indices=np.flatnonzero((d['role']==1)&c['available']) if pretrain else np.arange(40)
        epoch=1 if pretrain else None
        reference=model_probe('B');candidate=model_probe('B')
        den=float(d['weight'][indices].sum());maximum=0.
        with torch.no_grad():
            for k,v in reference.state_dict().items():torch.testing.assert_close(v,candidate.state_dict()[k],rtol=0,atol=0)
        for group in base.microbatches(indices,epoch):
            ids,x=base.pack(group,'cuda',pretrain)
            target=x.pop('target') if pretrain else torch.as_tensor(np.log(d['truth_E_GeV'][ids]),device='cuda',dtype=torch.float32)
            w=torch.as_tensor(d['weight'][ids],device='cuda',dtype=torch.float32)
            forward_loss(reference,x,target,w,den,pretrain)
        # Force extra event microbatches while preserving every original event and denominator.
        for ids in resident.groups(indices,epoch,node_cap=600,edge_cap=6000):
            x,t=resident.pack(ids,epoch)
            target=t if pretrain else torch.as_tensor(np.log(d['truth_E_GeV'][ids]),device='cuda',dtype=torch.float32)
            w=torch.as_tensor(d['weight'][ids],device='cuda',dtype=torch.float32)
            forward_loss(candidate,x,target,w,den,pretrain)
        for (name,a),(name2,b) in zip(reference.named_parameters(),candidate.named_parameters()):
            assert name==name2
            assert (a.grad is None)==(b.grad is None)
            if a.grad is None:continue
            torch.testing.assert_close(a.grad,b.grad,rtol=1e-5,atol=3e-6)
            maximum=max(maximum,float(abs(a.grad-b.grad).max()))
        # Same learned weights, only changed preparation; no optimizer ever created.
        ids=indices[:8];refids,refx=base.pack([(int(i),base.get(i,epoch)) for i in ids],'cuda',pretrain)
        if pretrain:refx.pop('target')
        newx,_=resident.pack(ids,epoch)
        with torch.no_grad():difference=float(abs(reference(**refx)-candidate(**newx)).max())
        assert difference<=3e-6
        gradients.append(dict(pretrain=pretrain,events=len(indices),real_incoming_weights=True,
            forced_microbatch_gradient_max_abs=maximum,output_max_abs=difference))
        del reference,candidate,x,refx,newx
    profile=[]
    for cell in ['A','B','pretraining']:
        pretrain=cell=='pretraining';model=model_probe('B' if pretrain else cell)
        source=np.flatnonzero((d['role']==1)&c['available']) if pretrain else np.arange(40)
        repeat=np.resize(source,256);times=[];cpus=[];epoch=1 if pretrain else None
        for repetition in range(4):
            model.zero_grad(set_to_none=True);torch.cuda.synchronize();tick=time.perf_counter(),time.process_time()
            den=float(d['weight'][repeat].sum())
            for ids in resident.groups(repeat,epoch):
                x,target=resident.pack(ids,epoch)
                if not pretrain:target=torch.as_tensor(np.log(d['truth_E_GeV'][ids]),device='cuda',dtype=torch.float32)
                w=torch.as_tensor(d['weight'][ids],device='cuda',dtype=torch.float32)
                value=forward_loss(model,x,target,w,den,pretrain);value.cpu().numpy()
            torch.cuda.synchronize();times.append(time.perf_counter()-tick[0]);cpus.append(time.process_time()-tick[1])
        profile.append(dict(cell=cell,device='cuda',batch=256,forward_backward_wall_s=float(np.median(times[1:])),
            CPU_s=float(np.median(cpus[1:])),timing_wall_s=times,timing_CPU_s=cpus))
        del model
    peak=torch.cuda.max_memory_allocated()/1024**2
    properties=torch.cuda.get_device_properties(0)
    config=json.loads((OUT/'protocol.json').read_text())
    previous=config['previous_cost_charged']
    ext=json.loads((ROOT/'workbook/stage106_energy_ml/QA_extraction.json').read_text())
    batchfactor=math.ceil(46575/256)*620*3
    gpu=max(p['forward_backward_wall_s'] for p in profile)*batchfactor+600+previous['GPU_container_wall_s']
    CPU=max(p['CPU_s'] for p in profile)*batchfactor+ext['projected_full_extraction_CPU_s']+previous['CPU_s']
    # Cold construction/schedule cost is a separate fixed cost, never hidden by warmup.
    cold_projection=3*cold_cost['CPU_s']*58187/40
    GPU_cold_projection=3*cold_cost['wall_s']*58187/40
    gpu+=GPU_cold_projection;CPU+=cold_projection
    admission=bool(gpu<=7200 and CPU<=21600 and peak<=.75*properties.total_memory/1024**2)
    save('model_QA.json',dict(passed=True,equality=equality,hidden_coordinate_count_input_exact=True,
        weighted_gradients=gradients,profile=profile,cold_cost=cold_cost,
        GPU_allocated_peak_MiB=peak,peak_scope='maximum since before resident construction across entire numerical QA',
        GPU=properties.name,device_memory_MiB=properties.total_memory/1024**2,
        optimizer_steps=0,new_fits=0,test_payload_records=0,**cost(start)))
    save('admission.json',dict(passed=admission,GPU_task_wall_projection_s=gpu,CPU_projection_s=CPU,
        cold_CPU_projection_s=cold_projection,cold_GPU_wall_projection_s=GPU_cold_projection,
        GPU_limit_s=7200,CPU_limit_s=21600,old_measured_cost_included=True,
        same_worst_batch_620epoch_factor3_rule=True,optimizer_steps=0))
    print((OUT/'model_QA.json').read_text(),flush=True);print((OUT/'admission.json').read_text(),flush=True)


if __name__=='__main__':main()
