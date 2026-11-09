"""All fixed spectra, energy bins, flux strata and family-paired conditional intervals."""
import json
import time

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from stage199_common import DATA_ROOT,OUT,load,save,table,resources,masks


def metrics(y,p,w):
    if len(y)==0 or w.sum()==0:return dict(log_RMSE=None,mean_bias_pct=None,median_bias_pct=None,R68_pct=None,tail50_pct=None,positive_tail50_pct=None,negative_tail50_pct=None)
    error=p-y;rel=np.expm1(error);order=np.argsort(rel,kind='stable')
    q=np.interp([.16,.5,.84],(np.cumsum(w[order])-.5*w[order])/w.sum(),rel[order])
    avg=lambda v:float(np.average(v,weights=w))
    return dict(log_RMSE=float(np.sqrt(avg(error**2))),mean_bias_pct=100*avg(rel),median_bias_pct=100*float(q[1]),
        R68_pct=50*float(q[2]-q[0]),tail50_pct=100*avg(abs(rel)>.5),positive_tail50_pct=100*avg(rel>.5),negative_tail50_pct=100*avg(rel<-.5))


def main():
    tick,cpu=time.perf_counter(),time.process_time()
    d=load(DATA_ROOT/'ntuples/energy_ml_stage199/input.npz')
    pred=load(DATA_ROOT/'ntuples/energy_ml_stage199/predictions.npz')
    for k in ['run','eventID','role']:np.testing.assert_array_equal(pred.pop(k),d[k])
    pred['traditional']=np.log(d['pz']/.8);y=np.log(d['truth_E_GeV']);strata=masks(d)
    rows=[];paired=[]
    for r in [1,2,3]:
        role=d['role']==r
        extra={f'run{v}':d['run']==v for v in np.unique(d['run'])}
        extra.update({f'component_{v}':d['component']==v for v in np.unique(d['component'])})
        extra.update({f'flux_{v}':d['flux']==v for v in np.unique(d['flux'])})
        for spectrum,weightname in [('original','weight'),('train_flat_map','flat_weight')]:
            for name,mask in {**strata,**extra}.items():
                ix=role&mask;w=d[weightname][ix]
                for model,p in pred.items():
                    rows.append(dict(role=r,spectrum=spectrum,stratum=name,N=int(ix.sum()),incoming_N=len(np.unique(d['key_id'][ix])),
                        families_N=len(np.unique(d['family'][ix])),ESS=float(w.sum()**2/(w@w)) if len(w) else 0,
                        model=model,**metrics(y[ix],p[ix],w)))
    for r in [2,3]:
        ids=np.flatnonzero(d['role']==r);family,first,gid=np.unique(d['family'][ids],return_index=True,return_inverse=True)
        component=d['component'][ids[first]];rng=np.random.default_rng(20261109200+r)
        draws=np.zeros((500,len(family)),np.int16)
        for c in np.unique(component):
            ix=np.flatnonzero(component==c)
            draws[:,ix]=rng.multinomial(len(ix),np.full(len(ix),1/len(ix)),size=500)
        # One family draw shared by every policy, stratum and spectrum.
        for spectrum,weightname in [('original','weight'),('train_flat_map','flat_weight')]:
            for name,mask in strata.items():
                use=mask[ids];ww=d[weightname][ids]*use
                mass=np.bincount(gid,weights=ww,minlength=len(family));den=draws@mass
                if not use.any():continue
                usable=den>0
                for candidate,reference in [('flat_cal','incoming_cal'),('flat_flatcal','incoming_flatcal'),
                    ('flat_raw','incoming_raw'),('flat_cal','traditional'),('flat_flatcal','traditional'),('incoming_cal','traditional')]:
                    a=pred[candidate][ids]-y[ids];b=pred[reference][ids]-y[ids]
                    qa=np.bincount(gid,weights=ww*a*a,minlength=len(family))
                    qb=np.bincount(gid,weights=ww*b*b,minlength=len(family))
                    ratios=np.sqrt((draws@qa)[usable]/(draws@qb)[usable])
                    center=float(np.sqrt(qa.sum()/qb.sum()))
                    low,high=np.quantile(ratios,[.025,.975])
                    rec=dict(role=r,spectrum=spectrum,stratum=name,N=int(use.sum()),candidate=candidate,reference=reference,
                        RMSE_ratio=center,low95=float(low),high95=float(high),valid_bootstrap_N=int(usable.sum()))
                    for tail,fun in [('total',lambda v:abs(np.expm1(v))>.5),('positive',lambda v:np.expm1(v)>.5),('negative',lambda v:np.expm1(v)<-.5)]:
                        v=np.bincount(gid,weights=ww*(fun(a).astype(float)-fun(b)),minlength=len(family))
                        delta=100*(draws@v)[usable]/den[usable]
                        lo,hi=np.quantile(delta,[.025,.975])
                        rec.update({tail+'_tail_delta_pp':float(100*v.sum()/mass.sum()),tail+'_tail_low95_pp':float(lo),tail+'_tail_high95_pp':float(hi)})
                    paired.append(rec)
    table('metrics.tsv',rows);table('paired.tsv',paired)
    # Original eight physics strata and unchanged guard values; no winner selection.
    protection=['all','E50_100','E100_200','E200_inf','pz50_100','pz50_100_trueE200','high_y','unconfirmed']
    decisions=[]
    for spectrum in ['original','train_flat_map']:
        for candidate,reference in [('flat_cal','incoming_cal'),('flat_flatcal','incoming_flatcal')]:
            rr=[v for v in paired if v['spectrum']==spectrum and v['candidate']==candidate and v['reference']==reference]
            low=[v for v in rr if v['stratum'] in ['E50_100','E100_200']]
            two_low=len(low)==4 and all(v['RMSE_ratio']<=.95 and v['high95']<1 for v in low)
            guards=all(v['high95']<=(1.01 if v['stratum']=='all' else 1.03) for v in rr if v['stratum'] in protection and v['stratum'] not in ['E50_100','E100_200'])
            tails=all(v[k+'_tail_high95_pp']<=2 for v in rr if v['stratum'] in protection for k in ['total','positive','negative'])
            traditional=[v for v in paired if v['spectrum']==spectrum and v['candidate']==candidate and v['reference']=='traditional' and v['stratum'] in ['E50_100','E100_200']]
            noninferiority=len(traditional)==4 and all(v['high95']<=1.05 for v in traditional)
            superiority=len(traditional)==4 and all(v['high95']<1 for v in traditional)
            decisions.append(dict(spectrum=spectrum,candidate=candidate,reference=reference,two_low_5pct_gain=two_low,
                RMSE_guard_pass=guards,tail_guard_pass=tails,traditional_two_low_noninferiority=noninferiority,
                traditional_two_low_superiority=superiority,development_extension=two_low and guards and tails and noninferiority,
                independent_confirmation=False))
    save('decisions.json',dict(decisions=decisions,automatic_promotion=False,blind_confirmation=False))
    fig,axes=plt.subplots(1,2,figsize=(11,4.4),sharey=True)
    for ax,spectrum in zip(axes,['original','train_flat_map']):
        for j,(label,reference,shift) in enumerate([('flat / incoming','incoming_cal',-.07),('flat / traditional','traditional',.07)]):
            values=[next(v for v in paired if v['role']==3 and v['spectrum']==spectrum and v['stratum']==s and v['candidate']=='flat_cal' and v['reference']==reference)
                    for s in ['E50_100','E100_200']]
            centers=np.array([v['RMSE_ratio'] for v in values]);lo=np.array([v['low95'] for v in values]);hi=np.array([v['high95'] for v in values])
            ax.errorbar(np.arange(2)+shift,centers,yerr=[centers-lo,hi-centers],fmt='o',capsize=4,label=label)
        ax.axhline(1,color='black',lw=1);ax.axhline(1.05,color='grey',lw=1,ls=':')
        ax.set_xticks([0,1],['50–100 GeV','100–200 GeV']);ax.set_title(spectrum);ax.set_xlabel('True neutrino energy');ax.grid(alpha=.2);ax.legend()
    axes[0].set_ylabel('log-energy RMSE ratio (95% conditional interval)')
    fig.suptitle('Direct62 energy-bin-flat retraining; new held-out development split')
    fig.tight_layout();fig.savefig(OUT/'low_energy_comparison.png',dpi=160);fig.savefig(OUT/'low_energy_comparison.svg');plt.close(fig)
    train=d['role']==1;edges=np.r_[json.loads((OUT/'protocol.json').read_text())['weights']['edges_GeV'],np.inf]
    before=np.bincount(d['energy_bin'][train],weights=d['weight'][train],minlength=8)
    after=np.bincount(d['energy_bin'][train],weights=d['flat_weight'][train],minlength=8)
    fig,ax=plt.subplots(figsize=(9,4.3));positions=np.arange(8)
    ax.bar(positions-.2,before,width=.4,label='Incoming weight');ax.bar(positions+.2,after,width=.4,label='Energy-bin-flat weight')
    labels=[f'{int(a)}–{int(b)}' if np.isfinite(b) else f'≥{int(a)}' for a,b in zip(edges[:-1],edges[1:])]
    ax.set_xticks(positions,labels,rotation=25);ax.set_xlabel('Training true neutrino energy / GeV');ax.set_ylabel('Sum of training weights')
    ax.set_title('Same training rows and total weight; no weight clipping');ax.legend();fig.tight_layout()
    fig.savefig(OUT/'training_weight_spectrum.png',dpi=160);fig.savefig(OUT/'training_weight_spectrum.svg');plt.close(fig)
    for path in OUT.glob('*.svg'):
        path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
    save('report.json',dict(passed=True,metrics_rows_N=len(rows),paired_rows_N=len(paired),bootstrap=500,
        scope='Family-paired conditional MC, original and frozen train-map spectra; source/system/refit/selection uncertainty absent',
        **resources(tick,cpu)))
    print(decisions,flush=True)


if __name__=='__main__':main()
