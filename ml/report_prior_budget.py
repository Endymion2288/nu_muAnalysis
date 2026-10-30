#!/usr/bin/env python3
"""Assess BDT budget sensitivity using frozen development predictions only."""
import json
import resource
import time
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import yaml

from check_set_preprocessing import compare_preprocessing
from report_prior import quantile_samples, read_table
from report_robustness import group_bootstrap_losses, svg
from train_bdt import metric_values, write_table


def main():
    root=Path(__file__).resolve().parents[1];out=root/'workbook/stage22_energy_ml'
    tick=time.perf_counter();cpu=time.process_time()
    cfg=yaml.safe_load((root/'ml/configs/prior_budget_cpu.yaml').read_text())
    prior=yaml.safe_load((root/cfg['reference_prior']).read_text())
    assert cfg['seeds']==prior['seeds'] and cfg['fixed_trials']['bdt']==prior['fixed_trials']['bdt']
    assert cfg['energy_edges_GeV']==prior['energy_edges_GeV'] and cfg['max_fit_wall_s']==prior['max_fit_wall_s']
    with np.load(root/'ntuples/energy_ml_stage15/validation_truth.npz') as d:
        truth={k:d[k] for k in d.files if not k.endswith('_json')}
    y=truth['truth_E_GeV'];edges=np.array(cfg['energy_edges_GeV']);n=len(y)
    assert n==13375
    predictions={};traces={};costs=[];runs=[];prechecks=[];controls=[];hardware=[];common=None;groups=None
    for mode in cfg['modes']:
        folder=out/f'bdt_{mode}';art=root/f'ml/artifacts/stage22/bdt_{mode}'
        run=json.loads((folder/'summary.json').read_text())
        if 'study' not in run:run['study']=json.loads((out/'training_config.json').read_text())['study']
        if 'weights' not in run:run['weights']=json.loads((out/'weights.json').read_text())
        assert run['gpu']=='none (CPU)' and run['device']=='cpu' and run['threads']==4
        assert run['torch_threads']==4
        assert not run['smoke'] and not run['calibration_test_challenge_evaluated']
        assert run['train_events']==54196 and run['validation_events']==n
        assert run['study']==cfg and run['effective_trial']==dict(max_depth=7,rounds=4800)
        assert run['weights']==json.loads((root/'workbook/stage21_energy_ml/weights.json').read_text())
        runs.append(run)
        meta=json.loads((art/'preprocessing.json').read_text())
        if common is None:common=meta
        prechecks.append(dict(model=mode,**compare_preprocessing(common,meta)))
        old_art=root/f'ml/artifacts/stage21/bdt_{mode}'
        prechecks.append(dict(model=f'{mode}_vs_stage21',**compare_preprocessing(json.loads((old_art/'preprocessing.json').read_text()),meta)))
        with np.load(art/'predictions.npz') as d:
            for key in ['run','eventID','truth_E_GeV']:np.testing.assert_array_equal(d[key],truth[key])
            if groups is None:groups=d['group']
            else:np.testing.assert_array_equal(d['group'],groups)
            predictions[f'{mode}4800']=np.stack([d[f'seed_{i}'] for i in range(3)])
            predictions[f'{mode}1200']=np.stack([d[f'prefix_seed_{i}'] for i in range(3)])
        for budget in [1200,4800]:
            p=predictions[f'{mode}{budget}'];assert p.shape==(3,n) and np.isfinite(p).all() and (p>0).all()
        traces[f'{mode}4800']=json.loads((folder/'learning_traces.json').read_text())
        control=json.loads((folder/'short_budget_control.json').read_text())
        assert control['max_relative_prediction_difference']==0 and all(v==0 for v in control['common_metric_max_differences'].values())
        costs.append(dict(model=f'{mode}1200_control',seed_index=0,seed=control['seed'],**control['cost']))
        new_costs=read_table(folder/'costs.tsv')
        for r in new_costs:
            h=traces[f'{mode}4800'][f"seed_{r['seed_index']}"]['validation']['rmse']
            assert int(r['best_iteration'])==int(np.argmin(h)) and int(r['iterations'])==len(h)
            assert int(r['prefix_best_iteration'])==int(np.argmin(h[:1200]))
            costs.append(dict(model=f'{mode}4800',**r))
            controls.append(dict(mode=mode,seed=r['seed'],prefix_iterations=min(len(h),1200),prefix_best_iteration=r['prefix_best_iteration'],
                independent_short_fit_measured=r['seed_index']=='0',independent_prediction_difference=control['max_relative_prediction_difference'] if r['seed_index']=='0' else 'unmeasured',
                independent_train_metric_difference=control['common_metric_max_differences']['train'] if r['seed_index']=='0' else 'unmeasured',
                independent_validation_metric_difference=control['common_metric_max_differences']['validation'] if r['seed_index']=='0' else 'unmeasured'))
        old_trace=json.loads((root/f'workbook/stage21_energy_ml/bdt_{mode}/learning_traces.json').read_text())
        with np.load(old_art/'predictions.npz') as d:
            for key in ['run','eventID','truth_E_GeV']:np.testing.assert_array_equal(d[key],truth[key])
            np.testing.assert_array_equal(d['group'],groups)
            for i,seed in enumerate(cfg['seeds']):
                a=predictions[f'{mode}1200'][i];b=d[f'seed_{i}'];row=dict(mode=mode,seed=seed,max_relative_prediction_difference=float(np.max(abs(a/b-1))),
                    mean_absolute_relative_prediction_difference=float(np.mean(abs(a/b-1))),CPU_prefix_log_RMSE=float(np.sqrt(np.mean(np.log(a/y)**2))),GPU_reference_log_RMSE=float(np.sqrt(np.mean(np.log(b/y)**2))))
                for split in ['train','validation']:
                    x=old_trace[f'seed_{i}'][split]['rmse'];z=traces[f'{mode}4800'][f'seed_{i}'][split]['rmse'];length=min(len(x),len(z),1200)
                    row[f'{split}_common_iterations']=length;row[f'{split}_max_metric_difference']=float(np.max(abs(np.array(x[:length])-z[:length])))
                hardware.append(row)
    write_table(out/'prefix_controls.tsv',controls);write_table(out/'preprocessing_checks.tsv',prechecks)
    write_table(out/'stage21_hardware_reference.tsv',hardware)
    thread_checks=[]
    for mode in cfg['modes']:
        before=out/f'before_thread_fix/bdt_{mode}'
        old_trace=json.loads((before/'learning_traces.json').read_text())
        old_costs=read_table(before/'costs.tsv')
        new_costs=read_table(out/f'bdt_{mode}/costs.tsv')
        with np.load(root/f'ml/artifacts/stage22_before_thread_fix/bdt_{mode}/predictions.npz') as d:
            for i,seed in enumerate(cfg['seeds']):
                a=predictions[f'{mode}4800'][i];b=d[f'seed_{i}']
                prefix=predictions[f'{mode}1200'][i];old_prefix=d[f'prefix_seed_{i}']
                old=old_costs[i];new=new_costs[i]
                row=dict(mode=mode,seed=seed,final_max_relative_prediction_difference=float(np.max(abs(a/b-1))),
                         prefix_max_relative_prediction_difference=float(np.max(abs(prefix/old_prefix-1))),
                         old_best_iteration=old['best_iteration'],new_best_iteration=new['best_iteration'],
                         old_iterations=old['iterations'],new_iterations=new['iterations'],old_wall_s=old['train_wall_s'],new_wall_s=new['train_wall_s'],
                         old_cpu_s=old['train_cpu_s'],new_cpu_s=new['train_cpu_s'])
                for split in ['train','validation']:
                    x=old_trace[f'seed_{i}'][split]['rmse'];z=traces[f'{mode}4800'][f'seed_{i}'][split]['rmse'];length=min(len(x),len(z))
                    row[f'{split}_common_iterations']=length;row[f'{split}_max_metric_difference']=float(np.max(abs(np.array(x[:length])-z[:length])))
                thread_checks.append(row)
    write_table(out/'threading_reproduction.tsv',thread_checks)
    losses={k:np.mean(np.log(p/y)**2,axis=0) for k,p in predictions.items()}
    macro,boot=group_bootstrap_losses(losses,y,groups,edges,cfg['bootstrap_replicates'],cfg['seeds'][0])
    overview=[]
    for name,loss in losses.items():
        ci=np.quantile(boot[name],[.025,.975]);overview.append(dict(model=name,macro_log_RMSE=macro[name],CI025=ci[0],CI975=ci[1],integrated_log_RMSE=float(np.sqrt(loss.mean()))))
    pairs=[('FU1200','FU4800'),('UU4800','FU4800'),('UU1200','UU4800'),('UU1200','FU1200')]
    gains=[]
    for left,right in pairs:
        ci=np.quantile(boot[right]-boot[left],[.025,.975]);gains.append(dict(reference=left,model=right,delta=macro[right]-macro[left],CI025=ci[0],CI975=ci[1]))
    matched=truth['lead_primary_parent_confirmed'];ylep=truth['y_lepton'];z=truth['vertex_z_mm']
    masks=[('all','all',np.ones(n,dtype=bool)),('matching','primary_confirmed',matched),('matching','other_leading',~matched),
           ('truth_region','FASERnu_box',z< -1950),('truth_region','lead_block',z>= -1950)]
    masks += [('y_lepton',f'{lo:g}_{hi:g}',(ylep>=lo)&(ylep<hi)) for lo,hi in zip(cfg['y_edges'][:-1],cfg['y_edges'][1:])]
    masks += [('y_primary_confirmed',f'ge_{lo:g}',matched&(ylep>=lo)) for lo in [.6,.8]]
    masks += [('energy_GeV',f'{lo:g}_{hi:g}',(y>=lo)&(y<hi)) for lo,hi in zip(edges[:-1],edges[1:])]
    masks += [('run',str(int(run)),truth['run']==run) for run in np.unique(truth['run'])]
    _,gid=np.unique(groups,return_inverse=True);ng=gid.max()+1
    draws=np.random.default_rng(cfg['seeds'][0]).multinomial(ng,np.full(ng,1/ng),size=cfg['bootstrap_replicates'])
    residual={k:p/y-1 for k,p in predictions.items()};vectors={'log_RMSE':losses}
    for key,fun in [('mean_bias',lambda r:r),('tail_0p5',lambda r:abs(r)>.5),('tail_1',lambda r:abs(r)>1),('under_0p5',lambda r:r<-.5),('over_0p5',lambda r:r>.5)]:
        vectors[key]={k:np.mean(fun(r),axis=0) for k,r in residual.items()}
    metrics=[];stratified=[];nonlinear=[]
    for label,value,mask in masks:
        counts=np.bincount(gid[mask],minlength=ng);den=draws@counts;valid=den>0;center={};samples={}
        for name,p in predictions.items():
            for si,a in enumerate(p):
                r=a[mask]/y[mask]-1
                metrics.append(dict(model=name,seed=cfg['seeds'][si],stratum=label,value=value,**metric_values(y,a,mask),under_0p5=float(np.mean(r<-.5)),over_0p5=float(np.mean(r>.5))))
            center[name]={};samples[name]={}
            for key,by_model in vectors.items():
                v=by_model[name];sums=np.bincount(gid[mask],weights=v[mask],minlength=ng);b=(draws@sums)[valid]/den[valid]
                center[name][key]=np.sqrt(v[mask].mean()) if key=='log_RMSE' else v[mask].mean();samples[name][key]=np.sqrt(b) if key=='log_RMSE' else b
        for left,right in pairs:
            row=dict(reference=left,model=right,stratum=label,value=value,N=int(mask.sum()),source_groups=int((counts>0).sum()),bootstrap_valid=int(valid.sum()))
            for key in vectors:
                ci=np.quantile(samples[right][key]-samples[left][key],[.025,.975])
                row.update({f'{key}_reference':center[left][key],f'{key}_model':center[right][key],f'{key}_delta':center[right][key]-center[left][key],f'{key}_CI025':ci[0],f'{key}_CI975':ci[1]})
            stratified.append(row)
        if label not in ['energy_GeV','y_primary_confirmed']:continue
        nc={};nb={}
        for name,r in residual.items():
            values=[quantile_samples(a[mask],gid[mask],draws[valid]) for a in r]
            nc[name]={k:np.mean([v[1][k] for v in values]) for k in ['median_bias','R68']}
            nb[name]={k:np.mean([v[0][k] for v in values],axis=0) for k in ['median_bias','R68']}
        for left,right in pairs:
            for key in ['median_bias','R68']:
                ci=np.quantile(nb[right][key]-nb[left][key],[.025,.975])
                nonlinear.append(dict(reference=left,model=right,stratum=label,value=value,N=int(mask.sum()),metric=key,reference_CDF=nc[left][key],model_CDF=nc[right][key],delta_CDF=nc[right][key]-nc[left][key],CI025=ci[0],CI975=ci[1],bootstrap_valid=int(valid.sum())))
    # Union of cost columns keeps the inherited UU inference timing and the new prefix index.
    keys=list(dict.fromkeys(k for r in costs for k in r));costs=[{k:r.get(k,'unmeasured') for k in keys} for r in costs]
    for filename,items in [('macro_summary.tsv',overview),('macro_gains.tsv',gains),('metrics.tsv',metrics),('stratified_gains.tsv',stratified),('nonlinear_gains.tsv',nonlinear),('costs.tsv',costs)]:write_table(out/filename,items)
    fig,axes=plt.subplots(1,2,figsize=(12,4.8),layout='constrained')
    centers=np.sqrt(edges[:-1]*edges[1:])
    for name in predictions:
        chosen=[r for r in metrics if r['model']==name and r['stratum']=='energy_GeV']
        values=[[r for r in chosen if r['value']==f'{lo:g}_{hi:g}'] for lo,hi in zip(edges[:-1],edges[1:])]
        axes[0].plot(centers,[np.mean([r['median_bias'] for r in rr]) for rr in values],'o-',label=name)
        axes[1].plot(centers,[np.mean([r['tail_0p5'] for r in rr]) for rr in values],'o-',label=name)
    axes[0].axhline(0,color='gray',lw=1);axes[0].set(ylabel='Median relative bias');axes[1].set(ylabel='P(abs(relative error)>0.5)')
    for ax in axes:ax.set(xscale='log',xlabel='True neutrino energy [GeV]');ax.legend()
    svg(fig,out/'budget_response.svg')
    fig,axes=plt.subplots(1,2,figsize=(12,4.5),layout='constrained')
    for i in range(3):
        h=traces['FU4800'][f'seed_{i}']
        for ax,split in zip(axes,['train','validation']):
            values=h[split]['rmse'];start=0 if split=='train' else 399
            line,=ax.plot(np.arange(start+1,len(values)+1),values[start:],label=f'seed {i}')
            if split=='validation':
                best=int(np.argmin(values));ax.plot(best+1,values[best],'*',color=line.get_color(),ms=10)
    for ax,split in zip(axes,['train','validation']):ax.axvline(1200,color='gray',ls='--');ax.set(xlabel='Boosting round',ylabel=f'{split}: normalized log-E RMSE');ax.legend()
    axes[1].set_title('Validation from round 400; stars mark minima')
    svg(fig,out/'budget_learning.svg')
    (out/'training_config.json').write_text(json.dumps(dict(study=cfg,prior_reference=prior),indent=2)+'\n')
    (out/'weights.json').write_text(json.dumps(runs[0]['weights'],indent=2)+'\n')
    for run in runs:
        compact={k:v for k,v in run.items() if k not in ['study','weights']};compact.update(configuration_file='../training_config.json',weights_file='../weights.json')
        (out/f"bdt_{run['mode']}"/'summary.json').write_text(json.dumps(compact,indent=2)+'\n')
    summary=dict(models=4,new_fits=8,long_fits=6,independent_short_controls=2,train_events=54196,validation_events=n,source_groups=int(ng),
        total_new_fit_wall_s=sum(float(r['train_wall_s']) for r in costs),
        worker_wall_sum_s=sum(r['wall_s'] for r in runs),worker_cpu_sum_s=sum(r['cpu_s'] for r in runs),worker_peak_rss_MiB=max(r['peak_rss_MiB'] for r in runs),
        actual_gpus=[r['gpu'] for r in runs],cpu_models=[r['cpu_model'] for r in runs],hosts=[r['host'] for r in runs],calibration_test_challenge_evaluated=False,
        report_wall_s=time.perf_counter()-tick,report_cpu_s=time.process_time()-cpu,report_peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    previous=json.loads((out/'before_thread_fix/summary.json').read_text())
    summary.update(first_round_fits=previous['new_fits'],total_stage_fits=previous['new_fits']+summary['new_fits'],
        first_round_fit_wall_s=previous['total_new_fit_wall_s'],total_stage_fit_wall_s=previous['total_new_fit_wall_s']+summary['total_new_fit_wall_s'],
        total_stage_worker_wall_s=previous['worker_wall_sum_s']+summary['worker_wall_sum_s'],
        total_stage_worker_cpu_s=previous['worker_cpu_sum_s']+summary['worker_cpu_sum_s'])
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
