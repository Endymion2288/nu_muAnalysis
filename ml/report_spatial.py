#!/usr/bin/env python3
"""Paired source-group validation of station information and its null."""
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
from scipy.stats import spearmanr

from report_robustness import group_bootstrap_losses, svg
from train_bdt import metric_values, write_table


def main():
    repo=Path(__file__).resolve().parents[1];out=repo/'workbook/stage18_energy_ml';art=repo/'ml/artifacts/stage18'
    tick=time.perf_counter();cpu=time.process_time();cfg=yaml.safe_load((repo/'ml/configs/spatial.yaml').read_text())
    predictions={k:[] for k in cfg['models']};costs=[];runs=[];f5_differences=[]
    with np.load(repo/'ntuples/energy_ml_stage15/validation_truth.npz') as d:truth={k:d[k] for k in d.files if not k.endswith('_json')}
    for i,seed in enumerate(cfg['seeds']):
        folder=out/f'seed_{i}';run=json.loads((folder/'summary.json').read_text())
        study=run['study'] if 'study' in run else json.loads((out/'training_config.json').read_text())
        assert study==cfg and not run['smoke'] and not run['calibration_test_challenge_evaluated'] and run['seed']==seed
        assert run['train_events']==54196 and run['validation_events']==13375;runs.append(run)
        with np.load(art/f'seed_{i}/predictions.npz') as d:
            for k in ['run','eventID','truth_E_GeV']:np.testing.assert_array_equal(d[k],truth[k])
            if i==0:groups=d['group']
            else:np.testing.assert_array_equal(groups,d['group'])
            for name in cfg['models']:
                value=d[name];assert np.isfinite(value).all() and (value>0).all();predictions[name].append(value)
        with np.load(repo/'ml/artifacts/stage16/bdt_F5/predictions.npz') as previous:
            np.testing.assert_array_equal(previous['run'],truth['run']);np.testing.assert_array_equal(previous['eventID'],truth['eventID'])
            difference=float(np.max(abs(predictions['F5'][-1]/previous[f'seed_{i}']-1)))
            np.testing.assert_allclose(predictions['F5'][-1],previous[f'seed_{i}'],rtol=2e-5,atol=.001)
            f5_differences.append(difference)
        costs += [dict(seed_index=i,**r) for r in csv.DictReader((folder/'costs.tsv').open(),delimiter='\t')]
    y=truth['truth_E_GeV'];edges=np.array(cfg['energy_edges_GeV']);n=len(y)
    losses={k:np.mean(np.log(np.array(v)/y)**2,axis=0) for k,v in predictions.items()}
    macro,boot=group_bootstrap_losses(losses,y,groups,edges,cfg['bootstrap_replicates'],cfg['seeds'][0])
    summary=[];metrics=[]
    for name,values in predictions.items():
        single=[np.sqrt(np.mean([np.mean(np.log(a[(y>=lo)&(y<hi)]/y[(y>=lo)&(y<hi)])**2) for lo,hi in zip(edges[:-1],edges[1:])])) for a in values]
        ci=np.quantile(boot[name],[.025,.975])
        summary.append(dict(model=name,macro_RMS_over_seeds=macro[name],macro_CI025=ci[0],macro_CI975=ci[1],
                            macro_seed_min=min(single),macro_seed_max=max(single),integrated_RMS_over_seeds=np.sqrt(losses[name].mean())))
    pairs=[('F5','counts'),('counts','moments'),('reassigned','moments'),('counts','centroids'),('counts','widths'),('moments','tangent'),('counts','reassigned')]
    gains=[]
    for left,right in pairs:
        ci=np.quantile(boot[right]-boot[left],[.025,.975])
        gains.append(dict(reference=left,model=right,delta=macro[right]-macro[left],CI025=ci[0],CI975=ci[1]))
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
    stratified=[]
    for label,value,mask in masks:
        counts=np.bincount(gid[mask],minlength=ng);den=draws@counts;valid=den>0
        centers={};samples={}
        for name,values in predictions.items():
            centers[name]={};samples[name]={}
            for i,pred in enumerate(values):metrics.append(dict(model=name,seed=cfg['seeds'][i],stratum=label,value=value,**metric_values(y,pred,mask)))
            for key,model_vectors in vectors.items():
                v=model_vectors[name];sums=np.bincount(gid[mask],weights=v[mask],minlength=ng)
                c=v[mask].mean();b=(draws@sums)[valid]/den[valid]
                centers[name][key]=np.sqrt(c) if key=='log_RMSE' else c;samples[name][key]=np.sqrt(b) if key=='log_RMSE' else b
        for left,right in pairs:
            row=dict(stratum=label,value=value,N=int(mask.sum()),source_groups=int((counts>0).sum()),reference=left,model=right,bootstrap_valid=int(valid.sum()))
            for key in vectors:
                ci=np.quantile(samples[right][key]-samples[left][key],[.025,.975])
                row.update({f'{key}_reference':centers[left][key],f'{key}_model':centers[right][key],
                            f'{key}_delta':centers[right][key]-centers[left][key],f'{key}_CI025':ci[0],f'{key}_CI975':ci[1]})
            stratified.append(row)
    write_table(out/'macro_summary.tsv',summary);write_table(out/'macro_gains.tsv',gains)
    write_table(out/'metrics.tsv',metrics);write_table(out/'stratified_gains.tsv',stratified);write_table(out/'costs.tsv',costs)
    profiles=[]
    with np.load(repo/'ntuples/energy_ml_stage18/validation.npz') as d:
        np.testing.assert_array_equal(d['run'],truth['run']);np.testing.assert_array_equal(d['eventID'],truth['eventID'])
        station_counts=d['counts'].reshape(n,4,3).sum(axis=2);station_moments=d['moments'].reshape(n,4,5)
        global_moments=d['global_moments']
    for label,value,mask in masks:
        for station in range(4):
            count=station_counts[mask,station];shape=station_moments[mask,station]
            row=dict(stratum=label,value=value,station=station,N=int(mask.sum()),empty=int((count==0).sum()),
                     median_energy_GeV=float(np.median(y[mask])),median_y=float(np.median(ylep[mask])),
                     median_points=float(np.median(count)),mean_points=float(count.mean()))
            for j,key in enumerate(['mean_x_mm','mean_y_mm','rms_x_mm','rms_y_mm','cov_xy_mm2']):row[f'median_{key}']=float(np.nanmedian(shape[:,j]))
            profiles.append(row)
    write_table(out/'station_profiles.tsv',profiles)
    fraction=station_counts[:,0]/station_counts.sum(axis=1)
    occupancy=dict(N=n,IFT_fraction_event_quantiles=dict(zip(['q025','q25','median','q75','q975'],np.quantile(fraction,[.025,.25,.5,.75,.975]).tolist())),
                   events_with_no_IFT=int((station_counts[:,0]==0).sum()),each_station_nonempty_events=(station_counts>0).sum(axis=0).tolist())
    (out/'occupancy_diagnostics.json').write_text(json.dumps(occupancy,indent=2)+'\n')
    redundancy=[]
    with np.load(repo/'ntuples/energy_ml_stage12/dataset/validation.npz') as d:
        np.testing.assert_array_equal(d['run'],truth['run']);np.testing.assert_array_equal(d['eventID'],truth['eventID'])
        for station in range(4):
            correlation=float(spearmanr(station_counts[:,station],d[f'nClusters{station}']).statistic)
            redundancy.append(dict(relation=f'station{station}_points_vs_clusters',subset='all',N=n,statistic='Spearman rho',value=correlation))
    for subset,select in [('nonempty_IFT',station_counts[:,0]>0),('IFT_fraction_ge_0p8',fraction>=.8),('IFT_fraction_le_0p2',(fraction<=.2)&(station_counts[:,0]>0))]:
        for left,right,label in [(0,0,'mean_x'),(1,2,'mean_y'),(2,1,'rms_x'),(3,3,'rms_y')]:
            correlation=float(np.corrcoef(station_moments[select,0,left],global_moments[select,right])[0,1])
            redundancy.append(dict(relation=f'IFT_vs_global_{label}',subset=subset,N=int(select.sum()),statistic='Pearson r',value=correlation))
    write_table(out/'redundancy_diagnostics.tsv',redundancy)
    endpoints=[]
    for i in range(3):
        traces=json.loads((out/f'seed_{i}/learning_traces.json').read_text())
        for name,h in traces.items():
            best=int(next(r['best_iteration'] for r in costs if r['model']==name and int(r['seed_index'])==i))
            endpoints.append(dict(seed_index=i,model=name,best_iteration=best,train_rmse=h['train']['rmse'][best],validation_rmse=h['validation']['rmse'][best]))
    write_table(out/'learning_endpoints.tsv',endpoints)
    fig,axes=plt.subplots(1,2,figsize=(12,4),layout='constrained')
    names=cfg['models'];v=np.array([macro[k] for k in names]);ci=np.array([np.quantile(boot[k],[.025,.975]) for k in names])
    axes[0].errorbar(range(len(names)),v,yerr=[v-ci[:,0],ci[:,1]-v],fmt='o',capsize=4)
    axes[0].set(xticks=range(len(names)),xticklabels=names,ylabel='Macro log-RMSE',title='Unit MC; 3 seeds; tuned validation');axes[0].tick_params(axis='x',rotation=30)
    for name in ['F5','counts','moments','reassigned']:
        values=[]
        for lo,hi in zip(cfg['y_edges'][:-1],cfg['y_edges'][1:]):values.append(np.sqrt(losses[name][(ylep>=lo)&(ylep<hi)].mean()))
        axes[1].plot((np.array(cfg['y_edges'][:-1])+cfg['y_edges'][1:])/2,values,'o-',label=name)
    axes[1].set(xlabel='Leptonic y (diagnostic only)',ylabel='Log-RMSE',title='All original selected events');axes[1].legend()
    svg(fig,out/'spatial_summary.svg')
    fig,ax=plt.subplots(figsize=(9,4),layout='constrained')
    delta=np.array([r['delta'] for r in gains]);lower=np.array([r['CI025'] for r in gains]);upper=np.array([r['CI975'] for r in gains])
    ax.errorbar(delta,range(len(gains)),xerr=[delta-lower,upper-delta],fmt='o',capsize=4)
    ax.axvline(0,color='gray',lw=1);ax.invert_yaxis()
    ax.set(yticks=range(len(gains)),yticklabels=[f"{r['model']} - {r['reference']}" for r in gains],
           xlabel='Difference in macro log-RMSE (negative means improvement)',title='Paired 95% source-group intervals; tuned validation')
    svg(fig,out/'spatial_paired_gains.svg')
    (out/'training_config.json').write_text(json.dumps(cfg,indent=2)+'\n')
    for i,run in enumerate(runs):
        run={k:v for k,v in run.items() if k!='study'};run['configuration_file']='../training_config.json'
        (out/f'seed_{i}/summary.json').write_text(json.dumps(run,indent=2)+'\n')
    record=dict(models=7,fits=len(costs),seeds=cfg['seeds'],train_events=54196,validation_events=n,source_groups=int(ng),
                F5_max_relative_difference_from_stage16=f5_differences,fit_wall_sum_s=sum(float(r['train_wall_s']) for r in costs),
                worker_wall_sum_s=sum(r['wall_s'] for r in runs),worker_cpu_sum_s=sum(r['cpu_s'] for r in runs),
                worker_peak_rss_MiB=max(r['peak_rss_MiB'] for r in runs),actual_gpus=[r['gpu'] for r in runs],
                calibration_test_challenge_evaluated=False,report_wall_s=time.perf_counter()-tick,report_cpu_s=time.process_time()-cpu,
                report_peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    (out/'summary.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))


if __name__=='__main__':main()
