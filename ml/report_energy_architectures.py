"""Stage94 four-process weighted evaluation; analytic residual-MDN probabilities."""
import argparse
import json
import math
import multiprocessing as mp
import time
from pathlib import Path

import numpy as np
from scipy.special import logsumexp,ndtr

from audited_features import REPO
from support_augmentation import arrays,save,table,begin,resources
from report_resplit_energy import strata,metrics,incoming_draws,wquantile

OUT=REPO/'workbook/stage94_energy_ml'
CACHE=REPO/'ntuples/energy_ml_stage94'
ART=REPO/'ml/artifacts/stage94'
SEED=2026110494
G=None


def mixture(head,anchor):
    lp=head[:,:3].astype(float);lp-=logsumexp(lp,axis=1)[:,None]
    mu=head[:,3:6].astype(float)+anchor[:,None]
    sig=.05+np.logaddexp(0.,head[:,6:9].astype(float))
    return np.exp(lp),mu,sig


def probability_summary(w,mu,sig,y):
    def cdf(z):return np.sum(w*ndtr((z[:,None]-mu)/sig),axis=1)
    quantiles=[];residual=0.
    for p in [.05,.16,.5,.84,.95]:
        lo=np.min(mu-12*sig,axis=1);hi=np.max(mu+12*sig,axis=1)
        for _ in range(55):
            mid=(lo+hi)/2;above=cdf(mid)>=p;hi=np.where(above,mid,hi);lo=np.where(above,lo,mid)
        q=(lo+hi)/2;residual=max(residual,float(np.max(abs(cdf(q)-p))));quantiles.append(q)
    ld=logsumexp(np.log(w)-np.log(sig)-.5*((y[:,None]-mu)/sig)**2-.5*math.log(2*math.pi),axis=1)
    assert np.isfinite(ld).all() and residual<1e-10
    return dict(quantiles=np.column_stack(quantiles),PIT=cdf(y),logscore=ld,max_root_residual=residual)


def prepare():
    start=begin();d=arrays(CACHE/'evaluation_input.npz');raw=arrays(ART/'point_predictions.npz');head=arrays(ART/'MDN_heads.npz');part=arrays(CACHE/'cal_partition.npz')
    np.testing.assert_array_equal(d['row'],raw['row'])
    ih=np.searchsorted(d['row'],head['row']);np.testing.assert_array_equal(d['row'][ih],head['row'])
    for code in [1,2,3]:
        m=d['role']==code;_,inverse=np.unique(d['key_id'][m],return_inverse=True);np.testing.assert_allclose(np.bincount(inverse,weights=d['weight'][m]),1,atol=1e-12)
    y=np.log(d['truth_E_GeV']);anchor=np.log(d['pz']/.8);cal=np.flatnonzero(d['role']==2)
    ii=np.searchsorted(part['row'],d['row'][cal]);np.testing.assert_array_equal(part['row'][ii],d['row'][cal]);post=cal[part['subrole'][ii]==2];pw=part['weight'][ii][part['subrole'][ii]==2]
    base=arrays(REPO/'ml/artifacts/stage87/predictions.npz');ib=np.searchsorted(base['row'],d['row']);np.testing.assert_array_equal(base['row'][ib],d['row'])
    policies=dict(traditional=anchor,direct_raw=base['direct_raw'][ib],direct_cal=base['direct_cal'][ib],bounded_cal=base['bounded_cal'][ib])
    distributions={};offsets=[]
    for name,v in raw.items():
        if name=='row':continue
        delta=float(np.average(y[post]-v[post],weights=pw));policies[name+'_raw']=v.astype(float);policies[name+'_cal']=v.astype(float)+delta
        offsets.append(dict(model=name,offset_logE=delta,fit_role='cal_post',N=len(post),incoming_weight_sum=float(pw.sum())))
        if not name.startswith('E'):continue
        hh=[head[name]] if name!='E_ensemble' else [head[k] for k in sorted(head) if k!='row']
        ww,mm,ss=zip(*[mixture(h,anchor[ih]) for h in hh]);w=np.column_stack(ww)/len(hh);mu=np.column_stack(mm);sig=np.column_stack(ss)
        point=(w*mu).sum(1);assert np.max(abs(point-v[ih]))<3e-6
        for suffix,shift in [('raw',0.),('cal',delta)]:
            value=probability_summary(w,mu+shift,sig,y[ih]);full={}
            for k,a in value.items():
                if np.ndim(a):
                    full[k]=np.full((len(y),)+a.shape[1:],np.nan);full[k][ih]=a
                else:full[k]=a
            distributions[name+'_'+suffix]=full
    for name in ['traditional','direct_raw']:
        delta=float(np.average(y[post]-policies[name][post],weights=pw));policies[name+'_post']=policies[name]+delta
        offsets.append(dict(model=name,offset_logE=delta,fit_role='cal_post',N=len(post),incoming_weight_sum=float(pw.sum())))
    # Retain stage92 as a named comparator without recalibration or new posterior integration.
    oldpoint=np.full(len(y),np.nan)
    for role,code in [('cal',2),('test',3)]:
        m=d['role']==code;old=arrays(REPO/f'ntuples/energy_ml_stage92/predictions_{role}.npz');np.testing.assert_array_equal(d['row'][m],old['row']);oldpoint[m]=old['accurate_quantiles'][:,2]
    policies['posterior92']=oldpoint
    table(OUT/'offsets.tsv',offsets)
    save(OUT/'probability_numerics.json',dict(passed=True,models=list(distributions),max_quantile_residual=max(v['max_root_residual'] for v in distributions.values()),analytic_Normal_mixture=True,new_posterior_integrations=0,**resources(start)))
    return d,policies,distributions


def initialize():
    global G
    G=prepare()


def group_masks(d):
    masks=strata(d)
    masks.update(X_pz50_100=d['pz']<100,X_pz100_200=(d['pz']>=100)&(d['pz']<200),X_pz200_plus=d['pz']>=200,
                 X_status_valid=~(d['wave_invalid']|d['fit_failure']|d['calo_invalid']|d['input_missing']),X_status_other=d['wave_invalid']|d['fit_failure']|d['calo_invalid']|d['input_missing'])
    for var in ['calo','activity']:
        for j in [-1,0,1,2]:masks[f'X_{var}_{j}']=d['X_'+var]==j
    return masks


def one_task(task):
    role,layer=task;d,policies,distributions=G;code={'train':1,'cal':2,'test':3}[role]
    use=np.flatnonzero(d['role']==code);sub={k:v[use] for k,v in d.items()};keys,gid,draw=incoming_draws(sub,2026110387+code)
    mask=group_masks(sub)[layer];ix=use[mask];ww=d['weight'][ix];n=len(ix)
    support=dict(role=role,stratum=layer,N=n,incoming=len(np.unique(d['key_id'][ix])),weight_sum=float(ww.sum()))
    points=[];paired=[];coverage=[];reliability=[];scores=[];validation=[]
    if not n:return points,paired,coverage,reliability,scores,validation
    y=np.log(d['truth_E_GeV'][ix]);smallgid=gid[mask];den=draw@np.bincount(smallgid,weights=ww,minlength=len(keys));good=den>0
    available={k:v[ix] for k,v in policies.items() if np.isfinite(v[ix]).all()}
    names=list(available);matrix=np.column_stack([available[k]-y for k in names]);losskey=np.zeros((len(keys),len(names)))
    np.add.at(losskey,smallgid,ww[:,None]*matrix**2);drawloss=draw@losskey
    for j,name in enumerate(names):
        for weighting,w in [('incoming',ww),('record',np.ones(n))]:
            r=dict(policy=name,weighting=weighting,**support,**metrics(y,available[name],w));points.append(r)
            check=float(np.sqrt(np.dot(w,matrix[:,j]**2)/w.sum()));assert abs(check-r['log_RMSE'])<1e-12
    comparisons=[]
    for name in names:
        if name.startswith(tuple('ABCDE')) and name.endswith('_cal'):
            comparisons.extend((name,ref) for ref in ['traditional','direct_cal','posterior92','traditional_post','direct_raw_post'] if ref in names)
    for a,b in [('B','A'),('C','B'),('D','C'),('E','C')]:comparisons.append((f'{a}_{SEED}_cal',f'{b}_{SEED}_cal'))
    tails={}
    for sign in ['total','positive','negative']:
        rel=np.expm1(matrix);flag=abs(rel)>.5 if sign=='total' else rel>.5 if sign=='positive' else rel<-.5
        key=np.zeros_like(losskey);np.add.at(key,smallgid,ww[:,None]*flag);tails[sign]=(np.average(flag,weights=ww,axis=0),draw@key)
    for candidate,reference in comparisons:
        a=names.index(candidate);b=names.index(reference);valid=good&(drawloss[:,b]>0)
        ratios=np.sqrt(drawloss[valid,a]/drawloss[valid,b]);lo,hi=np.quantile(ratios,[.025,.975])
        r=dict(candidate=candidate,reference=reference,**support,RMSE_ratio=float(np.sqrt(losskey[:,a].sum()/losskey[:,b].sum())),conditional_low95=float(lo),conditional_high95=float(hi),valid_draws=int(valid.sum()),source95='未测量')
        for sign,(point,bs) in tails.items():
            delta=(bs[valid,a]-bs[valid,b])/den[valid]*100;ci=np.quantile(delta,[.025,.975]);r.update({sign+'_tail_delta_pp':float((point[a]-point[b])*100),sign+'_tail_low95_pp':float(ci[0]),sign+'_tail_high95_pp':float(ci[1])})
        # Independent root-mean-square point calculation.
        direct=float(np.sqrt(np.average((available[candidate]-y)**2,weights=ww)/np.average((available[reference]-y)**2,weights=ww)));assert abs(direct-r['RMSE_ratio'])<1e-12
        paired.append(r)
    if role in ['cal','test']:
        for name,p in distributions.items():
            q=p['quantiles'][ix];pit=p['PIT'][ix];ld=p['logscore'][ix]
            pm=(draw@np.bincount(smallgid,weights=ww*pit,minlength=len(keys)))[good]/den[good];pci=np.quantile(pm,[.025,.975])
            for level,lo,hi in [(68,1,3),(90,0,4)]:
                flag=(y>=q[:,lo])&(y<=q[:,hi]);bs=(draw@np.bincount(smallgid,weights=ww*flag,minlength=len(keys)))[good]/den[good];ci=np.quantile(bs,[.025,.975])
                coverage.append(dict(model=name,level=level,**support,coverage_pct=float(np.average(flag,weights=ww)*100),conditional_low95_pct=float(ci[0]*100),conditional_high95_pct=float(ci[1]*100),mean_PIT=float(np.average(pit,weights=ww)),mean_PIT_low95=float(pci[0]),mean_PIT_high95=float(pci[1]),mean_width_logE=float(np.average(q[:,hi]-q[:,lo],weights=ww)),meanPIT_uniformity_required=layer=='all' or layer.startswith('X_'),sparse=n<20,target='incoming empirical role mix; no extra prior reweight'))
            bins=np.minimum((pit*10).astype(int),9)
            for j in range(10):reliability.append(dict(model=name,**support,PIT_bin=j,weight=float(ww[bins==j].sum()),fraction=float(ww[bins==j].sum()/ww.sum())))
            scores.append(dict(model=name,**support,logE_NLL=float(-np.average(ld,weights=ww))))
    validation.append(dict(**support,point_metrics_checked=len(points),paired_points_checked=len(paired),draws=500,scope='fixed-source/component incoming conditional; no refit/cal/source/response/research-selection coverage',passed=True))
    return points,paired,coverage,reliability,scores,validation


def main(processes):
    start=begin()
    global G
    G=prepare();d,_,_=G;tasks=[]
    for role,code in [('train',1),('cal',2),('test',3)]:
        for layer in group_masks({k:v[d['role']==code] for k,v in d.items()}):
            if role=='train' and layer.startswith('X_'):continue
            tasks.append((role,layer))
    # fork preserves the already loaded arrays; no repeated decompression/preparation in workers.
    tick=time.perf_counter()
    with mp.get_context('fork').Pool(processes=processes) as pool:results=pool.map(one_task,tasks,chunksize=1)
    combined=[sum((r[j] for r in results),[]) for j in range(6)]
    for name,rr in zip(['metrics','paired','coverage','PIT_reliability','scores','independent_checks'],combined):table(OUT/(name+'.tsv'),rr)
    gates=[]
    for r in combined[1]:
        if r['role']!='test':continue
        layer=r['stratum'];ref=r['reference'];lim=1.05 if layer in ['E50_100','E100_200'] else 1.01 if layer=='all' else 1.03
        if layer not in ['E50_100','E100_200','all','E200_inf','pz50_100','pz50_100_trueE200','high_y','unconfirmed']:continue
        if ref!=('traditional' if layer in ['E50_100','E100_200'] else 'direct_cal'):continue
        tail=next(a for a in combined[1] if a['role']=='test' and a['candidate']==r['candidate'] and a['stratum']==layer and a['reference']=='direct_cal')
        gates.append(dict(candidate=r['candidate'],stratum=layer,reference=ref,upper95=r['conditional_high95'],limit=lim,RMSE_pass=r['conditional_high95']<=lim,tail_pass=all(tail[t+'_tail_high95_pp']<=2 for t in ['total','positive','negative'])))
    table(OUT/'gates.tsv',gates)
    child=resource_usage();save(OUT/'report_resources.json',dict(processes=processes,tasks=len(tasks),parallel_wall_s=time.perf_counter()-tick,child_CPU_s=child,**resources(start)))
    save(OUT/'report_complete.json',dict(passed=True,roles={str(k):int((d['role']==k).sum()) for k in [1,2,3]},finite_points=True,tasks=len(tasks),models=json.loads((OUT/'worker_completion.json').read_text())['new_fits'],point_tail_joint_pass={name:all(r['RMSE_pass'] and r['tail_pass'] for r in gates if r['candidate']==name) for name in sorted({r['candidate'] for r in gates})},source95=False,model_promotion=False))
    print((OUT/'report_complete.json').read_text(),flush=True)


def resource_usage():
    import resource
    u=resource.getrusage(resource.RUSAGE_CHILDREN);return u.ru_utime+u.ru_stime


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--processes',type=int,default=4);args=p.parse_args();main(args.processes)
