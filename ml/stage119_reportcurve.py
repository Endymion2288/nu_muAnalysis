"""Paired energy learning curves, original gates and conditional confirmation size."""
import csv
import json
import multiprocessing as mp
from pathlib import Path

import numpy as np

from stage119_curve_common import ROOT,OUT,CACHE,LAYERS,load,masks,weights,table

ART=ROOT/'ml/artifacts/stage119';G=None


def ci(x):
    x=np.asarray(x);x=x[np.isfinite(x)]
    return list(map(float,np.quantile(x,[.025,.975]))) if len(x)>=475 else [None,None]


def metrics(err,w):
    rel=np.expm1(err);avg=lambda v:float(np.average(v,weights=w))
    ix=np.argsort(rel,kind='stable');q=np.interp([.16,.5,.84],(np.cumsum(w[ix])-.5*w[ix])/w.sum(),rel[ix])
    return dict(log_RMSE=np.sqrt(avg(err**2)),mean_bias_pct=100*avg(rel),median_bias_pct=100*q[1],R68_pct=50*(q[2]-q[0]),
        tail50_pct=100*avg(abs(rel)>.5),positive_tail50_pct=100*avg(rel>.5),negative_tail50_pct=100*avg(rel<-.5))


def task(spec):
    role,layer=spec;d,p,v=G[role];ix=v['ix'][v['masks'][layer]];gid=v['gid'][v['masks'][layer]];w=v['w'][v['masks'][layer]]
    names=list(p);err=np.column_stack([p[k][ix]-np.log(d['truth_E_GeV'][ix]) for k in names])
    assert np.isfinite(err).all()
    draw=v['draw'];nk=draw.shape[1];agg=np.zeros((nk,len(names)));np.add.at(agg,gid,w[:,None]*err**2)
    den=draw@np.bincount(gid,weights=w,minlength=nk);bt=draw@agg;valid=den>0
    support=dict(role=role,stratum=layer,N=len(ix),incoming=len(np.unique(gid)),weight_sum=float(w.sum()),ESS=float(w.sum()**2/(w@w)))
    points=[]
    for j,k in enumerate(names):
        lo,hi=ci(np.sqrt(bt[valid,j]/den[valid]));points.append(dict(model=k,**support,**metrics(err[:,j],w),RMSE_low95=lo,RMSE_high95=hi))
    rel=np.expm1(err);tails={}
    for sign,flag in [('total',abs(rel)>.5),('positive',rel>.5),('negative',rel<-.5)]:
        a=np.zeros_like(agg);np.add.at(a,gid,w[:,None]*flag);tails[sign]=(a.sum(0)/w.sum(),draw@a)
    pairs=[(k,r) for k in names if k not in ['direct_cal','traditional'] for r in ['direct_cal','traditional']]
    pairs += [('curve_4N_cal','curve_1N_cal'),('curve_4N_raw','curve_1N_raw')]
    for control in ['old_same_N_cal','old_same_N_fixed_cal']:
        if control in names:pairs += [('curve_4N_cal',control)]
    rows=[];checks=[]
    # Independently recompute the designated augmented candidate in row space.
    sw=draw[:,gid]*w if layer in LAYERS else None
    for a,b in pairs:
        j,k=names.index(a),names.index(b);good=valid&(bt[:,k]>0);ratio=np.full(500,np.nan);ratio[good]=np.sqrt(bt[good,j]/bt[good,k])
        lo,hi=ci(ratio);r=dict(candidate=a,reference=b,**support,RMSE_ratio=float(np.sqrt(agg[:,j].sum()/agg[:,k].sum())),low95=lo,high95=hi,valid_draws=int(good.sum()))
        for sign,(central,t) in tails.items():
            lo,hi=ci(100*(t[good,j]-t[good,k])/den[good]);r.update({sign+'_tail_delta_pp':float(100*(central[j]-central[k])),sign+'_tail_low95_pp':lo,sign+'_tail_high95_pp':hi})
        rows.append(r)
        if a=='augmented_cal' and sw is not None:
            ind=ci(np.sqrt((sw@err[:,j]**2)/(sw@err[:,k]**2)));error=max(abs(ind[0]-r['low95']),abs(ind[1]-r['high95']))
            for sign,flag in [('total',abs(rel)>.5),('positive',rel>.5),('negative',rel<-.5)]:
                ind=ci(100*(sw@(flag[:,j].astype(float)-flag[:,k].astype(float)))/sw.sum(1))
                error=max(error,abs(ind[0]-r[sign+'_tail_low95_pp']),abs(ind[1]-r[sign+'_tail_high95_pp']))
            assert error<1e-10;checks.append(dict(**support,candidate=a,reference=b,interval_max_abs=error))
    return points,rows,checks


def power(d,p,ix):
    rows=[]
    for layer,mask in masks({k:v[ix] for k,v in d.items()}).items():
        use=ix[mask]
        if not len(use):continue
        keys,gid,count=np.unique(d['incoming'][use],axis=0,return_inverse=True,return_counts=True);w=1/count[gid]
        y=np.log(d['truth_E_GeV'][use]);a=p['augmented_cal'][use]-y;b=p['direct_cal'][use]-y
        # A 5% RMSE reduction corresponds to a 0.9025 squared-loss ratio.
        # Planning variance is measured for the paired candidate/reference
        # contrast at the boundary; normal approximation, 80% power, two-sided95%.
        contrast=a*a-.9025*b*b;family=np.bincount(gid,weights=w*contrast)
        variance=float(np.var(family,ddof=1)) if len(keys)>1 else None;delta=.0975*float(np.mean(np.bincount(gid,weights=w*b*b)))
        needed=int(np.ceil((1.959963984540054+ .8416212335729143)**2*variance/delta**2)) if variance is not None and delta>0 else None
        rows.append(dict(stratum=layer,development_rows=len(use),development_incoming=len(keys),contrast_variance=variance,
            target_RMSE_ratio=.95,reference_MSE=float(np.average(b*b,weights=w)),normal_80pct_power_incoming=needed,
            caveat='conditional incoming proxy iid normal approximation; no certified parent/source/system uncertainty, no confirmation opened'))
        for sign,fa,fb in [('total',abs(np.expm1(a))>.5,abs(np.expm1(b))>.5),('positive',np.expm1(a)>.5,np.expm1(b)>.5),('negative',np.expm1(a)<-.5,np.expm1(b)<-.5)]:
            family=np.bincount(gid,weights=w*(fa.astype(float)-fb.astype(float)));v=float(np.var(family,ddof=1)) if len(keys)>1 else None
            rows[-1][sign+'_1pp_halfwidth_incoming']=int(np.ceil(1.959963984540054**2*v/.01**2)) if v is not None else None
    table('confirmation_power.tsv',rows)


def main(fit_filename='fits.json'):
    global G
    old=load('ntuples/energy_ml_stage119/old_input.npz');new=load('ntuples/energy_ml_stage119/curve_input.npz')
    reference=load('ml/artifacts/stage119/reference_predictions.npz');fits=json.loads((OUT/fit_filename).read_text())
    policies={}
    for side,d in [('old',old),('new',new)]:
        use=d['role']>0 if side=='old' else d['role']!=3
        traditional=np.full(len(use),np.nan);traditional[use]=np.log(d['pz'][use]/.8)
        policies[side]=dict(direct_cal=reference[side],traditional=traditional)
    for fit in fits['results']:
        pred=load(f'ml/artifacts/stage119/{fit["policy"]}_predictions.npz')
        for side in ['old','new']:
            for version in ['raw','cal']:policies[side][fit['policy']+'_'+version]=pred[side+'_'+version]
    G={}
    for role,side,d,mask,seed in [('old_cal','old',old,old['role']==2,2026110389),('old_test','old',old,old['role']==3,2026110390),
            ('new_development','new',new,(new['role']==2)&(new['kind']=='expansion'),20261105195)]:
        ix=np.flatnonzero(mask);sd={k:v[ix] for k,v in d.items()};keys,first,gid=np.unique(sd['incoming'],axis=0,return_index=True,return_inverse=True)
        w=weights(sd['incoming']);rng=np.random.default_rng(seed);draw=np.zeros((500,len(keys)),np.int16)
        for c in sorted(set(sd['component'][first])):
            use=np.flatnonzero(sd['component'][first]==c);draw[:,use]=rng.multinomial(len(use),np.full(len(use),1/len(use)),size=500)
        if side=='old':np.testing.assert_allclose(w,d['weight'][ix],atol=1e-12,rtol=0)
        G[role]=(d,policies[side],dict(ix=ix,gid=gid,w=w,draw=draw,masks=masks(sd)))
    tasks=[(r,k) for r,(_,_,v) in G.items() for k,z in v['masks'].items() if z.any()]
    with mp.get_context('fork').Pool(6) as pool:result=pool.map(task,tasks)
    points=sum((v[0] for v in result),[]);paired=sum((v[1] for v in result),[]);checks=sum((v[2] for v in result),[])
    table('curve_metrics.tsv',points);table('curve_paired.tsv',paired);table('curve_validation.tsv',checks)
    gates=[]
    for role in G:
        for candidate in policies['old']:
            if candidate in ['direct_cal','traditional']:continue
            for layer in LAYERS:
                ref='traditional' if layer in LAYERS[:2] else 'direct_cal';limit=1.05 if ref=='traditional' else 1.01 if layer=='all' else 1.03
                match=[r for r in paired if r['role']==role and r['stratum']==layer and r['candidate']==candidate and r['reference']==ref]
                t=[r for r in paired if r['role']==role and r['stratum']==layer and r['candidate']==candidate and r['reference']=='direct_cal']
                hi=match[0]['high95'] if match else None
                tails={s:(t[0][s+'_tail_high95_pp'] if t else None) for s in ['total','positive','negative']}
                gates.append(dict(role=role,candidate=candidate,stratum=layer,reference=ref,RMSE_upper95=hi,limit=limit,RMSE_pass=hi is not None and hi<=limit,
                    tail_pass=all(v is not None and v<=2 for v in tails.values()),**{s+'_tail_upper95_pp':v for s,v in tails.items()}))
    table('curve_gates.tsv',gates)
    power(new,policies['new'],G['new_development'][2]['ix'])
    # Validate historical reference scalars independently of the new-model fit.
    prior=list(csv.DictReader((ROOT/'workbook/stage94_energy_ml/metrics.tsv').open(),delimiter='\t'));controls=[]
    for row in points:
        if not row['role'].startswith('old_'):continue
        matches=[r for r in prior if r['weighting']=='incoming' and r['role']==row['role'][4:] and r['stratum']==row['stratum'] and r['policy']==row['model']]
        if matches:
            for key in ['log_RMSE','median_bias_pct','mean_bias_pct','R68_pct','tail50_pct','positive_tail50_pct','negative_tail50_pct']:
                error=abs(row[key]-float(matches[0][key]));assert error<1e-10;controls.append(dict(role=row['role'],stratum=row['stratum'],model=row['model'],metric=key,abs_error=error))
    assert controls;table('curve_reference_validation.tsv',controls)
    reserved=new['role']==3
    for k,p in policies['new'].items():assert np.isnan(p[reserved]).all()
    # No reserved labels/risks are used by this report or the planning variance.
    summary=dict(passed_validation=True,paired_checks=len(checks),reference_controls=len(controls),reserved_predictions=0,
        augmented_joint={role:all(r['RMSE_pass'] and r['tail_pass'] for r in gates if r['role']==role and r['candidate']=='augmented_cal') for role in G},
        limitations=['old test developed','incoming proxies not complete GENIE ancestry','only downstream expansion','conditional source fixed bootstrap','no new confirmation opened'])
    (OUT/'curve_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    protocol=json.loads((OUT/'curve_protocol.json').read_text());fig,axes=plt.subplots(1,3,figsize=(12,3.5),layout='constrained')
    for ax,layer in zip(axes,LAYERS[:3]):
        for role in ['new_development','old_test']:
            rows=[next(r for r in points if r['role']==role and r['stratum']==layer and r['model']==f'curve_{f}N_cal') for f in [1,2,4]]
            v=np.array([r['log_RMSE'] for r in rows]);lo=np.array([r['RMSE_low95'] for r in rows]);hi=np.array([r['RMSE_high95'] for r in rows])
            ax.errorbar(protocol['scales'],v,yerr=[v-lo,hi-v],marker='o',label=role)
        ax.set_title(layer);ax.set_xlabel('Training incoming proxies');ax.set_ylabel('log-energy RMSE');ax.set_xscale('log',base=2)
    axes[0].legend(fontsize=8);fig.savefig(OUT/'learning_curve.png',dpi=150);plt.close(fig)
    print(summary,flush=True)


if __name__=='__main__':main()
