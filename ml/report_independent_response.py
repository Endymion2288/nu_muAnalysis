#!/usr/bin/env python3
"""Report independent MC layers with paired trial blocks and oracle diagnostics."""
import argparse
import json
import time
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import norm

from closure import read_table, write_table
from independent_response import LAYERS, config
from report_closure import save_svg


PAIRS = [(1, 0), (2, 0), (3, 1), (3, 0)]


def block_stat(values):
    blocks = np.nanmean(values.reshape(len(values), -1), axis=1)
    blocks = blocks[np.isfinite(blocks)]
    mean = float(blocks.mean()); se = float(blocks.std(ddof=1)/np.sqrt(len(blocks)))
    return dict(value=mean, mc_se=se, mc_low95=mean-1.96*se, mc_high95=mean+1.96*se, trial_blocks=len(blocks))


def main():
    parser = argparse.ArgumentParser(__doc__); parser.add_argument('--compact', action='store_true'); args = parser.parse_args()
    tick = time.perf_counter(); root=Path(__file__).resolve().parents[1]; cfg=config(root); out=root/'workbook/stage27_energy_ml'
    old=json.loads((out/'summary.json').read_text()) if (out/'summary.json').exists() else {}
    arrays={}; runs={}; intervals=[]; failures=[]
    for model,spec in cfg['models'].items():
        for seed in spec['seeds']:
            for ai,alpha in enumerate(cfg['alphas']):
                key=f'{model}/seed_{seed}/alpha_{ai}'; folder=out/key
                runs[key]=json.loads((folder/'summary.json').read_text()) if (folder/'summary.json').exists() else old['runs'][key]
                run=runs[key];assert run['events']==13375 and run['replicates']==cfg['replicates'] and not run['smoke']
                assert not run['calibration_test_challenge_evaluated']
                for name,rows in [('intervals',intervals),('failures',failures)]:
                    if (folder/f'{name}.tsv').exists(): rows.extend(read_table(folder/f'{name}.tsv'))
                with np.load(root/f'ml/artifacts/stage27/{key}/independent_inference.npz') as z:
                    arrays[model,seed,ai]={k:z[k] for k in z.files}
    if not intervals and (out/'intervals.tsv').exists(): intervals=read_table(out/'intervals.tsv')
    if not failures and (out/'failures.tsv').exists(): failures=read_table(out/'failures.tsv')
    metrics=[];summary_metrics=[];cover=[];comparisons=[];sd_comparisons=[];tests=[]
    rng=np.random.default_rng(cfg['seed']+27)
    bootstrap=rng.multinomial(cfg['replicates'],np.full(cfg['replicates'],1/cfg['replicates']),size=2000)
    for model,spec in cfg['models'].items():
        for ai,alpha in enumerate(cfg['alphas']):
            seeds=spec['seeds']; data=[arrays[model,s,ai] for s in seeds]
            truth=data[0]['truth']; target=np.r_[truth,alpha]
            fits=np.stack([d['fits'] for d in data],axis=1) # trial,seed,layer,count,method,parameter
            lr=np.stack([d['lrs'] for d in data],axis=1)
            local=np.stack([d['local_covariance'] for d in data])
            for li,layer in enumerate(LAYERS):
                for ci,counting in enumerate(['asimov','multinomial_N1000']):
                    predicted=(local[:,0] if ci else np.zeros_like(local[:,0]))+int(li in [1,3])*local[:,1]+int(li in [2,3])*local[:,2]
                    sigma=np.sqrt(np.maximum(0,np.diagonal(predicted,axis1=-2,axis2=-1)))
                    for mi,method in enumerate(['known_alpha','profile_alpha']):
                        f=fits[:,:,li,ci,mi]; error=f-target
                        for p in range(7):
                            valid=np.isfinite(f[...,p]); perseed_sd=np.nanstd(f[...,p],axis=0,ddof=1)
                            metrics.append(dict(model=model,alpha_injected=alpha,layer=layer,counting=counting,method=method,parameter=p,
                                                requested=f.shape[0]*f.shape[1],valid=int(valid.sum()),
                                                bias=float(np.nanmean(error[...,p])),sd=float(np.sqrt(np.nanmean(perseed_sd**2))),
                                                rmse=float(np.sqrt(np.nanmean(error[...,p]**2))),
                                                local_sigma=float(np.sqrt(np.mean(sigma[:,p]**2))) if mi else np.nan))
                    f=fits[:,:,li,ci,1]; error=f-target
                    relative=(f[...,:6]-truth)/truth
                    relsd=np.nanvar(f[...,:6],axis=0,ddof=1)/truth**2
                    summary_metrics.append(dict(model=model,alpha_injected=alpha,layer=layer,counting=counting,
                                                relative_sd_rms=float(np.sqrt(np.nanmean(relsd))),
                                                relative_rmse_rms=float(np.sqrt(np.nanmean(relative**2))),
                                                relative_bias_rms=float(np.sqrt(np.nanmean(np.nanmean(relative,axis=0)**2))),
                                                local_relative_sigma_rms=float(np.sqrt(np.mean((sigma[:,:6]/truth)**2))),
                                                alpha_bias=float(np.nanmean(error[...,6])),alpha_sd=float(np.sqrt(np.nanmean(np.nanvar(f[...,6],axis=0,ddof=1)))),
                                                local_alpha_sigma=float(np.sqrt(np.mean(sigma[:,6]**2))),
                                                truth_macro_acceptance=float(np.mean(lr[:,:,li,ci,:6]<=1)),
                                                truth_alpha_acceptance=float(np.mean(lr[:,:,li,ci,6]<=1)),
                                                alpha_boundary_frequency=float(np.mean(abs(f[...,6])>=3-1e-6)),
                                                fraction_boundary_frequency=float(np.mean(np.any(f[...,:6]<1e-7,axis=-1)))))
                indicator=np.where(np.isfinite(lr[:,:,li,1]),lr[:,:,li,1]<=1,np.nan)
                for p in range(8):
                    v=indicator[...,p] if p<7 else np.mean(indicator[...,:6],axis=-1)
                    stat=block_stat(v)
                    cover.append(dict(model=model,alpha_injected=alpha,layer=layer,parameter=p if p<7 else 'macro',
                                      requested=v.size,valid=int(np.isfinite(v).sum()),**stat))
            indicator=np.where(np.isfinite(lr[:,:,:,1]),lr[:,:,:,1]<=1,np.nan)
            for first,second in PAIRS:
                difference=indicator[:,:,first]-indicator[:,:,second]
                for p in range(8):
                    v=difference[...,p] if p<7 else np.mean(difference[...,:6],axis=-1)
                    stat=block_stat(v)
                    row=dict(model=model,alpha_injected=alpha,comparison=f'{LAYERS[first]}_minus_{LAYERS[second]}',
                             parameter=p if p<7 else 'macro',**stat)
                    comparisons.append(row)
                    if alpha==0 and p==7 and (first,second) in [(1,0),(3,1)]:
                        z=stat['value']/stat['mc_se'];tests.append(dict(**row,z=z,p_normal_two_sided=float(2*norm.sf(abs(z))),holm_p=np.nan))
            # Joint resampling of trial blocks, retaining all seed/case correlations.
            x=fits[:,:,:,1,1,:6]/truth
            assert np.isfinite(x).all(), 'Resolve fit failures before reporting paired variance ratios.'
            flat=x.reshape(len(x),-1);n=len(x)
            mean=bootstrap@flat/n; second=bootstrap@(flat**2)/n
            v=((second-mean**2)*n/(n-1)).reshape(len(bootstrap),len(seeds),4,6)
            boot_sd=np.sqrt(np.maximum(v,0).mean(axis=(1,3)))
            sd=np.sqrt(np.var(x,axis=0,ddof=1).mean(axis=(0,2)))
            for li in [1,2,3]:
                ratios=boot_sd[:,li]/boot_sd[:,0]
                sd_comparisons.append(dict(model=model,alpha_injected=alpha,layer=LAYERS[li],
                                           sd_ratio_to_oracle=float(sd[li]/sd[0]),bootstrap_low95=float(np.quantile(ratios,.025)),
                                           bootstrap_high95=float(np.quantile(ratios,.975)),bootstrap_replicates=len(bootstrap),trial_blocks=n))
    ordered=sorted(tests,key=lambda r:r['p_normal_two_sided']);assert len(ordered)==6
    current=0.
    for i,row in enumerate(ordered):
        current=max(current,min(1.,(len(ordered)-i)*row['p_normal_two_sided']));row['holm_p']=current
    widths=[];width_pairs=[]
    for model,spec in cfg['models'].items():
        for p in cfg['width_parameters']:
            bylayer=[]
            for layer in LAYERS:
                rows=[r for r in intervals if r['model']==model and r['layer']==layer and int(r['parameter'])==p]
                rows=sorted(rows,key=lambda r:(int(r['trial']),int(r['seed'])))
                assert len(rows)==cfg['width_trials']*len(spec['seeds'])
                assert all(r['interval_status']=='ok' for r in rows)
                v=np.array([float(r['high'])-float(r['low']) for r in rows]).reshape(cfg['width_trials'],len(spec['seeds']))
                bylayer.append(v);stat=block_stat(v)
                widths.append(dict(model=model,parameter=p,layer=layer,mean_width=stat['value'],mc_se=stat['mc_se'],trial_blocks=stat['trial_blocks'],
                                   median_width=float(np.median(v)),intervals=len(rows),
                                   low_limited=sum(str(r['low_limited'])=='True' for r in rows),
                                   high_limited=sum(str(r['high_limited'])=='True' for r in rows),
                                   scan_reentry=sum(str(r['scan_reentry'])=='True' for r in rows)))
            for li in [1,2,3]:
                stat=block_stat(bylayer[li]-bylayer[0])
                width_pairs.append(dict(model=model,parameter=p,comparison=f'{LAYERS[li]}_minus_oracle',**stat))
    for name,rows in [('metrics',metrics),('summary_metrics',summary_metrics),('coverage',cover),('coverage_comparisons',comparisons),
                      ('sd_comparisons',sd_comparisons),('primary_tests',tests),('intervals',intervals),('width_summary',widths),
                      ('width_comparisons',width_pairs),('failures',failures)]: write_table(out/f'{name}.tsv',rows)
    fig,axes=plt.subplots(1,3,figsize=(12,3.6),sharey=True,constrained_layout=True)
    for ax,model in zip(axes,cfg['models']):
        rows=[r for r in cover if r['model']==model and r['alpha_injected']==0 and r['parameter']=='macro']
        ax.errorbar(np.arange(4),[100*r['value'] for r in rows],yerr=[100*r['mc_se'] for r in rows],fmt='o',capsize=4)
        ax.axhline(68.268949,color='gray',ls='--');ax.set(xticks=np.arange(4),xticklabels=['Oracle','Source MC','Mean MC','Both MC'],title=model,ylabel='Macro profile coverage (%)')
        ax.tick_params(axis='x',labelrotation=20);ax.grid(alpha=.25)
    save_svg(fig,out/'independent_coverage.svg');plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(12,3.6),constrained_layout=True)
    for ax,model in zip(axes,cfg['models']):
        rows=[r for r in summary_metrics if r['model']==model and r['alpha_injected']==0 and r['counting']=='multinomial_N1000']
        ax.plot(np.arange(4),[100*r['relative_sd_rms'] for r in rows],'o-',label='Empirical SD')
        ax.plot(np.arange(4),[100*r['local_relative_sigma_rms'] for r in rows],'s--',label='Truth-point delta')
        ax.set(xticks=np.arange(4),xticklabels=['Oracle','Source MC','Mean MC','Both MC'],title=model,ylabel='Relative fraction SD RMS (%)')
        ax.tick_params(axis='x',labelrotation=20);ax.grid(alpha=.25)
    axes[-1].legend(fontsize=8);save_svg(fig,out/'independent_spread.svg');plt.close(fig)
    summary=dict(runs=runs,trial_blocks=cfg['replicates'],primary_tests=len(tests),holm_rejections=sum(r['holm_p']<.05 for r in tests),
                 failure_cells=len(failures),totals=dict(worker_wall_s=sum(r['wall_s'] for r in runs.values()),
                 worker_cpu_s=sum(r['cpu_s'] for r in runs.values()),peak_rss_KiB=max(r['max_rss_KiB'] for r in runs.values()),
                 solver_calls=sum(r['numerical_stats']['solver_calls'] for r in runs.values()),
                 solver_failures=sum(r['numerical_stats']['solver_failures'] for r in runs.values()),
                 counting_instances=sum(r['counting_instances'] for r in runs.values()),
                 mean_instances=sum(r['mean_instances'] for r in runs.values())),report_wall_s=time.perf_counter()-tick)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    if args.compact:
        removed=[]
        for key,run in runs.items():
            folder=out/key
            if not folder.exists():continue
            for path in folder.iterdir():
                if path.name=='summary.json':assert json.loads(path.read_text())==run
                else:
                    target=intervals if path.stem=='intervals' else failures
                    subset=[r for r in target if r['model']==run['model'] and int(r['seed'])==run['seed'] and float(r['alpha_injected'])==run['alpha_injected']]
                    assert read_table(path)==subset
                removed.append(dict(path=str(path.relative_to(root)),bytes=path.stat().st_size));path.unlink()
            folder.rmdir()
            if not any(folder.parent.iterdir()):folder.parent.rmdir()
            if folder.parent.parent.exists() and not any(folder.parent.parent.iterdir()):folder.parent.parent.rmdir()
        if removed:(out/'compaction.json').write_text(json.dumps(dict(removed=removed,bytes=sum(r['bytes'] for r in removed)),indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='runs'},indent=2))


if __name__=='__main__':main()
