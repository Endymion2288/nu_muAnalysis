#!/usr/bin/env python3
"""Physics-stratified paired validation of full SpacePoint set models."""
import csv
import json
import resource
import time
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import torch
import yaml

from report_robustness import group_bootstrap_losses,svg
from train_bdt import write_table,metric_values
from check_set_preprocessing import compare_preprocessing


def main():
    root=Path(__file__).resolve().parents[1];out=root/'workbook/stage19_energy_ml';art=root/'ml/artifacts/stage19'
    tick=time.perf_counter();cpu=time.process_time();cfg=yaml.safe_load((root/'ml/configs/sets.yaml').read_text())
    baseline=yaml.safe_load((root/'ml/configs/baseline.yaml').read_text());geo=yaml.safe_load((root/cfg['geometry_config']).read_text())
    with np.load(root/'ntuples/energy_ml_stage15/validation_truth.npz') as d:truth={k:d[k] for k in d.files if not k.endswith('_json')}
    y=truth['truth_E_GeV'];n=len(y);edges=np.array(cfg['energy_edges_GeV']);predictions={};costs=[];selected=[];runs=[];endpoints=[];common_preprocessing=None
    assert len(set(zip(truth['run'],truth['eventID'])))==n
    for name in cfg['models']:
        run=json.loads((out/name/'summary.json').read_text())
        study=run['study'] if 'study' in run else json.loads((out/'training_config.json').read_text())['study']
        assert study==cfg and not run['smoke'] and not run['calibration_test_challenge_evaluated']
        assert run['train_events']==54196 and run['validation_events']==13375 and run['train_points']==13204073 and run['validation_points']==3083555
        runs.append(run)
        with np.load(art/name/'predictions.npz') as d:
            for k in ['run','eventID','truth_E_GeV']:np.testing.assert_array_equal(d[k],truth[k])
            if not predictions:groups=d['group']
            else:np.testing.assert_array_equal(groups,d['group'])
            predictions[name]=[d[f'seed_{i}'] for i in range(3)]
        ckpt=torch.load(art/name/'best.pt',map_location='cpu',weights_only=True)
        assert ckpt['study']==cfg and ckpt['variant']==name and ckpt['trial']==cfg['trials'][run['winner_trial']]
        if common_preprocessing is None:common_preprocessing=ckpt['preprocessing']
        else:compare_preprocessing(common_preprocessing,ckpt['preprocessing'])
        traces=json.loads((out/name/'learning_traces.json').read_text())
        for r in csv.DictReader((out/name/'costs.tsv').open(),delimiter='\t'):
            chosen=r['phase']=='repeat' or int(r['trial'])==run['winner_trial'];row=dict(model=name,selected=int(chosen),**r)
            costs.append(row)
            if chosen:selected.append(row)
            trace=traces[r['fit']];assert len(trace)==int(r['epochs'])
            best=trace[int(r['best_epoch'])]
            assert best['validation_mse']==min(t['validation_mse'] for t in trace)
            endpoints.append(dict(model=name,fit=r['fit'],selected=int(chosen),epochs=len(trace),
                                  best_epoch=int(r['best_epoch']),stop_reason=r['stop_reason'],
                                  first_validation_mse=trace[0]['validation_mse'],best_validation_mse=best['validation_mse'],
                                  last_validation_mse=trace[-1]['validation_mse'],
                                  last_dropout_on_train_mse=trace[-1]['train_mse']))
    for ref in ['bdt_counts','bdt_moments']:
        predictions[ref]=[];key=ref.removeprefix('bdt_')
        for i in range(3):
            with np.load(root/f'ml/artifacts/stage18/seed_{i}/predictions.npz') as d:
                for k in ['run','eventID','truth_E_GeV']:np.testing.assert_array_equal(d[k],truth[k])
                np.testing.assert_array_equal(d['group'],groups);predictions[ref].append(d[key])
    with np.load(root/'ml/artifacts/stage16/tabm_F5/predictions.npz') as d:
        for k in ['run','eventID','truth_E_GeV']:np.testing.assert_array_equal(d[k],truth[k])
        np.testing.assert_array_equal(d['group'],groups);predictions['tabm_F5']=[d[f'seed_{i}'] for i in range(3)]
    losses={name:np.mean(np.log(np.array(values)/y)**2,axis=0) for name,values in predictions.items()}
    for name,values in predictions.items():assert np.isfinite(values).all() and (np.array(values)>0).all()
    macro,boot=group_bootstrap_losses(losses,y,groups,edges,cfg['bootstrap_replicates'],cfg['seeds'][0]);overview=[]
    for name,values in predictions.items():
        single=[]
        for a in values:single.append(np.sqrt(np.mean([np.mean(np.log(a[(y>=lo)&(y<hi)]/y[(y>=lo)&(y<hi)])**2) for lo,hi in zip(edges[:-1],edges[1:])])))
        ci=np.quantile(boot[name],[.025,.975])
        overview.append(dict(model=name,macro_RMS_over_seeds=macro[name],macro_CI025=ci[0],macro_CI975=ci[1],macro_seed_min=min(single),macro_seed_max=max(single),integrated_RMS_over_seeds=np.sqrt(losses[name].mean())))
    pairs=[('summary','full'),('reassigned','full'),('summary','global'),('global','full'),('summary','reassigned'),
           ('bdt_moments','full'),('tabm_F5','full'),('tabm_F5','summary')]
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
    vectors={'log_RMSE':losses}
    for key,fun in [('tail_0p5',lambda r:abs(r)>.5),('tail_1',lambda r:abs(r)>1),('mean_bias',lambda r:r)]:
        vectors[key]={k:np.mean(fun(np.array(v)/y-1),axis=0) for k,v in predictions.items()}
    stratified=[];metrics=[]
    for label,value,mask in masks:
        counts=np.bincount(gid[mask],minlength=ng);den=draws@counts;valid=den>0;center={};samples={}
        for name,values in predictions.items():
            center[name]={};samples[name]={}
            for i,a in enumerate(values):
                relative=a[mask]/y[mask]-1
                metrics.append(dict(model=name,seed=cfg['seeds'][i],stratum=label,value=value,**metric_values(y,a,mask),
                                    under_0p5=float(np.mean(relative<-.5)),over_0p5=float(np.mean(relative>.5))))
            for key,model_vectors in vectors.items():
                v=model_vectors[name];sums=np.bincount(gid[mask],weights=v[mask],minlength=ng);c=v[mask].mean();b=(draws@sums)[valid]/den[valid]
                center[name][key]=np.sqrt(c) if key=='log_RMSE' else c;samples[name][key]=np.sqrt(b) if key=='log_RMSE' else b
        for left,right in pairs:
            row=dict(stratum=label,value=value,N=int(mask.sum()),source_groups=int((counts>0).sum()),bootstrap_valid=int(valid.sum()),reference=left,model=right)
            for key in vectors:
                ci=np.quantile(samples[right][key]-samples[left][key],[.025,.975])
                row.update({f'{key}_reference':center[left][key],f'{key}_model':center[right][key],f'{key}_delta':center[right][key]-center[left][key],f'{key}_CI025':ci[0],f'{key}_CI975':ci[1]})
            stratified.append(row)
    write_table(out/'macro_summary.tsv',overview);write_table(out/'macro_gains.tsv',gains);write_table(out/'stratified_gains.tsv',stratified)
    write_table(out/'metrics.tsv',metrics);write_table(out/'costs.tsv',costs);write_table(out/'selected_fits.tsv',selected)
    write_table(out/'learning_endpoints.tsv',endpoints)
    fig,axes=plt.subplots(1,2,figsize=(13,4.5),layout='constrained')
    delta=np.array([r['delta'] for r in gains]);low=np.array([r['CI025'] for r in gains]);high=np.array([r['CI975'] for r in gains])
    axes[0].errorbar(delta,range(len(gains)),xerr=[delta-low,high-delta],fmt='o',capsize=4)
    axes[0].axvline(0,color='gray',lw=1);axes[0].invert_yaxis();axes[0].set(yticks=range(len(gains)),yticklabels=[f"{r['model']} - {r['reference']}" for r in gains],xlabel='Difference in macro log-RMSE',title='Paired 95% source-group intervals')
    for name in ['summary','global','full','reassigned','tabm_F5']:
        values=[np.sqrt(losses[name][(ylep>=lo)&(ylep<hi)].mean()) for lo,hi in zip(cfg['y_edges'][:-1],cfg['y_edges'][1:])]
        axes[1].plot((np.array(cfg['y_edges'][:-1])+cfg['y_edges'][1:])/2,values,'o-',label=name)
    axes[1].set(xlabel='Leptonic y (diagnostic only)',ylabel='Log-RMSE',title='Unit MC; tuned validation');axes[1].legend();svg(fig,out/'set_comparison.svg')
    fig,axes=plt.subplots(1,2,figsize=(12,4),layout='constrained')
    centers=np.sqrt(edges[:-1]*edges[1:])
    for name in ['summary','global','full','tabm_F5']:
        rows=[r for r in metrics if r['model']==name and r['stratum']=='energy_GeV']
        bias=[];tail=[]
        for lo,hi in zip(edges[:-1],edges[1:]):
            bin_rows=[r for r in rows if r['value']==f'{lo:g}_{hi:g}']
            bias.append(np.mean([r['median_bias'] for r in bin_rows]));tail.append(np.mean([r['tail_0p5'] for r in bin_rows]))
        axes[0].plot(centers,bias,'o-',label=name);axes[1].plot(centers,tail,'o-',label=name)
    axes[0].axhline(0,color='gray',lw=1);axes[0].set(ylabel='Median relative bias (seed mean)');axes[1].set(ylabel='P(abs(relative error) > 0.5)')
    for ax in axes:ax.set(xscale='log',xlabel='True neutrino energy [GeV]');ax.legend()
    svg(fig,out/'energy_response.svg')
    (out/'training_config.json').write_text(json.dumps(dict(study=cfg,baseline=baseline,geometry=geo),indent=2)+'\n')
    for run in runs:
        compact={k:v for k,v in run.items() if k!='study'};compact['configuration_file']='../training_config.json'
        (out/run['variant']/'summary.json').write_text(json.dumps(compact,indent=2)+'\n')
    record=dict(models=4,reference_models=3,fits=len(costs),selected_fits=len(selected),train_events=54196,validation_events=n,source_groups=int(ng),
                total_fit_wall_s=sum(float(r['train_wall_s']) for r in costs),worker_wall_sum_s=sum(r['wall_s'] for r in runs),worker_cpu_sum_s=sum(r['cpu_s'] for r in runs),
                worker_peak_rss_MiB=max(r['peak_rss_MiB'] for r in runs),actual_gpus=[r['gpu'] for r in runs],budget_stops=sum(r['stop_reason']=='time' for r in costs),
                calibration_test_challenge_evaluated=False,report_wall_s=time.perf_counter()-tick,report_cpu_s=time.process_time()-cpu,report_peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    (out/'summary.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))


if __name__=='__main__':main()
