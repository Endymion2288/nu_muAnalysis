"""Stage88 closeout from compact numerical arrays, no new inference or fitting."""
import csv
import json
from pathlib import Path

import numpy as np

from support_augmentation import arrays, save, table, begin, resources

REPO=Path(__file__).resolve().parents[1]
OUT=REPO/'workbook/stage88_energy_ml'


def report():
    start=begin();d=arrays(REPO/'ntuples/energy_ml_stage88/input.npz');v=arrays(OUT/'audit_numerical_values.npz')
    np.testing.assert_array_equal(d['row'],v['row'])
    checks=list(csv.DictReader((OUT/'audit_crosscheck.tsv').open(),delimiter='\t'))
    supported=np.array([float(r['max_abs_CDF_s_r'])<=1e-7 and float(r['max_abs_logdensity_s_r'])<=1e-6
                        and int(r['low_density_queries'])==0 for r in checks])
    rows=[];errors={}
    for order in [32,64,128,256]:
        name=f'GH{order}';delta=dict(edge_CDF=np.max(abs(v[name+'_F']-v['reference_F']),axis=1),
             PIT=abs(v[name+'_PIT']-v['reference_PIT']),quantile_logE=np.max(abs(v[name+'_quantiles']-v['reference_quantiles']),axis=1),
             log_density=abs(v[name+'_log_density']-v['reference_log_density']))
        errors[order]=delta
        for metric,limit in [('edge_CDF',1e-4),('PIT',1e-4),('quantile_logE',1e-3),('log_density',1e-3)]:
            x=delta[metric]
            rows.append(dict(method=name,metric=metric,N=len(x),reference_crosscheck_supported_N=int(supported.sum()),limit=limit,
                median=float(np.median(x)),p90=float(np.quantile(x,.9)),p99=float(np.quantile(x,.99)),maximum=float(x.max()),
                failure_N=int((x>limit).sum()),failure_pct=float(100*(x>limit).mean()),
                failure_supported_N=int(((x>limit)&supported).sum())))
    table(OUT/'error_distribution.tsv',rows)
    # Local transformed-density resolution diagnostic, not a new physical cut.
    from posterior_numerics import decode
    from scipy.special import expit
    mix,mr,ms,sr,ss=decode(d['head'],float(d['b']),float(d['T']))
    u=expit(ms);derivative=u.copy()
    derivative[:,0]=.1*u[:,0]*(1-u[:,0])/(1-.1*u[:,0])
    ratio=ss*derivative/sr
    resolution=np.where(mix>=.05,ratio,0.).max(1)
    diagnostic=[]
    for lo,hi in [(0.,.5),(.5,2.),(2.,5.),(5.,np.inf)]:
        m=(resolution>=lo)&(resolution<hi)
        diagnostic.append(dict(effective_width_ratio_low=lo,effective_width_ratio_high='inf' if np.isinf(hi) else hi,
            N=int(m.sum()),GH32_PIT_failure_N=int(((errors[32]['PIT']>1e-4)&m).sum()),
            GH32_quantile_failure_N=int(((errors[32]['quantile_logE']>1e-3)&m).sum()),
            GH32_logdensity_failure_N=int(((errors[32]['log_density']>1e-3)&m).sum()),
            meaning='max sigma_s*dlogE/ds/sigma_r at component mean for mixture weight>=.05; local numerical diagnostic, not event selection'))
    table(OUT/'latent_resolution.tsv',diagnostic)
    # Conditional subset diagnostics only: no full-cal/test risk claim or intervals.
    subset=[]
    e=d['truth_E_GeV'];pz=d['pz'];masks=dict(train=d['role']==1,cal=d['role']==2,E50_100=(50<=e)&(e<100),
        E100_200=(100<=e)&(e<200),lowpz_truehighE=(pz<100)&(e>=200),high_y=d['y_lepton']>=.8,unconfirmed=~d['confirmed'])
    y=np.log(e);reference=v['reference_quantiles'][:,2];old=v['GH32_quantiles'][:,2]
    for name,m in masks.items():
        w=d['weight'][m]
        subset.append(dict(stratum=name,N=int(m.sum()),weight_sum=float(w.sum()),GH32_log_RMSE=float(np.sqrt(np.average((old[m]-y[m])**2,weights=w))) if m.any() else '未测量',
            reference_log_RMSE=float(np.sqrt(np.average((reference[m]-y[m])**2,weights=w))) if m.any() else '未测量',
            max_median_shift_logE=float(np.max(abs(old[m]-reference[m]))) if m.any() else '未测量',
            scope='fixed selected rows only; not population/independent test evidence'))
    table(OUT/'subset_diagnostics.tsv',subset)
    # Zero-offset training-prior NLL must match the prior-corrected posterior table.
    pr=json.loads((REPO/'workbook/stage87_energy_ml/prior.json').read_text());ratio=np.array(pr['ratios']['nominal'])
    bins=np.searchsorted(np.array([0,50,100,200,400,800,1600,3200,6400,np.inf]),e,side='right')-1
    normalizer=(np.diff(v['reference_F'],axis=1)*ratio).sum(1)
    raw_logdensity=v['reference_log_density']-np.log(ratio[bins])+np.log(normalizer)
    m=d['role']==2;w=d['weight'][m]
    objectives=list(csv.DictReader((OUT/'fixed_calibration_objectives.tsv').open(),delimiter='\t'))
    sensitivity=[]
    for coordinate,minus,plus,step in [('b',1,2,.01),('T',3,4,.05)]:
        item=dict(coordinate=coordinate,step=step,N=int(m.sum()),scope='fixed selected cal rows, no parameter optimization')
        for method,column in [('GH32','fixed_subset_weighted_NLL_GH32'),('reference','fixed_subset_weighted_NLL_reference')]:
            a=float(objectives[minus][column]);b=float(objectives[plus][column]);c=float(objectives[0][column])
            item[method+'_centered_slope']=(b-a)/(2*step)
            item[method+'_centered_curvature']=(b+a-2*c)/(step*step)
        sensitivity.append(item)
    table(OUT/'fixed_objective_sensitivity.tsv',sensitivity)
    recomputed=-np.dot(w,raw_logdensity[m])/w.sum()
    difference=abs(recomputed-float(objectives[0]['fixed_subset_weighted_NLL_reference']))
    assert difference<1e-10,difference
    save(OUT/'closeout_validation.json',dict(passed=True,identity_rows=len(e),test_rows=int((d['role']==3).sum()),
        independently_prior_removed_cal_NLL=recomputed,cal_NLL_absolute_difference=difference,
        crosscheck_supported_N=int(supported.sum()),low_density_queries_not_log_certified=sum(int(r['low_density_queries']) for r in checks),
        inference_runs=0,fits=0,scope='recompute distributions/subset summaries and remove prior analytically; reference crosscheck is separate',**resources(start)))
    figure(errors)


def figure(errors):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(1,2,figsize=(10,3.8),layout='constrained')
    for order,values in errors.items():
        for a,key,limit in zip(ax,['PIT','quantile_logE'],[1e-4,1e-3]):
            x=np.sort(values[key]);a.plot(np.arange(1,len(x)+1)/len(x),np.maximum(x,1e-15),label=f'GH{order}')
    for a,label,limit in zip(ax,['Absolute PIT error','Max absolute logE quantile error'],[1e-4,1e-3]):
        a.set(yscale='log',xlabel='Unweighted fraction of fixed train/cal subset',ylabel=label,ylim=(1e-12,None))
        a.axhline(limit,color='black',ls='--',lw=.8);a.legend(fontsize=8)
    fig.suptitle('Stage88: saved model, fixed calibration/prior; adaptive reference, no test evaluation')
    path=OUT/'integration_errors.svg';fig.savefig(path)
    path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
    plt.close(fig)


if __name__=='__main__':report()
