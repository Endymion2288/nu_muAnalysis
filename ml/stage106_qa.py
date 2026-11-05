"""Zero optimizer QA and measured admission for the frozen Stage106 contract."""
import json
import math
import time

import numpy as np
import torch

from stage106_geometry import ROOT,OUT,CACHE,SEED,arrays,save,cost
from stage106_model import PointData,PointModel,initialized,settings,event_from_xyz,hidden_plane
from retrain_accurate_posterior import reconstruct
from compare_energy_architectures import representation
from stage105_point_feasibility import CENTERS,OFFSETS


def main():
    start=time.perf_counter(),time.process_time();settings()
    coordinates=arrays(CACHE/'QA_coordinates.npz')
    d=reconstruct(coordinates['row'])
    assert len(d['row'])==len(np.unique(d['key_id']))==40 and np.isin(d['role'],[1,2]).all()
    state=json.loads((ROOT/'workbook/stage94_energy_ml/preprocessing.json').read_text())['C']
    summary,_,_=representation(d,'C',state)
    assert summary.shape==(40,127)
    data=PointData(coordinates,summary,d['key_id'])
    for i in range(40):data.get(i)
    for i in range(40):
        v=data.get(i,1);hide=hidden_plane(d['key_id'][i],1)
        a,b=coordinates['offsets'][i:i+2];xyz=coordinates['xyz'][a:b]
        direct=event_from_xyz(xyz,bool(coordinates['available'][i]),hide)
        for k in ['x','plane','edges','ef','meta','target']:
            np.testing.assert_array_equal(v[k],direct[k])
        if coordinates['available'][i]:
            modified=np.r_[xyz,[[17.,-29.,CENTERS[hide//3]+OFFSETS[hide%3]]]]
            # Hidden-coordinate and multiplicity modification before the direct builder.
            from stage106_geometry import planes
            p,_=planes(modified);modified[p==hide,:2]+=[21,-13]
            damaged=event_from_xyz(modified,True,hide)
            for k in ['x','plane','edges','ef','meta']:np.testing.assert_array_equal(direct[k],damaged[k])
    checks=[];predictions={};base=None
    # A nonzero diagnostic output head sends derivatives through the encoders, no step.
    for cell in ['A','B']:
        initial=initialized(cell,device='cpu')
        current={k:v.detach().clone() for k,v in initial.state_dict().items()}
        if base is None:base=current
        else:
            for k in base:torch.testing.assert_close(base[k],current[k],rtol=0,atol=0)
        for device in ['cpu','cuda']:
            model=initialized(cell,device=device)
            with torch.no_grad():model.head.weight.copy_(torch.linspace(-.01,.01,64,device=device)[None,:])
            group=next(data.microbatches(np.arange(40)))
            ids,x=data.pack(group,device)
            torch.testing.assert_close(x['pool'][x['edges'][0]]//12,x['pool'][x['edges'][1]]//12,rtol=0,atol=0)
            p=model(**x);p.square().mean().backward()
            predictions[cell,device]=p.detach().cpu().numpy()
            grads={k:float(v.grad.norm()) for k,v in model.named_parameters() if v.grad is not None}
            assert all(torch.isfinite(v.grad).all() for v in model.parameters() if v.grad is not None)
            assert grads['point.0.weight']>0 and grads['update.0.weight']>0
            if cell=='B':assert grads['message.0.weight']>0
            reversed_group=list(reversed(group));ids2,x2=data.pack(reversed_group,device)
            with torch.no_grad():changed=model(**x2).cpu().numpy()[::-1]
            eventdelta=float(abs(changed-predictions[cell,device]).max())
            assert eventdelta<=3e-6
            # Reverse all node indices within each event and remap the edges/pool.
            perm=torch.arange(len(x['x'])-1,-1,-1,device=device)
            altered=dict(x);altered['x']=x['x'][perm];altered['pool']=x['pool'][perm]
            altered['edges']=len(perm)-1-x['edges']
            with torch.no_grad():pointdelta=float(abs(model(**altered)-p).max())
            assert pointdelta<=3e-6
            # Empty and missing whole events have no nodes/edges but finite outputs/gradients.
            empty=event_from_xyz(np.empty((0,3)),True);missing=event_from_xyz(np.empty((0,3)),False)
            bad=event_from_xyz(np.array([[-999.,-999.,-999.]]),True)
            assert bad['meta'][24]==0 and missing['meta'][24]==0 and empty['meta'][25]==1
            gi=[(0,empty),(1,missing),(2,bad)];_,sx=data.pack(gi,device)
            model.zero_grad(set_to_none=True);out=model(**sx);out.sum().backward();assert torch.isfinite(out).all()
            assert all(torch.isfinite(v.grad).all() for v in model.parameters() if v.grad is not None)
            # Cost includes effective256 full point inputs, microbatch packing, transfer and return.
            timings=[];cpus=[];repeat=np.arange(256)%40
            for rep in range(4):
                model.zero_grad(set_to_none=True)
                if device=='cuda':torch.cuda.synchronize();torch.cuda.reset_peak_memory_stats()
                tick=time.perf_counter(),time.process_time()
                for gg in data.microbatches(repeat):
                    ii,xx=data.pack(gg,device);z=model(**xx);(z.square().sum()/256).backward();z.detach().cpu().numpy()
                if device=='cuda':torch.cuda.synchronize()
                timings.append(time.perf_counter()-tick[0]);cpus.append(time.process_time()-tick[1])
            checks.append(dict(cell=cell,device=device,parameters=sum(p.numel() for p in model.parameters()),
                batch_events=256,microbatch_node_cap=16384,microbatch_edge_cap=262144,
                forward_backward_wall_s=float(np.median(timings[1:])),CPU_s=float(np.median(cpus[1:])),
                event_permutation_logE_max=eventdelta,point_permutation_logE_max=pointdelta,
                encoder_gradients=grads,empty_missing_invalid_finite=True,
                GPU_peak_allocated_MiB=torch.cuda.max_memory_allocated()/1024**2 if device=='cuda' else None))
            del model
            if device=='cuda':torch.cuda.empty_cache()
    candidate=initialized('C',device='cpu')
    for k,v in candidate.state_dict().items():torch.testing.assert_close(v,base[k],rtol=0,atol=0)
    # Train-only pretraining wiring: decoder input has no summary/scalar key.
    pre=initialized('B');timings=[];cpus=[];repeat=np.resize(np.flatnonzero(coordinates['available']&(d['role']==1)),256)
    for rep in range(4):
        pre.zero_grad(set_to_none=True);torch.cuda.synchronize();torch.cuda.reset_peak_memory_stats()
        tick=time.perf_counter(),time.process_time()
        for group in data.microbatches(repeat,1):
            ii,x=data.pack(group,'cuda',True);assert 'summary' not in x
            rates=pre(**x);target=x['target'];loss=(rates-target*rates.log()).mean(1).sum()/256
            loss.backward();rates.detach().cpu().numpy()
        torch.cuda.synchronize();timings.append(time.perf_counter()-tick[0]);cpus.append(time.process_time()-tick[1])
    assert all(v.grad is not None and torch.isfinite(v.grad).all() for k,v in pre.named_parameters() if k.startswith(('point.','message.','update.','decoder.')))
    overflow=event_from_xyz(np.array([[300.,0.,CENTERS[1]+OFFSETS[0]]]),True,3)
    assert overflow['target'][-1]==1 and overflow['target'].sum()==1
    precheck=dict(cell='pretraining',device='cuda',forward_backward_wall_s=float(np.median(timings[1:])),
        CPU_s=float(np.median(cpus[1:])),GPU_peak_allocated_MiB=torch.cuda.max_memory_allocated()/1024**2,
        decoder_gradient_norm=float(pre.decoder[0].weight.grad.norm()),train_only=True,scalars_absent=True)
    checks.append(precheck)
    agreement=max(float(abs(predictions[c,'cpu']-predictions[c,'cuda']).max()) for c in ['A','B'])
    assert agreement<=3e-6
    maxgpu=max(v['forward_backward_wall_s'] for v in checks if v['device']=='cuda')
    maxcpu=max(v['CPU_s'] for v in checks if v['device']=='cuda')
    ext=json.loads((OUT/'QA_extraction.json').read_text())
    gpu_projection=maxgpu*math.ceil(46575/256)*620*3+600
    host_projection=maxcpu*math.ceil(46575/256)*620*3
    extraction_projection=ext['projected_full_extraction_CPU_s']
    peak=max(v['GPU_peak_allocated_MiB'] for v in checks if v['device']=='cuda')
    deviceMiB=torch.cuda.get_device_properties(0).total_memory/1024**2
    admitted=gpu_projection<=7200 and host_projection+extraction_projection<=21600 and peak<=.75*deviceMiB
    save('model_QA.json',dict(passed=True,identities=40,optimizer_steps=0,new_fits=0,pretraining_steps=0,
        test_payload_records=0,CPU_GPU_max_logE_difference=agreement,B_C_initialization_exact=True,
        visible_only_direct_vs_filtered_edges_exact=True,hidden_coordinate_count_leak_probe_exact=True,
        overflow_empty_missing_invalid_probes=True,checks=checks,GPU=torch.cuda.get_device_name(),
        torch=torch.__version__,CUDA=torch.version.cuda,device_memory_MiB=deviceMiB,**cost(start)))
    save('admission.json',dict(passed=bool(admitted),projected_GPU_task_wall_s=gpu_projection,
        projected_GPU_host_CPU_s=host_projection,projected_extraction_plus_reserve_CPU_s=extraction_projection,
        projected_total_CPU_s=host_projection+extraction_projection,GPU_peak_allocated_MiB=peak,
        GPU_limit_s=7200,CPU_limit_s=21600,projection_heuristic=True,optimizer_steps=0))
    print((OUT/'model_QA.json').read_text(),flush=True);print((OUT/'admission.json').read_text(),flush=True)


if __name__=='__main__':main()
