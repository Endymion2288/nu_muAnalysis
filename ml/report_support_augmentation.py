#!/usr/bin/env python3
"""Frozen stage71 ensemble, source-paired gates and diagnostics; no fitting."""
import json
import numpy as np
from support_augmentation import REPO, OUT, ART, CACHE, LOW, COST, TAILS, arrays, begin, resources, save, table, masks, metrics, indicator, boot_weights


def review_arrays():
    if (CACHE/'input.npz').exists():
        d=arrays(CACHE/'input.npz');a=arrays(ART/'predictions.npz')
        return d,a,json.loads(str(a['metadata_json']))
    # The retained comparison contains everything needed to reproduce metrics;
    # the large prepared feature cache and duplicate predictions can be removed.
    d=arrays(ART/'comparison.npz')
    return d,d,json.loads((OUT/'fit.json').read_text())


def main():
    start=begin();p=json.loads((OUT/'protocol.json').read_text());d,a,md=review_arrays()
    assert md['formal_fits']==3 and md['status']=='completed'
    offset=float(np.mean(np.log(d['cal_truth_E_GeV'])-a['cal_raw_log'].mean(axis=0)))
    assert offset==md['offset_log']
    save(OUT/'calibration.json',dict(offset_log=offset,cal_N=8440,policy=p['calibration'],main_candidate='augmented_cal',additional_offsets=0))
    records=[];paired=[];sources=[];seeds=[];bootstrap_checks=[]
    for role in ['cal','eval']:
        dd={k:d[role+'_'+k] for k in ['truth_E_GeV','pz','y_lepton','confirmed','missing','group','source','component']}
        np.testing.assert_array_equal(a[role+'_row'],d[role+'_row'])
        y=np.log(dd['truth_E_GeV']);raw=a[role+'_raw_log'].mean(axis=0)
        logs=dict(mu=np.log(dd['pz']/.8),F7=d[role+'_F7'],augmented_raw=raw,augmented_cal=raw+offset)
        mm=masks(dd);groups,gid,w=boot_weights(dd,p['bootstrap_seed']+(role=='cal'),500)
        assert len(groups)==(16 if role=='cal' else 22)
        for key,m in mm.items():
            sp=dict(N=int(m.sum()),groups=len(np.unique(dd['group'][m])),sources=len(np.unique(dd['source'][m])))
            for name,pred in logs.items():records.append(dict(sample=role,stratum=key,model=name,**sp,**metrics(y[m],pred[m])))
            for j,seed in enumerate(p['seeds']):
                seeds.append(dict(sample=role,stratum=key,seed=seed,policy='same single ensemble offset; diagnostic, no candidate selection',**sp,**metrics(y[m],a[role+'_raw_log'][j,m]+offset)))
            if not m.any():continue
            den=w@np.bincount(gid[m],minlength=len(groups))
            sums={name:w@np.bincount(gid[m],weights=(pred[m]-y[m])**2,minlength=len(groups)) for name,pred in logs.items()}
            for name in ['augmented_raw','augmented_cal']:
                for ref in ['mu','F7']:
                    error=logs[name]-y;reference=logs[ref]-y;good=(den>0)&(sums[ref]>0)
                    valid=int(good.sum()) if sp['groups']>=3 else 0
                    ratio=float(np.sqrt(np.mean(error[m]**2)/np.mean(reference[m]**2)))
                    lo,hi=np.quantile(np.sqrt(sums[name][good]/sums[ref][good]),[.025,.975]) if valid else ['未测量','未测量']
                    row=dict(sample=role,stratum=key,model=name,reference=ref,**sp,RMSE_ratio=ratio,
                             RMSE_ratio_low95=float(lo) if valid else lo,RMSE_ratio_high95=float(hi) if valid else hi,
                             gain_pct=100*(1-ratio),gain_low95_pct=float(100*(1-hi)) if valid else '未测量',
                             gain_high95_pct=float(100*(1-lo)) if valid else '未测量',bootstrap_valid=valid,bootstrap_invalid=500-valid)
                    for tail in TAILS:
                        diff=100*(indicator(error,tail).astype(float)-indicator(reference,tail).astype(float))
                        vals=w@np.bincount(gid[m],weights=diff[m],minlength=len(groups))
                        low,high=np.quantile(vals[good]/den[good],[.025,.975]) if valid else ['未测量','未测量']
                        row.update({tail+'_delta_pp':float(diff[m].mean()),tail+'_low95_pp':float(low) if valid else low,tail+'_high95_pp':float(high) if valid else high})
                    paired.append(row)
            # Independent explicit event replication of three prespecified draws.
            if role=='eval':
                for rep in [0,1,2]:
                    idx=np.repeat(np.flatnonzero(m),w[rep,gid[m]])
                    if not len(idx):continue
                    direct=float(np.sqrt(np.mean((logs['augmented_cal'][idx]-y[idx])**2)/np.mean((logs['F7'][idx]-y[idx])**2)))
                    grouped=float(np.sqrt(sums['augmented_cal'][rep]/sums['F7'][rep]))
                    tail_diff=[]
                    for tail in TAILS[:3]:
                        direct_tail=100*np.mean(indicator(logs['augmented_cal'][idx]-y[idx],tail).astype(float)-indicator(logs['F7'][idx]-y[idx],tail).astype(float))
                        values=100*(indicator(logs['augmented_cal'][m]-y[m],tail).astype(float)-indicator(logs['F7'][m]-y[m],tail).astype(float))
                        grouped_tail=float(w[rep]@np.bincount(gid[m],weights=values,minlength=len(groups))/den[rep])
                        tail_diff.append(abs(direct_tail-grouped_tail))
                    bootstrap_checks.append(dict(stratum=key,replicate=rep,ratio_abs_diff=abs(direct-grouped),tail_pp_abs_diff=max(tail_diff)))
        for group in groups:
            for key in LOW+list(COST)+['input_missing','E3200_6400']:
                m=mm[key]&(dd['group']==group)
                if not m.any():continue
                for name,pred in logs.items():sources.append(dict(sample=role,group=str(group),stratum=key,model=name,N=int(m.sum()),**metrics(y[m],pred[m])))
    decisions={};gate_rows=[]
    for name in ['augmented_raw','augmented_cal']:
        def row(key,reference):return next(r for r in paired if r['sample']=='eval' and r['stratum']==key and r['model']==name and r['reference']==reference)
        recovery={k:row(k,'mu')['RMSE_ratio_high95']<=1.05 for k in LOW}
        breakthrough={k:row(k,'mu')['gain_low95_pct']>0 for k in LOW}
        protection={k:row(k,'F7')['RMSE_ratio_high95']<=limit for k,limit in COST.items()}
        tails={k:{tail:row(k,'F7')[tail+'_high95_pp']<=2 for tail in TAILS[:3]} for k in LOW+list(COST)}
        decisions[name]=dict(recovery=recovery,breakthrough=breakthrough,protection=protection,tail50=tails,
                             pass_all=all(recovery.values()) and all(protection.values()) and all(all(v.values()) for v in tails.values()))
        for k in LOW+list(COST):
            ref='mu' if k in LOW else 'F7';limit=1.05 if k in LOW else COST[k]
            gate_rows.append(dict(model=name,stratum=k,reference=ref,RMSE_upper95=row(k,ref)['RMSE_ratio_high95'],RMSE_limit=limit,
                                  RMSE_pass=row(k,ref)['RMSE_ratio_high95']<=limit,**{t+'_upper95_pp':row(k,'F7')[t+'_high95_pp'] for t in TAILS[:3]}))
    save(OUT/'decisions.json',dict(main_candidate='augmented_cal',versions=decisions,
         deployment='research candidate needs untouched confirmation' if decisions['augmented_cal']['pass_all'] else 'retain F7',
         policy='no selecting raw/cal, seed, round or further methods; developed evaluation only'))
    for name,rr in [('metrics',records),('paired',paired),('source_metrics',sources),('seed_metrics',seeds),('gates',gate_rows)]:table(OUT/(name+'.tsv'),rr)
    save(OUT/'bootstrap_validation.json',dict(passed=True,draw_indices=[0,1,2],checks=len(bootstrap_checks),
         max_ratio_abs_diff=max(r['ratio_abs_diff'] for r in bootstrap_checks),max_tail_pp_abs_diff=max(r['tail_pp_abs_diff'] for r in bootstrap_checks),
         fixed_prediction_only=True,refits=0,offset_reestimates=0))
    assert max(r['ratio_abs_diff'] for r in bootstrap_checks)<1e-12 and max(r['tail_pp_abs_diff'] for r in bootstrap_checks)<1e-12
    # Preserve the compact developed comparison without the prepared feature cache.
    fields={k:v for k,v in d.items() if k.startswith(('cal_','eval_')) and not k.endswith('_x')}
    fields.update({k:v for k,v in a.items() if k!='metadata_json'})
    np.savez_compressed(ART/'comparison.npz',**fields)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(11,4.2),constrained_layout=True)
    strata=['E50_100','E100_200','all','E200_inf','pz50_100','high_y','unconfirmed','E3200_6400']
    for name in ['mu','F7','augmented_raw','augmented_cal']:
        v=[next(r['log_RMSE'] for r in records if r['sample']=='eval' and r['stratum']==k and r['model']==name) for k in strata]
        axes[0].plot(np.arange(len(strata)),v,'o-',label=name,ms=3)
    axes[0].set_xticks(np.arange(len(strata)),strata,rotation=45,ha='right');axes[0].set_ylabel('log-RMSE');axes[0].legend(fontsize=8)
    edges=[50,75,100,150,200,400,800,1600,3200,6400]
    for name in ['mu','F7','augmented_cal']:
        values=[next(r['median_bias_pct'] for r in records if r['sample']=='eval' and r['stratum']==f'E{lo}_{hi}' and r['model']==name) for lo,hi in zip(edges[:-1],edges[1:])]
        axes[1].plot(np.sqrt(np.array(edges[:-1])*edges[1:]),values,'o-',label=name,ms=3)
    axes[1].set_xscale('log');axes[1].set_xlabel('True neutrino energy [GeV]');axes[1].set_ylabel('Median relative bias [%]');axes[1].axhline(0,color='black',lw=.6);axes[1].legend(fontsize=8)
    fig.suptitle('Stage71: one fixed F7 augmentation, +28 pi events; developed evaluation')
    fig.savefig(OUT/'augmentation.png',dpi=150);plt.close(fig)
    save(OUT/'report_resources.json',resources(start));print(json.dumps(decisions,indent=2))


if __name__=='__main__':main()
