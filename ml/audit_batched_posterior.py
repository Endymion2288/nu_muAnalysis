"""Stage91 saved-reference batch likelihood certification and timings; zero fit."""
import argparse
import json
import subprocess
import sys
import tarfile
from pathlib import Path

import numpy as np
import torch

from batched_posterior import value_gradient, log_energy_density
from support_augmentation import arrays, save, table, begin, resources

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / 'workbook/stage91_energy_ml'
CACHE = REPO / 'ntuples/energy_ml_stage91'
SPOOL = Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage91')
CODE = ['ml/batched_posterior.py', 'ml/audit_batched_posterior.py', 'ml/support_augmentation.py']


def sync(device):
    if device == 'cuda':
        torch.cuda.synchronize()


def environment():
    return dict(torch=torch.__version__,torch_cuda=torch.version.cuda,cuda_available=torch.cuda.is_available(),
        GPU=torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'unavailable',
        CPU_threads=torch.get_num_threads(),GPU_properties=str(torch.cuda.get_device_properties(0)) if torch.cuda.is_available() else 'unavailable')


def make_inputs():
    d=arrays(REPO/'ntuples/energy_ml_stage90/input.npz')
    v=arrays(REPO/'ntuples/energy_ml_stage90/audit_values.npz')
    np.testing.assert_array_equal(d['row'],v['row'])
    assert len(d['row'])==552 and (d['role']==1).sum()==40 and (d['role']==2).sum()==512
    assert not (d['role']==3).any()
    keep=['row','head','role','weight','truth_E_GeV','pz','b','T','key_id','group']
    d={k:d[k] for k in keep}
    d.update(reference_value=v['reference_value'],reference_gradient=v['reference_gradient'],
        reference_uncertainty=v['reference_uncertainty'],adaptive_value=v['value'],adaptive_gradient=v['gradient'])
    return d


def evaluate(d,device,batch=256):
    start=begin();values=[];gradients=[];tail=[];intervals=[]
    if device=='cuda':
        torch.cuda.reset_peak_memory_stats()
    for j in range(0,len(d['row']),batch):
        sl=slice(j,j+batch)
        h=torch.as_tensor(d['head'][sl],device=device)
        z=torch.as_tensor(np.log(d['truth_E_GeV'][sl]),device=device)
        p=torch.as_tensor(d['pz'][sl],device=device)
        b=torch.as_tensor(d['b'][sl],device=device);T=torch.as_tensor(d['T'][sl],device=device)
        value,gradient,meta=value_gradient(h,z,p,b,T)
        values.append(value.cpu().numpy());gradients.append(gradient.cpu().numpy())
        tail.append(meta['density_tail_bound'].cpu().numpy());intervals.append(meta['nonempty_intervals'].cpu().numpy())
    sync(device)
    value=np.concatenate(values);gradient=np.concatenate(gradients)
    threshold=1e-4+1e-3*abs(d['reference_gradient'])
    error=abs(gradient-d['reference_gradient'])
    scaled=(error+d['reference_uncertainty'])/threshold
    vp=abs(value-d['reference_value'])<=1e-6
    gp=scaled<=1
    certified=vp&gp.all(1)&np.isfinite(gradient).all(1)&np.isfinite(value)
    summary=dict(device=device,N=len(value),batch=batch,certified_N=int(certified.sum()),
        failed_values_N=int((~vp).sum()),failed_coordinates_N=int((~gp).sum()),
        max_value_error=float(abs(value-d['reference_value']).max()),max_gradient_error=float(error.max()),
        max_gradient_error_plus_uncertainty_over_tolerance=float(scaled.max()),
        max_density_tail_bound=float(np.concatenate(tail).max()),
        intervals_min=int(np.concatenate(intervals).min()),intervals_max=int(np.concatenate(intervals).max()),
        GPU_peak_allocated_MiB=torch.cuda.max_memory_allocated()/2**20 if device=='cuda' else 0,
        **resources(start))
    return dict(value=value,gradient=gradient,certified=certified,gradient_pass=gp),summary


def vjp_control(d,device):
    # Original float32 head leaves, float64 integration, mixed upstream signs.
    h=torch.tensor(d['head'],device=device,dtype=torch.float32,requires_grad=True)
    z=torch.tensor(np.log(d['truth_E_GeV']),device=device)
    p=torch.tensor(d['pz'],device=device)
    b=torch.tensor(d['b'][0],device=device,dtype=torch.float64,requires_grad=True)
    T=torch.tensor(d['T'][0],device=device,dtype=torch.float64,requires_grad=True)
    up=torch.linspace(-.7,1.3,len(h),device=device,dtype=torch.float64)
    value=log_energy_density(h,z,p,b,T);(up*value).sum().backward()
    _,g,_=value_gradient(h,z,p,b,T)
    expected=g*up[:,None]
    diff=float((h.grad-expected[:,:15].to(torch.float32)).abs().max().cpu())
    bp=abs(float(b.grad.cpu())-float(expected[:,15].sum().cpu()))
    tp=abs(float(T.grad.cpu())-float(expected[:,16].sum().cpu()))
    # Reference comparison includes expected float32 rounding after integration.
    ref=torch.tensor(d['reference_gradient'],device=device)*up[:,None]
    tol=(1e-4+1e-3*torch.tensor(abs(d['reference_gradient']),device=device))*up.abs()[:,None]
    noise=torch.tensor(d['reference_uncertainty'],device=device)*up.abs()[:,None]
    passed=bool(((h.grad.to(torch.float64)-ref[:,:15]).abs()+noise[:,:15]<=tol[:,:15]+1e-12).all().cpu())
    assert h.grad.dtype==torch.float32 and value.dtype==torch.float64
    assert diff==0 and bp<1e-10 and tp<1e-10
    return dict(device=device,N=len(h),passed=passed,head_leaf_dtype=str(h.dtype),integral_dtype=str(value.dtype),
        head_exact_cast_difference=diff,shared_b_difference=bp,shared_T_difference=tp,
        head_gradient=h.grad.cpu().numpy(),b_gradient=float(b.grad.cpu()),T_gradient=float(T.grad.cpu()))


def moving_node_control(d,device):
    # Fixed first two QA identities; recompute partitions at every perturbation.
    rows=[];maximum=0.
    for i in range(2):
        x=np.r_[d['head'][i].astype(float),d['b'][i],d['T'][i]]
        h=[];bb=[];tt=[]
        for step in [1e-4,5e-5]:
            for j in range(17):
                for sign in [-1,1]:
                    xx=x.copy();xx[j]+=sign*step;h.append(xx[:15]);bb.append(xx[15]);tt.append(xx[16])
        n=len(h);make=lambda a:torch.tensor(np.asarray(a),device=device,dtype=torch.float64)
        vals,_,_=value_gradient(make(h),make(np.full(n,np.log(d['truth_E_GeV'][i]))),make(np.full(n,d['pz'][i])),make(bb),make(tt))
        vals=vals.cpu().numpy().reshape(2,17,2)
        full=(vals[0,:,1]-vals[0,:,0])/2e-4;half=(vals[1,:,1]-vals[1,:,0])/1e-4
        fd=(4*half-full)/3
        _,g,_=value_gradient(make(x[:15][None]),make([np.log(d['truth_E_GeV'][i])]),make([d['pz'][i]]),make([x[15]]),make([x[16]]))
        error=abs(fd-g.cpu().numpy()[0]);tol=1e-4+1e-3*abs(fd)
        maximum=max(maximum,float(error.max()))
        rows.append(dict(row=int(d['row'][i]),max_difference=float(error.max()),passed=bool((error<=tol).all())))
    return dict(device=device,passed=all(r['passed'] for r in rows),recomputed_node_derivative_checks=34,max_difference=maximum,rows=rows)


def qa():
    start=begin();OUT.mkdir(exist_ok=True,parents=True);CACHE.mkdir(exist_ok=True,parents=True)
    torch.set_num_threads(1);d=make_inputs();m=np.flatnonzero(d['role']==2)[:40]
    d={k:v[m] for k,v in d.items()};np.savez_compressed(CACHE/'qa_input.npz',**d)
    summaries=[];controls=[];result={}
    for device in ['cpu','cuda']:
        v,s=evaluate(d,device);summaries.append(s);result[device]=v
        c=vjp_control(d,device);np.savez_compressed(CACHE/f'qa_{device}_vjp.npz',head_gradient=c.pop('head_gradient'))
        controls.extend([c,moving_node_control(d,device)])
    cross=dict(max_value_difference=float(abs(result['cpu']['value']-result['cuda']['value']).max()),
        max_gradient_difference=float(abs(result['cpu']['gradient']-result['cuda']['gradient']).max()))
    passed=all(s['certified_N']==40 for s in summaries) and all(c['passed'] for c in controls)
    save(OUT/'startup_QA.json',dict(passed=passed,environment=environment(),fixed_cal_N=40,numerics=summaries,controls=controls,CPU_GPU=cross,
        new_fits=0,new_test_evaluations=0,**resources(start)))
    for device in result:np.savez_compressed(CACHE/f'qa_{device}.npz',**result[device])
    print(json.dumps(dict(passed=passed,numerics=summaries,controls=controls,CPU_GPU=cross),indent=2),flush=True)


def package_qa():
    d=arrays(CACHE/'input.npz');q=arrays(CACHE/'qa_input.npz')
    assert len(d['row'])==552 and (d['role']==1).sum()==40 and (d['role']==2).sum()==512
    assert not (d['role']==3).any()
    q={k:v[:4] for k,v in q.items()}
    for device in ['cpu','cuda']:
        _,s=evaluate(q,device);assert s['certified_N']==4,s
    print('actual552 payload/roles and 4 fixedcal CPU/CUDA value/gradient controls passed',flush=True)


def benchmark(d,device,batch):
    # Fixed deterministic repeats of cal rows only; not additional independent events.
    ix=np.resize(np.flatnonzero(d['role']==2),batch)
    fixed={k:v[ix] for k,v in d.items()}
    times=[];CPU=[]
    if device=='cuda':torch.cuda.reset_peak_memory_stats()
    for repetition in range(6):
        sync(device);start=begin()
        # Includes host->device inputs, node construction, integrated score,
        # VJP, and output/gradient transfer back to host and synchronization.
        h=torch.tensor(fixed['head'],device=device,dtype=torch.float32,requires_grad=True)
        z=torch.tensor(np.log(fixed['truth_E_GeV']),device=device)
        p=torch.tensor(fixed['pz'],device=device)
        b=torch.tensor(fixed['b'][0],device=device,dtype=torch.float64,requires_grad=True)
        T=torch.tensor(fixed['T'][0],device=device,dtype=torch.float64,requires_grad=True)
        val=log_energy_density(h,z,p,b,T);(-val.mean()).backward()
        val.detach().cpu().numpy();h.grad.cpu().numpy();b.grad.cpu().numpy();T.grad.cpu().numpy();sync(device)
        cost=resources(start)
        if repetition>0:times.append(cost['wall_s']);CPU.append(cost['CPU_s'])
    return dict(device=device,batch=batch,repeats=5,warmup_repeats=1,wall_s=times,CPU_s=CPU,
        median_wall_s=float(np.median(times)),median_events_per_wall_s=float(batch/np.median(times)),
        GPU_peak_allocated_MiB=torch.cuda.max_memory_allocated()/2**20 if device=='cuda' else 0,
        scope='includes node construction/transfer/sync/forward/backward/output transfer; fixed repeatedcal heads only, no network or optimizer')


def worker():
    start=begin();torch.set_num_threads(2);package_qa();d=arrays(CACHE/'input.npz')
    rows=[];results={};checks=[]
    for device in ['cpu','cuda']:
        for batch in [256,1024]:
            v,s=evaluate(d,device,batch);rows.append(s);results[f'{device}_{batch}']=v
            np.savez_compressed(CACHE/f'{device}_{batch}.npz',row=d['row'],**v)
            print(device,batch,json.dumps(s),flush=True)
        q=arrays(CACHE/'qa_input.npz');c=vjp_control(q,device);c.pop('head_gradient');checks.extend([c,moving_node_control(q,device)])
    table(OUT/'numerics.tsv',rows);save(OUT/'VJP_controls.json',checks)
    timings=[]
    for device in ['cpu','cuda']:
        for batch in [256,1024]:
            r=benchmark(d,device,batch);timings.append(r);print('timing',json.dumps(r),flush=True)
    save(OUT/'benchmark.json',dict(environment=environment(),measurements=timings,new_fits=0,new_test_evaluations=0))
    diffs=[]
    ref=results['cpu_256']
    for name,v in results.items():
        diffs.append(dict(method=name,max_value_difference=float(abs(v['value']-ref['value']).max()),
            max_gradient_difference=float(abs(v['gradient']-ref['gradient']).max())))
    save(OUT/'decisions.json',dict(all552_certified=all(s['certified_N']==552 for s in rows),all_VJP_controls=all(c['passed'] for c in checks),
        scope='fixed552 finalhead only; no training trajectory/physics/test confirmation',cross_device_batch=diffs,
        deployment='retain existing deployment',new_fits=0,new_calibration=0,new_test_evaluations=0))
    save(OUT/'worker_resources.json',resources(start))


def submit():
    start=begin();assert not (OUT/'submission.json').exists()
    assert json.loads((OUT/'startup_QA.json').read_text())['passed']
    d=make_inputs();np.savez_compressed(CACHE/'input.npz',**d)
    paths=CODE+['ntuples/energy_ml_stage91/input.npz','ntuples/energy_ml_stage91/qa_input.npz','workbook/stage91_energy_ml/protocol.json']
    archive=REPO/'software/energy-ml-batched-stage91.tar.gz'
    with tarfile.open(archive,'w:gz',compresslevel=1) as t:
        for name in paths:t.add(REPO/name,arcname=name)
    import tempfile
    with tempfile.TemporaryDirectory(prefix='stage91_package_') as tmp:
        with tarfile.open(archive) as t:t.extractall(tmp,filter='data')
        output=subprocess.check_output([sys.executable,'ml/audit_batched_posterior.py','package-qa'],cwd=tmp,text=True)
    save(OUT/'package_QA.json',dict(passed=True,output=output,archive_bytes=archive.stat().st_size))
    (SPOOL/'logs').mkdir(parents=True,exist_ok=True)
    (SPOOL/'worker_v1.sh').write_bytes((REPO/'AnalysisZipFramework/submission/run_ml_batched_posterior.sh').read_bytes())
    output=subprocess.check_output(['condor_submit','-terse',str(REPO/'AnalysisZipFramework/submission/ml_batched_posterior.sub')],text=True)
    cluster=int(output.split('.')[0]);ads=json.loads(subprocess.check_output(['condor_q',str(cluster),'-json','-attributes','ClusterId,ProcId,RequestCpus,RequestMemory,RequestGpus,MaxRuntime,RequireGPUs'],text=True))
    assert len(ads)==1 and ads[0]['RequestCpus']==2 and ads[0]['RequestMemory']==6000 and ads[0]['RequestGpus']==1 and ads[0]['MaxRuntime']==1800
    save(OUT/'submission.json',dict(cluster=cluster,result=output,actual_ads=ads,**resources(start)));print(output,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['qa','package-qa','submit','worker'])
    a=p.parse_args();globals()[a.action.replace('-','_')]()
