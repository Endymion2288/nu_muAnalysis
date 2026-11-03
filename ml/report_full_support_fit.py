"""Stage84 fixed prediction risks, source intervals and stage82 mechanism control."""
import csv
import json

import numpy as np

from full_support_fit import OUT, CACHE, ART
from k_support_curve import masks
from support_augmentation import arrays, save, table, metrics, indicator, boot_weights, LOW, COST, TAILS, begin, resources


def review():
    if (CACHE/'input.npz').exists():
        d=arrays(CACHE/'input.npz'); a=arrays(ART/'predictions.npz')
    else:
        d=arrays(ART/'comparison.npz'); a=d
    return d,a,json.loads((OUT/'fit.json').read_text())


def main():
    start=begin(); p=json.loads((OUT/'protocol.json').read_text()); d,a,md=review()
    assert md['formal_fits']==3 and md['status']=='completed'
    offset=float(np.mean(np.log(d['cal_truth_E_GeV'])-a['cal_raw_log'].mean(0))); assert offset==md['offset_log']
    save(OUT/'calibration.json',dict(offset_log=offset,cal_N=8440,additional_offsets=0,main='pooled_cal'))
    rr=[]; paired=[]; sources=[]; seeds=[]
    for role in ['cal','eval']:
        dd={k:d[role+'_'+k] for k in ['truth_E_GeV','pz','y_lepton','confirmed','missing','group','source','component']}
        np.testing.assert_array_equal(a[role+'_row'],d[role+'_row'])
        y=np.log(dd['truth_E_GeV']);raw=a[role+'_raw_log'].mean(0)
        logs=dict(mu=np.log(dd['pz']/.8),F7=d[role+'_F7'],stage82_full=d[role+'_stage82'],pooled_raw=raw,pooled_cal=raw+offset)
        mm=masks(dd); groups,gid,w=boot_weights(dd,p['bootstrap_seed']+(role=='cal'),500)
        assert len(groups)==(16 if role=='cal' else 22)
        for key,m in mm.items():
            support=dict(N=int(m.sum()),groups=len(np.unique(gid[m])),sources=len(np.unique(dd['source'][m])))
            for name,pred in logs.items():rr.append(dict(sample=role,stratum=key,model=name,**support,**metrics(y[m],pred[m])))
            for j,seed in enumerate(p['seeds']):
                seeds.append(dict(sample=role,stratum=key,seed=seed,policy='same ensemble offset; diagnostic only',**support,**metrics(y[m],a[role+'_raw_log'][j,m]+offset)))
            if not m.any():continue
            den=w@np.bincount(gid[m],minlength=len(groups))
            sums={name:w@np.bincount(gid[m],weights=(v[m]-y[m])**2,minlength=len(groups)) for name,v in logs.items()}
            for name in ['pooled_raw','pooled_cal']:
                for ref in ['mu','F7','stage82_full']:
                    e,r=logs[name]-y,logs[ref]-y; good=(den>0)&(sums[ref]>0)
                    valid=int(good.sum()) if support['groups']>=3 else 0
                    lo,hi=np.quantile(np.sqrt(sums[name][good]/sums[ref][good]),[.025,.975]) if valid else ['未测量','未测量']
                    row=dict(sample=role,stratum=key,model=name,reference=ref,**support,
                        RMSE_ratio=float(np.sqrt(np.mean(e[m]**2)/np.mean(r[m]**2))),
                        RMSE_ratio_low95=float(lo) if valid else lo,RMSE_ratio_high95=float(hi) if valid else hi,
                        bootstrap_valid=valid,bootstrap_invalid=500-valid)
                    for tail in TAILS:
                        diff=100*(indicator(e,tail).astype(float)-indicator(r,tail).astype(float))
                        values=w@np.bincount(gid[m],weights=diff[m],minlength=len(groups))
                        low,high=np.quantile(values[good]/den[good],[.025,.975]) if valid else ['未测量','未测量']
                        row.update({tail+'_delta_pp':float(diff[m].mean()),tail+'_low95_pp':float(low) if valid else low,tail+'_high95_pp':float(high) if valid else high})
                    paired.append(row)
        for group in groups:
            for key,m in mm.items():
                use=m&(dd['group']==group)
                if not use.any():continue
                for name,v in logs.items():sources.append(dict(sample=role,group=str(group),stratum=key,model=name,N=int(use.sum()),**metrics(y[use],v[use])))
    decisions={}; gates=[]
    for name in ['pooled_raw','pooled_cal']:
        def row(k,ref):return next(r for r in paired if r['sample']=='eval' and r['stratum']==k and r['model']==name and r['reference']==ref)
        recovery={k:row(k,'mu')['RMSE_ratio_high95']<=1.05 for k in LOW}
        protection={k:row(k,'F7')['RMSE_ratio_high95']<=v for k,v in COST.items()}
        tails={k:{tail:row(k,'F7')[tail+'_high95_pp']<=2 for tail in TAILS[:3]} for k in LOW+list(COST)}
        decisions[name]=dict(recovery=recovery,protection=protection,tail50=tails,
                            pass_all=all(recovery.values()) and all(protection.values()) and all(all(v.values()) for v in tails.values()))
        for k in LOW+list(COST):
            ref='mu' if k in LOW else 'F7'; limit=1.05 if k in LOW else COST[k]
            gates.append(dict(model=name,stratum=k,reference=ref,RMSE_upper95=row(k,ref)['RMSE_ratio_high95'],RMSE_limit=limit,
                RMSE_pass=row(k,ref)['RMSE_ratio_high95']<=limit,**{t+'_upper95_pp':row(k,'F7')[t+'_high95_pp'] for t in TAILS[:3]}))
    save(OUT/'decisions.json',dict(main='pooled_cal',versions=decisions,
        conclusion='development candidate; requires untouched confirmation' if decisions['pooled_cal']['pass_all'] else 'retain F7; close fixed full-support experiment',
        interval_scope='fixed predictions and offsets, developed cal/eval; exclude refit/augmentation sampling/offset estimation/genealogy/response/research choice; not joint coverage'))
    for name,rows in [('metrics',rr),('paired',paired),('source_metrics',sources),('seed_metrics',seeds),('gates',gates)]:table(OUT/(name+'.tsv'),rows)
    comparison={k:v for k,v in d.items() if k.startswith(('cal_','eval_')) and not k.endswith('_x')}
    comparison.update({r+'_raw_log':a[r+'_raw_log'] for r in ['cal','eval']})
    np.savez_compressed(ART/'comparison.npz',**comparison)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(11,4.4),constrained_layout=True)
    keys=['E50_100','E100_200','all','pz50_100','high_y','unconfirmed','E3200_6400']
    labels=['E50–100','E100–200','all','pz50–100','high-y','unconfirmed','E3200–6400']
    for name in ['mu','F7','stage82_full','pooled_cal']:
        vals=[next(r['log_RMSE'] for r in rr if r['sample']=='eval' and r['stratum']==k and r['model']==name) for k in keys]
        axes[0].plot(range(len(keys)),vals,'o-',label=name,ms=3)
    axes[0].set_xticks(range(len(keys)),labels,rotation=40,ha='right'); axes[0].set_ylabel('log-RMSE');axes[0].legend(fontsize=8)
    edges=[50,75,100,150,200,400,800,1600,3200,6400]
    for name in ['mu','F7','stage82_full','pooled_cal']:
        v=[next(r['median_bias_pct'] for r in rr if r['sample']=='eval' and r['stratum']==f'E{lo}_{hi}' and r['model']==name) for lo,hi in zip(edges[:-1],edges[1:])]
        axes[1].plot(np.sqrt(np.array(edges[:-1])*edges[1:]),v,'o-',label=name,ms=3)
    axes[1].set_xscale('log');axes[1].axhline(0,color='black',lw=.6);axes[1].set_xlabel('True neutrino energy [GeV]');axes[1].set_ylabel('Median relative bias [%]');axes[1].legend(fontsize=8)
    fig.suptitle('Stage84: +7720 full pi+K support, fixed 3 seeds; developed eval')
    fig.savefig(OUT/'full_support.png',dpi=150);plt.close(fig)
    save(OUT/'report_resources.json',resources(start))
    print(json.dumps(decisions,indent=2))


if __name__=='__main__':main()
