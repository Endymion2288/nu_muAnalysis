#!/usr/bin/env python3
"""Held-out calibration report; source-trial blocks retain seed correlations."""
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
from mc_bootstrap import config
from report_closure import save_svg


def stat(values):
    blocks=np.asarray(values).reshape(len(values),-1).mean(axis=1)
    value=float(blocks.mean());se=float(blocks.std(ddof=1)/np.sqrt(len(blocks)))
    return dict(value=value,mc_se=se,mc_low95=value-1.96*se,mc_high95=value+1.96*se,trial_blocks=len(blocks))


def main():
    parser=argparse.ArgumentParser(__doc__);parser.add_argument('--compact',action='store_true');args=parser.parse_args()
    tick=time.perf_counter();root=Path(__file__).resolve().parents[1];cfg=config(root);out=root/'workbook/stage28_energy_ml'
    previous=json.loads((out/'summary.json').read_text()) if (out/'summary.json').exists() else {}
    runs={};arrays={};widths=[];failures=[]
    for model,spec in cfg['models'].items():
        for seed in spec['seeds']:
            key=f'{model}/seed_{seed}';folder=out/key
            runs[key]=json.loads((folder/'summary.json').read_text()) if (folder/'summary.json').exists() else previous['runs'][key]
            r=runs[key];assert r['trials']==200 and r['calibration_trials']==100 and r['events']==13375 and not r['smoke']
            if (folder/'widths.tsv').exists():widths.extend(dict(model=model,seed=seed,**w) for w in read_table(folder/'widths.tsv'))
            if (folder/'failures.json').exists():failures.extend(dict(model=model,seed=seed,**w) for w in json.loads((folder/'failures.json').read_text()))
            with np.load(root/f'ml/artifacts/stage28/{key}/mc_bootstrap.npz') as z:arrays[model,seed]={k:z[k] for k in z.files}
    if not widths and (out/'widths.tsv').exists():widths=read_table(out/'widths.tsv')
    if not failures and previous:failures=previous['failures']
    coverage=[];seed_coverage=[];comparisons=[];threshold_rows=[];width_summary=[];metrics=[];primary=[]
    joint_coverage=[];diagnostics=[];rng=np.random.default_rng(cfg['seed']+28);nb=1000
    # Calibration and test block resampling are independent; identical index
    # draws across identities retain all common-RNG correlations.
    caldraw=rng.integers(0,100,(nb,100));testdraw=rng.integers(0,100,(nb,100))
    for model,spec in cfg['models'].items():
        ds=[arrays[model,s] for s in spec['seeds']];nseeds=len(ds)
        actual=np.stack([d['actual_lrs'][100:] for d in ds],axis=1)
        boot=np.stack([d['bootstrap_lrs'][:100] for d in ds],axis=1)
        thresholds=np.stack([d['thresholds'] for d in ds])
        assert np.isfinite(actual).all() and np.isfinite(boot).all(), 'Resolve failed fits before reporting coverage.'
        thrboots=np.empty((nb,nseeds,2))
        for si,d in enumerate(ds):
            expected=np.array([np.quantile(d['bootstrap_lrs'][:100,:,:6],cfg['threshold_quantile']),np.quantile(d['bootstrap_lrs'][:100,:,6],cfg['threshold_quantile'])])
            np.testing.assert_array_equal(expected,d['thresholds'])
            for bi in range(nb):
                selected=d['bootstrap_lrs'][caldraw[bi]]
                thrboots[bi,si]=[np.quantile(selected[:,:,:6],cfg['threshold_quantile']),np.quantile(selected[:,:,6],cfg['threshold_quantile'])]
            for group in range(2):
                threshold_rows.append(dict(model=model,seed=spec['seeds'][si],parameter_group=['fraction','alpha'][group],threshold=float(thresholds[si,group]),
                                           calibration_low95=float(np.quantile(thrboots[:,si,group],.025)),calibration_high95=float(np.quantile(thrboots[:,si,group],.975)),
                                           calibration_trials=100,replicates_per_trial=16))
            # Descriptive boundary diagnostics; they do not change calibration.
            for par in range(7):
                target=d['fits'][:100,par]
                boundary=(abs(target)>=3-1e-6) if par==6 else ((target<1e-7)|(target>1-1e-7))
                values=d['bootstrap_lrs'][:100,:,par]
                for label,mask in [('all',np.ones(100,dtype=bool)),('target_boundary',boundary),('target_interior',~boundary)]:
                    v=values[mask]
                    diagnostics.append(dict(model=model,seed=spec['seeds'][si],parameter=par,target_class=label,
                                            outer_trials=int(mask.sum()),lr_instances=int(v.size),
                                            lr_zero_frequency=float(np.mean(v<1e-7)) if v.size else np.nan,
                                            lr_quantile=float(np.quantile(v,cfg['threshold_quantile'])) if v.size else np.nan))
        full_thr=np.concatenate([np.repeat(thresholds[:,:1],6,axis=1),thresholds[:,1:]],axis=1)
        fixed=actual<=1;calibrated=actual<=full_thr[None]
        for si,seed in enumerate(spec['seeds']):
            for method,indicator in [('fixed_lr1',fixed[:,si]),('calibrated_lr',calibrated[:,si])]:
                for par in range(8):
                    values=indicator[:,par] if par<7 else indicator[:,:6].mean(axis=-1)
                    seed_coverage.append(dict(model=model,seed=seed,method=method,parameter=par if par<7 else 'macro',**stat(values)))
        for method,indicator in [('fixed_lr1',fixed),('calibrated_lr',calibrated)]:
            for par in range(8):
                v=indicator[:,:,par] if par<7 else indicator[:,:,:6].mean(axis=-1)
                coverage.append(dict(model=model,method=method,parameter=par if par<7 else 'macro',**stat(v)))
        difference=calibrated.astype(float)-fixed
        for par in range(8):
            v=difference[:,:,par] if par<7 else difference[:,:,:6].mean(axis=-1)
            row=dict(model=model,parameter=par if par<7 else 'macro',**stat(v));comparisons.append(row)
            if par==7:
                z=row['value']/row['mc_se'] if row['mc_se']>0 else (0. if row['value']==0 else np.inf)
                primary.append(dict(**row,p_normal_two_sided=float(2*norm.sf(abs(z))),holm_p=np.nan))
        bootcov=np.empty((nb,8));bootdelta=np.empty((nb,8))
        for bi in range(nb):
            sample=actual[testdraw[bi]]
            threshold=np.concatenate([np.repeat(thrboots[bi,:,:1],6,axis=1),thrboots[bi,:,1:]],axis=1)
            calibrated_b=(sample<=threshold[None]).mean(axis=(0,1));fixed_b=(sample<=1).mean(axis=(0,1))
            bootcov[bi,:7]=calibrated_b;bootcov[bi,7]=calibrated_b[:6].mean()
            bootdelta[bi,:7]=calibrated_b-fixed_b;bootdelta[bi,7]=(calibrated_b-fixed_b)[:6].mean()
        for par in range(8):
            joint_coverage.append(dict(model=model,parameter=par if par<7 else 'macro',calibrated_low95=float(np.quantile(bootcov[:,par],.025)),
                                       calibrated_high95=float(np.quantile(bootcov[:,par],.975)),delta_low95=float(np.quantile(bootdelta[:,par],.025)),
                                       delta_high95=float(np.quantile(bootdelta[:,par],.975)),bootstrap_replicates=nb,calibration_trials=100,test_trials=100))
        fits=np.stack([d['fits'][100:] for d in ds],axis=1);truth=ds[0]['truth'];target=np.r_[truth,0.]
        for par in range(7):
            x=fits[:,:,par];error=x-target[par]
            boundary=(abs(x)>=3-1e-6) if par==6 else ((x<1e-7)|(x>1-1e-7))
            metrics.append(dict(model=model,parameter=par,bias=float(error.mean()),sd=float(np.sqrt(np.var(x,axis=0,ddof=1).mean())),rmse=float(np.sqrt(np.mean(error**2))),boundary_frequency=float(boundary.mean())))
        for par in [5,6]:
            w=[r for r in widths if r['model']==model and int(r['parameter'])==par]
            w=sorted(w,key=lambda r:(int(r['trial']),int(r['seed'])));assert len(w)==16*nseeds
            for method,column in [('fixed_lr1','fixed_width'),('calibrated_lr','calibrated_width')]:
                values=np.array([float(r[column]) for r in w]).reshape(16,nseeds)
                width_summary.append(dict(model=model,parameter=par,method=method,**stat(values)))
            delta=np.array([float(r['calibrated_width'])-float(r['fixed_width']) for r in w]).reshape(16,nseeds)
            width_summary.append(dict(model=model,parameter=par,method='calibrated_minus_fixed',**stat(delta)))
    current=0.
    for i,r in enumerate(sorted(primary,key=lambda x:x['p_normal_two_sided'])):
        current=max(current,min(1.,(3-i)*r['p_normal_two_sided']));r['holm_p']=current
    for name,rows in [('coverage',coverage),('seed_coverage',seed_coverage),('coverage_comparisons',comparisons),('thresholds',threshold_rows),('joint_uncertainty',joint_coverage),
                      ('metrics',metrics),('widths',widths),('width_summary',width_summary),('primary_tests',primary),('boundary_diagnostics',diagnostics)]:write_table(out/f'{name}.tsv',rows)
    fig,axes=plt.subplots(1,3,figsize=(11,3.8),sharey=True,constrained_layout=True)
    for ax,model in zip(axes,cfg['models']):
        for mi,method in enumerate(['fixed_lr1','calibrated_lr']):
            rows=[r for r in coverage if r['model']==model and r['method']==method and r['parameter']!='macro']
            ax.errorbar(np.arange(7)+(mi-.5)*.12,[100*r['value'] for r in rows],yerr=[100*r['mc_se'] for r in rows],fmt='o',capsize=2,label=method)
        ax.axhline(68.268949,color='gray',ls='--');ax.set(title=model,xticks=np.arange(7),xticklabels=['f0','f1','f2','f3','f4','f5','alpha'],ylabel='Held-out profile coverage (%)');ax.grid(alpha=.25)
    axes[-1].legend(fontsize=8);save_svg(fig,out/'bootstrap_coverage.svg');plt.close(fig)
    summary=dict(runs=runs,failures=failures,held_out_trials=100,calibration_trials=100,primary_tests=3,holm_rejections=sum(r['holm_p']<.05 for r in primary),
                 totals=dict(worker_wall_s=sum(r['wall_s'] for r in runs.values()),worker_cpu_s=sum(r['cpu_s'] for r in runs.values()),peak_rss_KiB=max(r['max_rss_KiB'] for r in runs.values()),
                 solver_calls=sum(r['numerical_stats']['solver_calls'] for r in runs.values()),solver_failures=sum(r['numerical_stats']['solver_failures'] for r in runs.values()),
                 iterations=sum(r['numerical_stats']['iterations'] for r in runs.values()),failure_cells=sum(r['failures'] for r in runs.values())),report_wall_s=time.perf_counter()-tick)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    if args.compact:
        removed=[]
        for key,r in runs.items():
            folder=out/key
            if not folder.exists():continue
            for path in folder.iterdir():
                if path.name=='summary.json':assert json.loads(path.read_text())==r
                elif path.name=='failures.json':assert json.loads(path.read_text())==[{k:v for k,v in row.items() if k not in ['model','seed']} for row in failures if row['model']==r['model'] and int(row['seed'])==r['seed']]
                else:assert read_table(path)==[{k:str(v) for k,v in row.items() if k not in ['model','seed']} for row in widths if row['model']==r['model'] and int(row['seed'])==r['seed']]
                removed.append(dict(path=str(path.relative_to(root)),bytes=path.stat().st_size));path.unlink()
            folder.rmdir()
            if not any(folder.parent.iterdir()):folder.parent.rmdir()
        if removed:(out/'compaction.json').write_text(json.dumps(dict(removed=removed,bytes=sum(r['bytes'] for r in removed)),indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ['runs','failures']},indent=2))


if __name__=='__main__':main()
