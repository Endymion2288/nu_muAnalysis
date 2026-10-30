#!/usr/bin/env python3
"""Development-only paired architecture and physics comparisons for stage16."""
import argparse
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

from report_robustness import group_bootstrap_losses, svg
from train_bdt import metric_values, write_table


def read_npz(path):
    with np.load(path) as d:return {k:d[k] for k in d.files if not k.endswith('_json')}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
    args=p.parse_args();repo=args.repo;out=repo/'workbook/stage16_energy_ml';art=repo/'ml/artifacts/stage16'
    tick=time.perf_counter();cpu=time.process_time()
    cfg=yaml.safe_load((repo/'ml/configs/tabular.yaml').read_text())
    baseline=yaml.safe_load((repo/'ml/configs/baseline.yaml').read_text())
    truth=read_npz(repo/'ntuples/energy_ml_stage15/validation_truth.npz')
    y=truth['truth_E_GeV'];n=len(y);edges=np.array(cfg['energy_edges_GeV'])
    predictions={};runs=[];costs=[];selection=[];traces={}
    for architecture in cfg['architectures']:
        for version in cfg['versions']:
            name=f'{architecture}_{version}';folder=out/name
            run=json.loads((folder/'summary.json').read_text())
            configuration=json.loads((folder/run['configuration_file']).read_text()) if 'configuration_file' in run else run
            if configuration['study']!=cfg or configuration['baseline']!=baseline or run['smoke'] or run['calibration_test_challenge_evaluated']:
                raise RuntimeError(f'Provenance mismatch: {name}')
            if run['train_events']!=54196 or run['validation_events']!=13375:raise RuntimeError('Sample changed')
            runs.append(run);data=read_npz(art/name/'predictions.npz')
            for k in ['run','eventID','truth_E_GeV']:np.testing.assert_array_equal(data[k],truth[k])
            if predictions:np.testing.assert_array_equal(groups,data['group'])
            groups=data['group'];predictions[name]=[data[f'seed_{i}'] for i in range(3)]
            rows=list(csv.DictReader((folder/'costs.tsv').open(),delimiter='\t'))
            winner=run['winner_trial']
            for r in rows:
                chosen=(r['phase']=='repeat' or int(r['trial'])==winner)
                costs.append(dict(model=name,selected=int(chosen),**r))
                if chosen:selection.append(dict(model=name,seed_index=r['seed_index'],trial=r['trial'],
                                                train_wall_s=r['train_wall_s'],stop_reason=r['stop_reason'],
                                                iterations=r['iterations'],best_iteration=r['best_iteration']))
            traces[name]=json.loads((folder/'learning_traces.json').read_text())
    # Legacy models diagnose total pipeline changes; not an isolated preprocessing test.
    for version in cfg['versions']:
        predictions[f'legacy_{version}']=[]
        for i in range(3):
            d=read_npz(repo/f'ml/artifacts/stage14/seed_{i}/predictions.npz')
            for k in ['run','eventID','truth_E_GeV','group']:np.testing.assert_array_equal(d[k],data[k])
            predictions[f'legacy_{version}'].append(d[f'd5_1600__{version}'])
    losses={k:np.mean([np.log(a/y)**2 for a in values],axis=0) for k,values in predictions.items()}
    tails={k:np.mean([abs(a/y-1)>.5 for a in values],axis=0) for k,values in predictions.items()}
    extreme_tails={k:np.mean([abs(a/y-1)>1 for a in values],axis=0) for k,values in predictions.items()}
    biases={k:np.mean([a/y-1 for a in values],axis=0) for k,values in predictions.items()}
    macro,boots=group_bootstrap_losses(losses,y,groups,edges,cfg['bootstrap_replicates'],cfg['seeds'][0])
    overview=[];metrics=[]
    for name,values in predictions.items():
        scores=[]
        for i,a in enumerate(values):
            error=np.log(a/y)**2
            score=np.sqrt(np.mean([error[(y>=lo)&(y<hi)].mean() for lo,hi in zip(edges[:-1],edges[1:])]))
            scores.append(score)
            metrics.append(dict(model=name,seed=cfg['seeds'][i],stratum='all',value='all',**metric_values(y,a,np.ones(n,dtype=bool))))
        ci=np.quantile(boots[name],[.025,.975])
        overview.append(dict(model=name,macro_seed_mean=float(np.mean(scores)),macro_seed_min=min(scores),macro_seed_max=max(scores),
                             macro_RMS_over_seeds=macro[name],macro_CI025=ci[0],macro_CI975=ci[1],
                             integrated_RMS_over_seeds=float(np.sqrt(losses[name].mean())),
                             tail_0p5_seed_mean=float(tails[name].mean()),tail_1_seed_mean=float(extreme_tails[name].mean()),
                             mean_bias_seed_mean=float(biases[name].mean())))
    pairs=[(f'bdt_{v}',f'{a}_{v}') for v in cfg['versions'] for a in ['mlp','resnet','tabm']]
    pairs += [(f'{a}_F3',f'{a}_F5') for a in cfg['architectures']]
    pairs += [(f'legacy_{v}',f'bdt_{v}') for v in cfg['versions']]
    macro_gains=[]
    for left,right in pairs:
        ci=np.quantile(boots[right]-boots[left],[.025,.975])
        macro_gains.append(dict(reference=left,model=right,reference_score=macro[left],model_score=macro[right],
                                delta=macro[right]-macro[left],CI025=ci[0],CI975=ci[1]))
    matched=truth['lead_primary_parent_confirmed'];ylep=truth['y_lepton'];z=truth['vertex_z_mm']
    masks=[('all','all',np.ones(n,dtype=bool)),('matching','primary_confirmed',matched),('matching','other_leading',~matched),
           ('truth_region','FASERnu_box',z< -1950),('truth_region','lead_block',z>= -1950)]
    masks += [('y_lepton',f'{lo:g}_{hi:g}',(ylep>=lo)&(ylep<hi)) for lo,hi in zip(cfg['y_edges'][:-1],cfg['y_edges'][1:])]
    masks += [('y_primary_confirmed',f'ge_{lo:g}',matched&(ylep>=lo)) for lo in [.6,.8]]
    response=truth['reco_p_GeV']/truth['primary_p_GeV']
    masks += [('response','primary_abs_p_ratio_minus_1_le_0p1',matched&(abs(response-1)<=.1)),
              ('response','primary_abs_p_ratio_minus_1_gt_0p1',matched&(abs(response-1)>.1))]
    masks += [('energy_GeV',f'{lo:g}_{hi:g}',(y>=lo)&(y<hi)) for lo,hi in zip(edges[:-1],edges[1:])]
    masks += [('run',str(int(run)),truth['run']==run) for run in np.unique(truth['run'])]
    _,gid=np.unique(groups,return_inverse=True);ng=gid.max()+1
    rng=np.random.default_rng(cfg['seeds'][0]);draws=rng.multinomial(ng,np.full(ng,1/ng),size=cfg['bootstrap_replicates'])
    gains=[]
    for label,value,mask in masks:
        counts=np.bincount(gid[mask],minlength=ng);den=draws@counts;valid=den>0
        center={};resamples={}
        for name,values in predictions.items():
            center[name]={};resamples[name]={}
            for key,vectors in [('log_RMSE',losses),('tail_0p5',tails),('tail_1',extreme_tails),('mean_bias',biases)]:
                c=float(vectors[name][mask].mean())
                sums=np.bincount(gid[mask],weights=vectors[name][mask],minlength=ng)
                samples=(draws@sums)[valid]/den[valid]
                center[name][key]=np.sqrt(c) if key=='log_RMSE' else c
                resamples[name][key]=np.sqrt(samples) if key=='log_RMSE' else samples
            if label!='all':
                for i,a in enumerate(values):metrics.append(dict(model=name,seed=cfg['seeds'][i],stratum=label,value=value,**metric_values(y,a,mask)))
        for left,right in pairs:
            row=dict(stratum=label,value=value,N=int(mask.sum()),source_groups=int((counts>0).sum()),
                     reference=left,model=right,bootstrap_valid=int(valid.sum()))
            for key in ['log_RMSE','tail_0p5','tail_1','mean_bias']:
                ci=np.quantile(resamples[right][key]-resamples[left][key],[.025,.975])
                row.update({f'{key}_reference':center[left][key],f'{key}_model':center[right][key],
                            f'{key}_delta':center[right][key]-center[left][key],f'{key}_CI025':ci[0],f'{key}_CI975':ci[1]})
            gains.append(row)
    write_table(out/'macro_summary.tsv',overview);write_table(out/'macro_gains.tsv',macro_gains)
    write_table(out/'stratified_gains.tsv',gains);write_table(out/'metrics.tsv',metrics)
    write_table(out/'all_costs.tsv',costs);write_table(out/'selected_fits.tsv',selection)
    # Learning endpoints expose budget truncation and training/validation gaps.
    endpoints=[]
    for run in runs:
        name=f"{run['architecture']}_{run['version']}"
        with (art/name/'preprocessing.json').open() as f:spread=json.load(f)['target_spread']
        for key,trace in traces[name].items():
            if isinstance(trace,dict):tr=[a*a for a in trace['train']['rmse']];va=[a*a for a in trace['validation']['rmse']]
            else:tr=[a['train_mse'] for a in trace];va=[a['validation_mse'] for a in trace]
            best_idx=int(np.argmin(va))
            endpoints.append(dict(model=name,fit=key,best_iteration=best_idx,
                                  train_trace_kind='full_train_eval' if isinstance(trace,dict) else 'dropout_on_online_epoch_average',
                                  train_log_RMSE_at_best=float(np.sqrt(tr[best_idx])*spread),
                                  validation_log_RMSE_at_best=float(np.sqrt(va[best_idx])*spread),
                                  final_train_log_RMSE=float(np.sqrt(tr[-1])*spread),final_validation_log_RMSE=float(np.sqrt(va[-1])*spread)))
    write_table(out/'learning_endpoints.tsv',endpoints)
    colors=dict(bdt='#444444',mlp='#377eb8',resnet='#4daf4a',tabm='#e41a1c')
    fig,axes=plt.subplots(2,2,figsize=(11,8),layout='constrained')
    for arch in cfg['architectures']:
        name=f'{arch}_F3';c=colors[arch]
        rms=[];bias=[];tail=[]
        for lo,hi in zip(edges[:-1],edges[1:]):
            m=(y>=lo)&(y<hi);rms.append(np.sqrt(losses[name][m].mean()))
            bias.append(np.mean([np.median(a[m]/y[m]-1) for a in predictions[name]]));tail.append(tails[name][m].mean())
        x=np.sqrt(edges[:-1]*edges[1:])
        for ax,values in [(axes[0,0],rms),(axes[1,0],bias),(axes[1,1],tail)]:ax.plot(x,values,'o-',color=c,label=arch)
        yrms=[np.sqrt(losses[name][(ylep>=lo)&(ylep<hi)].mean()) for lo,hi in zip(cfg['y_edges'][:-1],cfg['y_edges'][1:])]
        axes[0,1].plot((np.array(cfg['y_edges'][:-1])+np.array(cfg['y_edges'][1:]))/2,yrms,'o-',color=c,label=arch)
    axes[0,0].set(ylabel='Log-RMSE',title='Same F3 information; unit MC weights')
    axes[0,1].set(xlabel='Leptonic y (diagnostic only)',ylabel='Log-RMSE',title='Original leading definition; all events retained')
    axes[1,0].axhline(0,color='gray',lw=1);axes[1,0].set(ylabel='Median relative bias (mean over seeds)')
    axes[1,1].set(ylabel=r'$P(|\hat E/E-1|>0.5)$')
    for ax in [axes[0,0],axes[1,0],axes[1,1]]:ax.set(xscale='log',xlabel=r'True $E_\nu$ [GeV]')
    axes[0,0].legend();svg(fig,out/'physics_comparison.svg')
    fig,ax=plt.subplots(figsize=(9,4),layout='constrained')
    for j,v in enumerate(cfg['versions']):
        rs=[next(r for r in overview if r['model']==f'{a}_{v}') for a in cfg['architectures']]
        values=np.array([r['macro_RMS_over_seeds'] for r in rs])
        ax.errorbar(np.arange(4)+(j-.5)*.15,values,yerr=[values-np.array([r['macro_CI025'] for r in rs]),
                    np.array([r['macro_CI975'] for r in rs])-values],fmt='o',capsize=4,label=v)
    ax.set(xticks=np.arange(4),xticklabels=cfg['architectures'],ylabel='Macro log-RMSE',title='3 seeds; 95% source-group bootstrap; tuned validation')
    ax.legend();svg(fig,out/'architecture_summary.svg')
    (out/'training_config.json').write_text(json.dumps(dict(study=cfg,baseline=baseline),indent=2)+'\n')
    for run in runs:
        name=f"{run['architecture']}_{run['version']}"
        compact={k:v for k,v in run.items() if k not in ['study','baseline']};compact['configuration_file']='../training_config.json'
        (out/name/'summary.json').write_text(json.dumps(compact,indent=2)+'\n')
    summary=dict(models=8,fits=len(costs),train_events=54196,validation_events=n,source_groups=int(ng),
                 total_worker_wall_s=sum(r['wall_s'] for r in runs),total_worker_cpu_s=sum(r['cpu_s'] for r in runs),
                 max_worker_rss_MiB=max(r['peak_rss_MiB'] for r in runs),
                 total_fit_wall_s=sum(float(r['train_wall_s']) for r in costs),
                 budget_stops=sum(r['stop_reason']=='time' for r in costs),
                 calibration_test_challenge_evaluated=False,report_wall_s=time.perf_counter()-tick,report_cpu_s=time.process_time()-cpu,
                 report_peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
