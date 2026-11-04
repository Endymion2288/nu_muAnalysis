"""Stage92 full saved-output validation and publication plot, no new inference."""
import csv
import json

import numpy as np

from evaluate_retrained_posterior import OUT,CACHE,REPO
from support_augmentation import arrays,save,table,begin,resources


def read(path):
    return list(csv.DictReader(path.open(),delimiter='\t'))


def main():
    start=begin();numeric=[];checks=0
    for role in ['cal','test']:
        d=arrays(CACHE/f'input_{role}.npz');v=arrays(CACHE/f'predictions_{role}.npz')
        n=len(d['row']);assert n=={'cal':11612,'test':13189}[role] and int(v['completed_N'])==n
        np.testing.assert_array_equal(d['row'],v['row'])
        rows=read(OUT/role/'numerical_checks.tsv');np.testing.assert_array_equal(d['row'],[int(r['row']) for r in rows])
        assert len(rows)==n and v['numerical_certified'].all()
        assert all(r['certified']=='True' and not r['error'] for r in rows)
        for key in ['accurate_quantiles','accurate_PIT','accurate_logscore','accurate_training_logscore','accurate_F','accurate_ESS_fraction']:
            assert np.isfinite(v[key]).all();checks+=v[key].size
        assert (np.diff(v['accurate_quantiles'],axis=1)>=0).all()
        assert ((v['accurate_PIT']>=0)&(v['accurate_PIT']<=1)).all()
        assert (np.diff(v['accurate_F'],axis=1)>=-1e-9).all()
        flags=sum(int(r['quad_precision_flags']) for r in rows)
        row=dict(role=role,N=n,certified_N=int(v['numerical_certified'].sum()),missing_N=int(d['input_missing'].sum()),
                 precision_flags=flags,max_quad_error=max(float(r['quad_error']) for r in rows),
                 max_tail_bound=max(float(r['tail_bound']) for r in rows),max_root_residual=max(float(r['root_residual']) for r in rows),
                 max_lower_endpoint=abs(np.array([float(r['global_CDF_lower']) for r in rows])).max(),
                 max_upper_endpoint=abs(np.array([float(r['global_CDF_upper']) for r in rows])-1).max(),
                 minimum_CDF_increment=min(float(r['minimum_CDF_increment']) for r in rows),
                 CDF_calls=sum(int(r['CDF_calls']) for r in rows),integrand_evaluations=sum(int(r['integrand_evaluations']) for r in rows))
        assert flags==0 and row['max_quad_error']<1e-9 and row['max_root_residual']<1e-7 and row['max_tail_bound']<1e-10
        independent=json.loads((OUT/role/'independent_validation.json').read_text());assert independent['passed'];numeric.append(row)
    cal=json.loads((OUT/'cal/calibration_objective_closure.json').read_text());assert cal['passed']
    table(OUT/'numerical_summary.tsv',numeric)
    select=[];paired=[]
    for role in ['cal','test']:
        for r in read(OUT/role/'metrics.tsv'):
            if r['weighting']=='incoming' and r['stratum'] in ['E50_100','E100_200','all','E200_inf','pz50_100','pz50_100_trueE200','high_y','unconfirmed','input_missing','E3200_6400']:
                select.append(r)
        for r in read(OUT/role/'paired.tsv'):
            if r['stratum'] in ['E50_100','E100_200','all','pz50_100_trueE200','high_y','unconfirmed']:
                paired.append(r)
    table(OUT/'key_metrics.tsv',select);table(OUT/'key_paired.tsv',paired)
    save(OUT/'complete_validation.json',dict(passed=True,complete_records=24801,missing_cal_test=[6,5],finite_saved_values_checked=checks,
         all_rows_certified=True,precision_flags=0,fullcal_objective_closed=True,source95=False,independent_confirmation=False,
         independent_report_values_checked=sum(json.loads((OUT/r/'independent_validation.json').read_text())['checked_numeric_values'] for r in ['cal','test']),
         new_integrations=0,new_fits=0,**resources(start)))
    plot()
    save(OUT/'closeout_resources.json',resources(start))
    print(json.dumps(numeric,indent=2),flush=True)


def plot():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    metrics=read(OUT/'test/metrics.tsv');paired=read(OUT/'test/paired.tsv');coverage=read(OUT/'test/coverage.tsv')
    layers=['E50_100','E100_200','all','pz50_100_trueE200','high_y','unconfirmed']
    labels=['50–100 GeV','100–200 GeV','all','low pz, E≥200','high-y','unconfirmed'];x=np.arange(len(layers))
    fig,ax=plt.subplots(1,3,figsize=(15,4.3),layout='constrained')
    policies=[('traditional','Traditional','#666666'),('direct_cal','Direct','#d55e00'),('posterior_old_accurate','Old posterior, accurate inference','#0072b2'),('posterior_accurate','New accurate-loss posterior','#009e73')]
    for name,label,color in policies:
        val=[float(next(r for r in metrics if r['stratum']==s and r['weighting']=='incoming' and r['policy']==name)['log_RMSE']) for s in layers]
        ax[0].plot(x,val,'o-',label=label,color=color,ms=4)
    ax[0].set(xticks=x,xticklabels=labels,ylabel='Incoming-weighted log-RMSE',title='Same split; new fit uses accurate loss/calibration')
    ratios=[next(r for r in paired if r['stratum']==s and r['reference']=='posterior_old_accurate') for s in layers]
    y=np.array([float(r['RMSE_ratio']) for r in ratios]);lo=np.array([float(r['conditional_low95']) for r in ratios]);hi=np.array([float(r['conditional_high95']) for r in ratios])
    ax[1].errorbar(x,y,yerr=np.vstack([y-lo,hi-y]),fmt='o',color='#009e73',capsize=3)
    ax[1].axhline(1,color='grey',ls='--');ax[1].set(xticks=x,xticklabels=labels,ylabel='New / old accurate posterior RMSE',title='500 incoming draws, conditional 95% intervals')
    for level,color in [(68,'#0072b2'),(90,'#009e73')]:
        for method,style in [('old_accurate','--'),('accurate','-')]:
            yy=[float(next(r for r in coverage if r['stratum']==s and r['method']==method and int(r['level'])==level)['coverage_pct']) for s in layers]
            ax[2].plot(x,yy,'o'+style,color=color,ms=4,label=f'{level}% '+('old' if method=='old_accurate' else 'new'))
        ax[2].axhline(level,color=color,alpha=.3)
    ax[2].set(xticks=x,xticklabels=labels,ylabel='Posterior coverage [%]',title='Coverage does not replace PIT / tail protections')
    for a in ax:a.tick_params(axis='x',rotation=35);a.grid(axis='y',alpha=.15)
    ax[0].legend(fontsize=7);ax[2].legend(fontsize=8)
    fig.suptitle('Stage92: one fixed retraining; developed research test, no model promotion',fontsize=12)
    path=OUT/'accurate_retraining.svg';fig.savefig(path);path.write_text('\n'.join(l.rstrip() for l in path.read_text().splitlines())+'\n')
    fig.savefig('/tmp/stage92_accurate_retraining.png',dpi=140);plt.close(fig)


if __name__=='__main__':main()
