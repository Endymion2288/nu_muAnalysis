#!/usr/bin/env python3
"""Paired physics diagnostics for the training/monitor weight factorial study."""
import csv
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
from report_robustness import group_bootstrap_losses, svg
from train_bdt import metric_values, write_table


def read_table(path):
    return list(csv.DictReader(path.open(),delimiter='\t'))


def quantile_samples(residual, local_groups, draws):
    order=np.argsort(residual);ordered=residual[order]
    weights=draws[:,local_groups[order]];cumulative=np.cumsum(weights,axis=1);total=cumulative[:,-1]
    assert (total>0).all()
    values=[ordered[np.argmax(cumulative>=q*total[:,None],axis=1)] for q in [.16,.5,.84]]
    point=[ordered[max(0,int(np.ceil(q*len(ordered)))-1)] for q in [.16,.5,.84]]
    return {'median_bias':values[1],'R68':(values[2]-values[0])/2},{'median_bias':point[1],'R68':(point[2]-point[0])/2}


def main():
    root=Path(__file__).resolve().parents[1];out=root/'workbook/stage21_energy_ml';art=root/'ml/artifacts/stage21'
    tick=time.perf_counter();cpu=time.process_time();cfg=yaml.safe_load((root/'ml/configs/prior.yaml').read_text())
    base=yaml.safe_load((root/'ml/configs/baseline.yaml').read_text());study=yaml.safe_load((root/cfg['reference_study']).read_text())
    with np.load(root/'ntuples/energy_ml_stage15/validation_truth.npz') as d:truth={k:d[k] for k in d.files if not k.endswith('_json')}
    y=truth['truth_E_GeV'];edges=np.array(cfg['energy_edges_GeV']);n=len(y);predictions={};runs=[];costs=[];endpoints=[];traces={};preprocessing=[];baseline_checks=[]
    assert n==13375 and len(set(zip(truth['run'],truth['eventID'])))==n
    common=None;weights=None
    for arch in cfg['architectures']:
        for mode in cfg['modes']:
            name=f'{arch}_{mode}';run=json.loads((out/name/'summary.json').read_text())
            study_saved=run['study'] if 'study' in run else json.loads((out/'training_config.json').read_text())['study']
            assert study_saved==cfg and not run['smoke'] and not run['calibration_test_challenge_evaluated']
            assert run['train_events']==54196 and run['validation_events']==n
            assert run['gpu']=='NVIDIA H100 NVL'
            w=run.get('weights',json.loads((out/'weights.json').read_text()) if (out/'weights.json').exists() else None)
            if weights is None:weights=w
            else:
                assert weights.keys()==w.keys()
                np.testing.assert_array_equal(weights['counts'],w['counts'])
                for key in weights:
                    if key!='counts':np.testing.assert_allclose(weights[key],w[key],rtol=1e-13,atol=1e-13)
            runs.append(run)
            meta=json.loads((art/name/'preprocessing.json').read_text())
            assert meta['features']==sum([base['feature_groups'][g] for g in base['feature_versions']['F5']],[])
            if common is None:common=meta
            preprocessing.append(dict(model=name,**compare_preprocessing(common,meta)))
            with np.load(art/name/'predictions.npz') as d:
                for k in ['run','eventID','truth_E_GeV']:np.testing.assert_array_equal(d[k],truth[k])
                if not predictions:groups=d['group']
                else:np.testing.assert_array_equal(d['group'],groups)
                predictions[name]=np.stack([d[f'seed_{i}'] for i in range(3)])
            assert np.isfinite(predictions[name]).all() and (predictions[name]>0).all()
            traces[name]=json.loads((out/name/'learning_traces.json').read_text())
            for r in read_table(out/name/'costs.tsv'):
                costs.append(dict(model=name,**r));trace=traces[name][f"seed_{r['seed_index']}"]
                values=trace['validation']['rmse'] if arch=='bdt' else [t['validation_mse'] for t in trace]
                assert len(values)==int(r['iterations']) and int(r['best_iteration'])==int(np.argmin(values))
                endpoints.append(dict(model=name,seed=r['seed'],iterations=r['iterations'],best_iteration=r['best_iteration'],stop_reason=r['stop_reason'],
                                      monitor_metric='RMSE' if arch=='bdt' else 'MSE',first_monitor=values[0],best_monitor=min(values),last_monitor=values[-1]))
        with np.load(root/f'ml/artifacts/stage16/{arch}_F5/predictions.npz') as d:
            for k in ['run','eventID','truth_E_GeV']:np.testing.assert_array_equal(d[k],truth[k])
            np.testing.assert_array_equal(d['group'],groups)
            for i in range(3):
                a=predictions[f'{arch}_UU'][i];b=d[f'seed_{i}']
                baseline_checks.append(dict(model=f'{arch}_UU',seed=cfg['seeds'][i],max_relative_difference=float(np.max(abs(a/b-1))),
                                            mean_absolute_relative_difference=float(np.mean(abs(a/b-1))),identical=bool(np.array_equal(a,b))))
    assert len(costs)==24
    write_table(out/'baseline_reproduction.tsv',baseline_checks);write_table(out/'preprocessing_checks.tsv',preprocessing)
    trajectories=[]
    for arch in cfg['architectures']:
        for left,right in [('UU','UF'),('FU','FF')]:
            for si in range(3):
                a=traces[f'{arch}_{left}'][f'seed_{si}'];b=traces[f'{arch}_{right}'][f'seed_{si}']
                a=a['train']['rmse'] if arch=='bdt' else [v['train_mse'] for v in a]
                b=b['train']['rmse'] if arch=='bdt' else [v['train_mse'] for v in b]
                common_length=min(len(a),len(b));difference=float(np.max(abs(np.array(a[:common_length])-b[:common_length])))
                trajectories.append(dict(reference=f'{arch}_{left}',model=f'{arch}_{right}',seed=cfg['seeds'][si],common_iterations=common_length,max_train_metric_difference=difference))
    write_table(out/'trajectory_checks.tsv',trajectories)
    losses={k:np.mean(np.log(p/y)**2,axis=0) for k,p in predictions.items()}
    macro,boot=group_bootstrap_losses(losses,y,groups,edges,cfg['bootstrap_replicates'],cfg['seeds'][0]);overview=[]
    for name,p in predictions.items():
        seed_macro=[np.sqrt(np.mean([np.mean(np.log(a[(y>=lo)&(y<hi)]/y[(y>=lo)&(y<hi)])**2) for lo,hi in zip(edges[:-1],edges[1:])])) for a in p]
        ci=np.quantile(boot[name],[.025,.975]);overview.append(dict(model=name,macro_log_RMSE=macro[name],macro_CI025=ci[0],macro_CI975=ci[1],seed_min=min(seed_macro),seed_max=max(seed_macro),integrated_log_RMSE=np.sqrt(losses[name].mean())))
    pairs=[(f'{a}_{l}',f'{a}_{r}') for a in cfg['architectures'] for l,r in cfg['main_pairs']]
    pairs += [(f'bdt_{m}',f'tabm_{m}') for m in ['UU','FU','FF']]
    gains=[]
    for left,right in pairs:
        ci=np.quantile(boot[right]-boot[left],[.025,.975]);gains.append(dict(reference=left,model=right,delta=macro[right]-macro[left],CI025=ci[0],CI975=ci[1]))
    interaction=[]
    for a in cfg['architectures']:
        v=boot[f'{a}_FF']-boot[f'{a}_FU']-boot[f'{a}_UF']+boot[f'{a}_UU'];ci=np.quantile(v,[.025,.975])
        interaction.append(dict(architecture=a,contrast='FF-FU-UF+UU',macro_delta=macro[f'{a}_FF']-macro[f'{a}_FU']-macro[f'{a}_UF']+macro[f'{a}_UU'],CI025=ci[0],CI975=ci[1]))
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
            for key,vectors_by_model in vectors.items():
                v=vectors_by_model[name];sums=np.bincount(gid[mask],weights=v[mask],minlength=ng);b=(draws@sums)[valid]/den[valid]
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
    for filename,rows in [('macro_summary.tsv',overview),('macro_gains.tsv',gains),('factor_interaction.tsv',interaction),('metrics.tsv',metrics),('stratified_gains.tsv',stratified),('nonlinear_gains.tsv',nonlinear),('costs.tsv',costs),('learning_endpoints.tsv',endpoints)]:write_table(out/filename,rows)
    fig,axes=plt.subplots(1,2,figsize=(15,5.5),layout='constrained')
    for ax,kind in zip(axes,['macro','integrated']):
        rows=gains if kind=='macro' else [r for r in stratified if r['stratum']=='all']
        delta=np.array([r['delta'] if kind=='macro' else r['log_RMSE_delta'] for r in rows]);low=np.array([r['CI025'] if kind=='macro' else r['log_RMSE_CI025'] for r in rows]);high=np.array([r['CI975'] if kind=='macro' else r['log_RMSE_CI975'] for r in rows])
        ax.errorbar(delta,range(len(rows)),xerr=[delta-low,high-delta],fmt='o',capsize=3);ax.axvline(0,color='gray',lw=1);ax.invert_yaxis()
        ax.set(yticks=range(len(rows)),yticklabels=[f"{r['model']} - {r['reference']}" for r in rows],xlabel=f'Difference in {kind} log-RMSE',title='95% paired source-group intervals')
    svg(fig,out/'prior_tradeoff.svg')
    fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained');centers=np.sqrt(edges[:-1]*edges[1:])
    for i,arch in enumerate(cfg['architectures']):
        for mode in cfg['modes']:
            chosen=[r for r in metrics if r['model']==f'{arch}_{mode}' and r['stratum']=='energy_GeV'];bias=[];tail=[]
            for lo,hi in zip(edges[:-1],edges[1:]):
                rr=[r for r in chosen if r['value']==f'{lo:g}_{hi:g}'];bias.append(np.mean([r['median_bias'] for r in rr]));tail.append(np.mean([r['tail_0p5'] for r in rr]))
            axes[i,0].plot(centers,bias,'o-',label=mode);axes[i,1].plot(centers,tail,'o-',label=mode)
        axes[i,0].axhline(0,color='gray',lw=1);axes[i,0].set(ylabel=f'{arch}: median relative bias');axes[i,1].set(ylabel=f'{arch}: P(abs(relative error)>0.5)')
        for ax in axes[i]:ax.set(xscale='log',xlabel='True neutrino energy [GeV]');ax.legend()
    svg(fig,out/'prior_response.svg')
    (out/'training_config.json').write_text(json.dumps(dict(study=cfg,reference_study=study,baseline=base),indent=2)+'\n')
    (out/'weights.json').write_text(json.dumps(weights,indent=2)+'\n')
    for run in runs:
        compact={k:v for k,v in run.items() if k not in ['study','weights']};compact['configuration_file']='../training_config.json';compact['weights_file']='../weights.json'
        (out/f"{run['architecture']}_{run['mode']}"/'summary.json').write_text(json.dumps(compact,indent=2)+'\n')
    summary=dict(models=len(predictions),fits=len(costs),train_events=54196,validation_events=n,source_groups=int(ng),total_fit_wall_s=sum(float(r['train_wall_s']) for r in costs),
                 worker_wall_sum_s=sum(r['wall_s'] for r in runs),worker_cpu_sum_s=sum(r['cpu_s'] for r in runs),worker_peak_rss_MiB=max(r['peak_rss_MiB'] for r in runs),
                 actual_gpus=[r['gpu'] for r in runs],time_stops=sum(r['stop_reason']=='time' for r in costs),calibration_test_challenge_evaluated=False,
                 report_wall_s=time.perf_counter()-tick,report_cpu_s=time.process_time()-cpu,report_peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
