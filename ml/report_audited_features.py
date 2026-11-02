#!/usr/bin/env python3
"""Same-event evaluation of the fixed audited feature correction, no scans."""
import json
import resource
import time

import numpy as np

from audited_features import REPO, SCINTILLATORS, configuration, load
from report_low_energy import metrics
from train_bdt import write_table

tick,cpu=time.perf_counter(),time.process_time();cfg=configuration();out=REPO/'workbook/stage56_energy_ml'
d,s,x=load();rows=s['row']
with np.load(REPO/'ml/artifacts/stage56/predictions.npz') as z:
    ev=z['eval_row'];cal=z['cal_row'];raw=z['eval_raw_log'].mean(axis=0);cp=z['cal_raw_log'].mean(axis=0);md=json.loads(str(z['metadata_json']))
offset=float(np.mean(np.log(d['truth_E_GeV'][cal])-cp));np.testing.assert_allclose(offset,md['offset_log'],rtol=0,atol=1e-14)
with np.load(REPO/'ntuples/energy_ml_stage55/predictions.npz') as z:
    old_rows=z['eval_row'];lookup={int(r):i for i,r in enumerate(old_rows)};take=np.array([lookup[int(r)] for r in ev])
    old=z['nominal50'][take];old_raw=z['raw_nominal50'][take]
logy=np.log(d['truth_E_GeV'][ev]);p=d['reco_pz_GeV'][ev]
models=dict(pz0_over0p8=np.log(p/.8),historical_p0_over0p8=np.log(d['reco_p_GeV'][ev]/.8),
            historical_nominal50=old,audited_raw=raw+offset,audited_raw_uncalibrated=raw,historical_nominal50_uncalibrated=old_raw)
masks=dict(all=np.ones(len(ev),bool),E50_100=(d['truth_E_GeV'][ev]<100),E100_200=(d['truth_E_GeV'][ev]>=100)&(d['truth_E_GeV'][ev]<200),
           pz50_100=p<100,pz100_250=(p>=100)&(p<250),high_y=d['y_lepton'][ev]>=.8,unconfirmed=~d['confirmed'][ev],
           input_missing=np.isnan(x[np.searchsorted(rows,ev)]).any(axis=1))
for lo,hi in zip([50,75,100,150,200,400,800,1600,3200],[75,100,150,200,400,800,1600,3200,6400]):
    masks[f'E{lo}_{hi}']=(d['truth_E_GeV'][ev]>=lo)&(d['truth_E_GeV'][ev]<hi)
groups,gid=np.unique(d['group'][ev],return_inverse=True);rng=np.random.default_rng(cfg['bootstrap_seed'])
weights=np.zeros((cfg['bootstrap_replicates'],len(groups)),dtype=np.int64)
for comp in ['pi','k','charm']:
    idx=np.array([i for i,g in enumerate(groups) if g.startswith(comp+':')])
    weights[:,idx]=rng.multinomial(len(idx),np.full(len(idx),1/len(idx)),size=len(weights))
table=[];paired=[]
for stratum,m in masks.items():
    if not m.any():continue
    ng=len(set(d['group'][ev][m]));N=int(m.sum())
    for name,pred in models.items():table.append(dict(stratum=stratum,model=name,N=N,groups=ng,**metrics(logy[m],pred[m])))
    counts=np.bincount(gid[m],minlength=len(groups));denom=weights@counts
    for reference in ['pz0_over0p8','historical_nominal50']:
        a=(models['audited_raw'][m]-logy[m])**2;b=(models[reference][m]-logy[m])**2
        point=100*(1-np.sqrt(a.mean()/b.mean()));ci=[np.nan,np.nan];nb=0
        if ng>=3:
            aa=weights@np.bincount(gid[m],weights=a,minlength=len(groups));bb=weights@np.bincount(gid[m],weights=b,minlength=len(groups))
            valid=(denom>0)&(bb>0);samples=100*(1-np.sqrt(aa[valid]/bb[valid]));ci=np.quantile(samples,[.025,.975]);nb=len(samples)
        paired.append(dict(stratum=stratum,model='audited_raw',reference=reference,N=N,groups=ng,gain_pct=point,gain_low95_pct=ci[0],gain_high95_pct=ci[1],bootstrap_valid=nb))
write_table(out/'metrics.tsv',table);write_table(out/'paired.tsv',paired)
# Energy-binned figure is deliberately independent of reco-pz strata.
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig,axes=plt.subplots(1,2,figsize=(10,4),constrained_layout=True)
edges=[50,75,100,150,200,400,800,1600,3200,6400]
for name,label in [('pz0_over0p8',r'$p_{z0}/0.8$'),('historical_nominal50','Historical F6, nominal50'),('audited_raw','F7: pz0 + raw scintillator charges')]:
    values=[next(r for r in table if r['model']==name and r['stratum']==f'E{lo}_{hi}') for lo,hi in zip(edges[:-1],edges[1:])]
    for ax,metric in zip(axes,['log_RMSE','mean_bias_pct']):ax.plot(np.sqrt(np.array(edges[:-1])*edges[1:]),[r[metric] for r in values],'o-',label=label)
for ax in axes:
    ax.set_xscale('log');ax.set_xlabel(r'True $E_\nu$ [GeV]');ax.grid(alpha=.2);ax.axvspan(50,100,color='grey',alpha=.1)
axes[0].set_ylabel('log-RMSE');axes[1].set_ylabel('Mean relative bias [%]');axes[0].legend(fontsize=8);axes[1].axhline(0,color='black',lw=.6)
fig.suptitle('Nominal development comparison: same events, 3 fixed F7 fits\nGlobal common-cohort calibration; joint feature correction, unit MC')
svg=out/'audited_response.svg';fig.savefig(svg);fig.savefig(out/'audited_response.png',dpi=130);plt.close(fig)
svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
old_names=json.loads(str(d['metadata_json']))['features']
fig,axes=plt.subplots(1,2,figsize=(10,4),constrained_layout=True)
for ax,detector in zip(axes,['Veto20','Timing0']):
    q=s['raw_charge'][:,SCINTILLATORS.index(detector)];f=d['x'][rows,old_names.index(detector+'_charge')]
    m=np.isfinite(q)&np.isfinite(f)&(q>1)&(f>1)
    ax.hexbin(q[m],f[m],gridsize=45,xscale='log',yscale='log',bins='log',mincnt=1,cmap='viridis')
    lo=min(q[m].min(),f[m].min());hi=max(q[m].max(),f[m].max());ax.plot([lo,hi],[lo,hi],'r--',lw=1)
    ax.set_title(f'{detector}: {int(m.sum())} shown / {len(q)} selected');ax.set_xlabel('Raw charge [pC]');ax.set_ylabel('Fitted charge [pC]')
fig.suptitle('All nominal selected events; raw and fit >1 pC for log display only\nNegative/zero readouts remain in the feature audit and model')
svg=out/'scintillator_fit_raw.svg';fig.savefig(svg);fig.savefig(out/'scintillator_fit_raw.png',dpi=130);plt.close(fig)
svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
result=dict(formal_fits=len(md['fits']),feature_version=cfg['version'],features=len(cfg['features']),offset_log=offset,
            fit_wall_sum_s=sum(r['fit_wall_s'] for r in md['fits']),training=md,cal_N=len(cal),eval_N=len(ev),
            interval_scope='fixed models and common calibration; component-stratified 22-source-group bootstrap, no model/calibration/detector uncertainty or multiplicity correction',
            wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
(out/'results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
