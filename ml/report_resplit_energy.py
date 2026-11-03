"""Stage87 weighted evaluation; distinguish incoming-conditional and source evidence."""
import csv
import json

import numpy as np

from support_augmentation import arrays,save,table,begin,resources
from resplit_energy import OUT,ART,CACHE

TAILS=['tail50','positive_tail50','negative_tail50']


def strata(d):
    e,p,f=d['truth_E_GeV'],d['pz'],d['y_lepton'];valid=d['label_physical']
    return dict(all=np.ones(len(e),bool),E50_100=(e>=50)&(e<100),E100_200=(e>=100)&(e<200),E200_inf=e>=200,
        pz50_100=p<100,pz50_100_trueE200=(p<100)&(e>=200),high_y=valid&(f>=.8),unconfirmed=~d['confirmed'],
        confirmed_low_transfer=d['confirmed']&valid&(f<.2),input_missing=d['input_missing'],fit_failure=d['fit_failure'],
        response_nominal=~(d['input_missing']|d['wave_invalid']|d['fit_failure']|d['calo_invalid']),
        negative_valid_raw=d['negative_valid_raw'],E200_400=(e>=200)&(e<400),E400_800=(e>=400)&(e<800),
        E800_1600=(e>=800)&(e<1600),E1600_3200=(e>=1600)&(e<3200),E3200_6400=(e>=3200)&(e<6400),E6400_inf=e>=6400)


def wquantile(v,w,qs):
    ix=np.argsort(v,kind='stable');v=v[ix];w=w[ix];pos=(np.cumsum(w)-.5*w)/w.sum()
    return np.interp(qs,pos,v)


def metrics(y,pred,w):
    names=['log_RMSE','median_bias_pct','mean_bias_pct','R68_pct','tail50_pct','positive_tail50_pct','negative_tail50_pct']
    if not len(y):return dict.fromkeys(names,'未测量')
    err=pred-y;rel=np.expm1(err);q=wquantile(rel,w,[.16,.5,.84]);avg=lambda v:float(np.average(v,weights=w))
    return dict(log_RMSE=np.sqrt(avg(err**2)),median_bias_pct=float(q[1]*100),mean_bias_pct=100*avg(rel),R68_pct=float((q[2]-q[0])*50),
                tail50_pct=100*avg(abs(rel)>.5),positive_tail50_pct=100*avg(rel>.5),negative_tail50_pct=100*avg(rel<-.5))


def incoming_draws(d,seed):
    keys,first,gid=np.unique(d['key_id'],return_index=True,return_inverse=True);comp=d['component'][first]
    rng=np.random.default_rng(seed);w=np.zeros((500,len(keys)),np.int16)
    for c in sorted(set(comp)):
        ix=np.flatnonzero(comp==c);w[:,ix]=rng.multinomial(len(ix),np.full(len(ix),1/len(ix)),size=500)
    return keys,gid,w


def proper_scores(head,pz,truth,edges,ratios,b,T):
    """CRPS(logE) from fixed16x32 latent quadrature; approximate, not MC toys."""
    from transfer_posterior import numpy_parameters,nodes,M,log_energy_density
    import torch
    lp,mr,ms,sr,ss=numpy_parameters(head,b,T);xr,wr=nodes(16);xs,ws=nodes(32)
    rs=mr[:,:,None,None]+sr[:,:,None,None]*xr[None,None,:,None]
    s=ms[:,:,None,None]+ss[:,:,None,None]*xs[None,None,None,:]
    onef=np.concatenate([.9+.1/(1+np.exp(np.clip(s[:,:1],-700,700))),.9/(1+np.exp(np.clip(s[:,1:],-700,700)))],axis=1)
    z=np.log(M+pz[:,None,None,None]*np.exp(rs))-np.log(onef)
    z=z.reshape(len(pz),-1);weights=(np.exp(lp)[:,:,None,None]*wr[None,None,:,None]*ws[None,None,None,:]).reshape(len(pz),-1)
    ix=np.argsort(z,axis=1);z=np.take_along_axis(z,ix,axis=1);weights=np.take_along_axis(weights,ix,axis=1)
    bins=np.clip(np.searchsorted(edges,np.exp(z),side='right')-1,0,8);result={}
    for name,ratio in ratios.items():
        w=weights*ratio[bins];w/=w.sum(1)[:,None];cum=np.cumsum(w,axis=1)
        result[name+'_CRPS_logE']=(w*abs(z-np.log(truth)[:,None])).sum(1)-(w*z*(2*cum-1-w)).sum(1)
    return result


def report():
    start=begin();d=arrays(ART/'predictions.npz');y=np.log(d['truth_E_GeV']);masks=strata(d)
    policies=dict(traditional=np.log(d['pz']/.8),direct_raw=d['direct_raw'],direct_cal=d['direct_cal'],
        bounded_raw=d['bounded_raw'],bounded_cal=d['bounded_cal'],posterior_raw=d['posterior_raw'],
        posterior_training=d['posterior_training_median'],posterior_nominal=d['posterior_nominal_median'],
        posterior_flat=d['posterior_flat_median'],posterior_pressure=d['posterior_pressure_median'])
    rr=[];paired=[];coverage=[];draws={};sources=[]
    for role,code in [('train',1),('cal',2),('test',3)]:
        use=d['role']==code;ids=np.flatnonzero(use);a={k:v[use] for k,v in d.items() if len(v.shape)>0 and v.shape[0]==len(use)}
        keys,gid,bw=incoming_draws(a,2026110387+code);draws[role+'_key']=keys;draws[role+'_weights']=bw
        blocks,bi=np.unique(a['block'],return_inverse=True)
        bycomp={c:len({b for b in blocks if b.startswith(c+':')}) for c in ['pi','k','charm','mixed']}
        source_estimable=all(n>=2 for n in bycomp.values() if n)
        sources.append(dict(role=role,source_groups=len(np.unique(a['group'])),connected_blocks=len(blocks),
            blocks_pi=bycomp['pi'],blocks_k=bycomp['k'],blocks_charm=bycomp['charm'],source_interval_estimable=source_estimable))
        for name,mask in masks.items():
            ix=ids[mask[use]];small=mask[use];n=len(ix);w=d['weight'][ix];wk=np.bincount(gid[small],weights=w,minlength=len(keys));den=bw@wk
            support=dict(N=n,unique_incoming=len(np.unique(d['key_id'][ix])),groups=len(np.unique(d['group'][ix])),
                blocks=len(np.unique(d['block'][ix])),weight_sum=float(w.sum()))
            for policy,pred in policies.items():
                for weighting,ww in [('incoming',w),('record',np.ones(n))]:
                    rr.append(dict(role=role,stratum=name,policy=policy,weighting=weighting,**support,**metrics(y[ix],pred[ix],ww)))
            if n:
                losses={k:bw@np.bincount(gid[small],weights=w*(v[ix]-y[ix])**2,minlength=len(keys)) for k,v in policies.items()}
                for candidate in ['bounded_cal','posterior_nominal']:
                    for ref in ['traditional','direct_cal']:
                        good=(den>0)&(losses[ref]>0);val=np.sqrt(losses[candidate][good]/losses[ref][good]);ci=np.quantile(val,[.025,.975])
                        row=dict(role=role,stratum=name,candidate=candidate,reference=ref,**support,
                            RMSE_ratio=float(np.sqrt(np.average((policies[candidate][ix]-y[ix])**2,weights=w)/np.average((policies[ref][ix]-y[ix])**2,weights=w))),
                            conditional_low95=float(ci[0]),conditional_high95=float(ci[1]),valid_draws=int(good.sum()),source_low95='未测量',source_high95='未测量',
                            interval_scope='incoming-conditional within component; not source/retraining/response/research-selection coverage')
                        for tail in TAILS:
                            def indicator(v):
                                r=np.expm1(v[ix]-y[ix]);return r>.5 if tail.startswith('positive') else r<-.5 if tail.startswith('negative') else abs(r)>.5
                            diff=indicator(policies[candidate]).astype(float)-indicator(policies[ref]).astype(float)
                            bv=(bw@np.bincount(gid[small],weights=w*diff,minlength=len(keys)))[good]/den[good]*100
                            ci=np.quantile(bv,[.025,.975]);row.update({tail+'_delta_pp':float(100*np.average(diff,weights=w)),tail+'_conditional_low95_pp':float(ci[0]),tail+'_conditional_high95_pp':float(ci[1])})
                        paired.append(row)
            if role not in ['cal','test'] or not n:continue
            for prior in ['training','nominal','flat','pressure']:
                pit=d[f'posterior_{prior}_pit'][ix];es=d[f'posterior_{prior}_ESS_fraction'][ix]
                for level,lo,hi in [(68,'q16','q84'),(90,'q05','q95')]:
                    lower=d[f'posterior_{prior}_{lo}'][ix];upper=d[f'posterior_{prior}_{hi}'][ix]
                    covered=(y[ix]>=lower)&(y[ix]<=upper);good=den>0
                    bs=(bw@np.bincount(gid[small],weights=w*covered,minlength=len(keys)))[good]/den[good]
                    pm=(bw@np.bincount(gid[small],weights=w*pit,minlength=len(keys)))[good]/den[good]
                    ci=np.quantile(bs,[.025,.975]);pc=np.quantile(pm,[.025,.975])
                    coverage.append(dict(role=role,stratum=name,prior=prior,level=level,**support,coverage_pct=float(100*np.average(covered,weights=w)),
                        conditional_low95_pct=float(100*ci[0]),conditional_high95_pct=float(100*ci[1]),mean_PIT=float(np.average(pit,weights=w)),
                        mean_PIT_conditional_low95=float(pc[0]),mean_PIT_conditional_high95=float(pc[1]),median_width_logE=float(wquantile(upper-lower,w,[.5])[0]),
                        mean_width_logE=float(np.average(upper-lower,weights=w)),mean_ESS_fraction=float(np.average(es,weights=w)),
                        ESS_fraction_lt02_N=int((es<.2).sum()),source_interval='未测量'))
    table(OUT/'metrics.tsv',rr);table(OUT/'paired.tsv',paired);table(OUT/'posterior_coverage.tsv',coverage);table(OUT/'uncertainty_blocks.tsv',sources)
    np.savez_compressed(ART/'bootstrap.npz',**draws)
    # Proper scores and fixed ten-bin PIT reliability on new cal/test only.
    from transfer_posterior import prior_setup,log_energy_density
    import torch
    heads=arrays(ART/'posterior_parameters.npz');edges,ratios,_=prior_setup(d);scored={}
    select=np.flatnonzero((d['role']==2)|(d['role']==3));ridx=np.searchsorted(heads['row'],select)
    for j in range(0,len(select),256):
        ix=select[j:j+256];vv=heads['head'][ridx[j:j+256]]
        ss=proper_scores(vv,d['pz'][ix],d['truth_E_GeV'][ix],edges,ratios,float(heads['b']),float(heads['T']))
        for k,v in ss.items():scored.setdefault(k,np.full(len(y),np.nan))[ix]=v
    scoring=[];reliability=[];prior_ESS=[]
    pr=json.loads((OUT/'prior.json').read_text());ratio_values={k:np.array(v) for k,v in pr['ratios'].items()}
    for role,code in [('cal',2),('test',3)]:
        for name,m in masks.items():
            ix=np.flatnonzero(m&(d['role']==code))
            if not len(ix):continue
            w=d['weight'][ix]
            for prior,ratio in ratio_values.items():
                scoring.append(dict(role=role,stratum=name,prior=prior,N=len(ix),CRPS_logE=float(np.average(scored[prior+'_CRPS_logE'][ix],weights=w)),mean_logE_NLL=float(-np.average(d['posterior_'+prior+'_logscore'][ix],weights=w)),
                    approximation='fixed16 r x32 s quadrature; not an acceptance certificate'))
                bins=np.minimum((d[f'posterior_{prior}_pit'][ix]*10).astype(int),9)
                for k in range(10):reliability.append(dict(role=role,stratum=name,prior=prior,PIT_bin=k,weight=float(w[bins==k].sum()),fraction=float(w[bins==k].sum()/w.sum())))
                truth_bin=np.clip(np.searchsorted(edges,d['truth_E_GeV'][ix],side='right')-1,0,8);ww=w*ratio[truth_bin]
                prior_ESS.append(dict(role=role,stratum=name,prior=prior,N=len(ix),weight_sum=float(ww.sum()),record_ESS=float(ww.sum()**2/(ww@ww)),
                    base_record_ESS=float(w.sum()**2/(w@w)),ratio_at_cap_N=int(((ratio[truth_bin]==.1)|(ratio[truth_bin]==10)).sum())))
    table(OUT/'posterior_scores.tsv',scoring);table(OUT/'PIT_reliability.tsv',reliability);table(OUT/'prior_ESS.tsv',prior_ESS)
    gates=[];decisions={}
    protections=dict(all=1.01,E200_inf=1.03,pz50_100=1.03,pz50_100_trueE200=1.03,high_y=1.03,unconfirmed=1.03)
    for candidate in ['bounded_cal','posterior_nominal']:
        outcomes=[]
        for layer,limit,ref in [('E50_100',1.05,'traditional'),('E100_200',1.05,'traditional')]+[(k,v,'direct_cal') for k,v in protections.items()]:
            v=next(x for x in paired if x['role']=='test' and x['stratum']==layer and x['candidate']==candidate and x['reference']==ref)
            tail=next(x for x in paired if x['role']=='test' and x['stratum']==layer and x['candidate']==candidate and x['reference']=='direct_cal')
            ok=v['conditional_high95']<=limit;tails=all(tail[t+'_conditional_high95_pp']<=2 for t in TAILS);outcomes.append(ok and tails)
            gates.append(dict(candidate=candidate,stratum=layer,reference=ref,conditional_RMSE_upper95=v['conditional_high95'],limit=limit,
                conditional_RMSE_pass=ok,conditional_tail_pass=tails,source_certification=False,**{t+'_conditional_upper95_pp':tail[t+'_conditional_high95_pp'] for t in TAILS}))
        decisions[candidate]=dict(conditional_point_and_tail_gates=all(outcomes),independent_confirmation=False,
             source_intervals_available=False,meaning='development decision only; no new blind/source robustness claim')
    table(OUT/'gates.tsv',gates);save(OUT/'decisions.json',dict(main_posterior='nominal_cal_median',versions=decisions,
        conclusion='retain existing deployment; no independent/source-level confirmation; assess fixed development candidates',
        authority='user-authorized resplit and retraining; old F7 metrics not a held-out comparator on reassigned data'))
    figure(rr,coverage)
    save(OUT/'report_resources.json',resources(start));print(json.dumps(decisions,indent=2),flush=True)


def figure(rows,coverage):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(1,2,figsize=(11,4.2),layout='constrained')
    layers=['E50_100','E100_200','all','pz50_100_trueE200','high_y','unconfirmed']
    for policy in ['traditional','direct_cal','bounded_cal','posterior_nominal']:
        y=[next(r['log_RMSE'] for r in rows if r['role']=='test' and r['weighting']=='incoming' and r['policy']==policy and r['stratum']==s) for s in layers]
        ax[0].plot(np.arange(len(layers)),y,'o-',label=policy,ms=3)
    ax[0].set(xticks=np.arange(len(layers)),xticklabels=['E50–100','E100–200','all','low pz, high E','high-y','unconfirmed'],ylabel='Incoming-weighted log-RMSE');ax[0].tick_params(axis='x',rotation=35);ax[0].legend(fontsize=8)
    for level in [68,90]:
        v=[next(r for r in coverage if r['role']=='test' and r['prior']=='nominal' and r['level']==level and r['stratum']==s) for s in layers]
        ax[1].plot(np.arange(len(layers)),[r['coverage_pct'] for r in v],'o-',label=str(level)+'% interval')
        ax[1].axhline(level,color='grey',ls='--',lw=.7)
    ax[1].set(xticks=np.arange(len(layers)),xticklabels=['E50–100','E100–200','all','low pz, high E','high-y','unconfirmed'],ylabel='Posterior coverage [%]');ax[1].tick_params(axis='x',rotation=35);ax[1].legend(fontsize=8)
    fig.suptitle('Stage87: regrouped existing data; test held out from new fits, previously studied')
    path=OUT/'resplit_evaluation.svg';fig.savefig(path);plt.close(fig);path.write_text('\n'.join(s.rstrip() for s in path.read_text().splitlines())+'\n')


if __name__=='__main__':report()
