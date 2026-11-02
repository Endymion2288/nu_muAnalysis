#!/usr/bin/env python3
"""One bounded stage63 batch; no energy training or coverage toys."""
import json
import time
import traceback

import numpy as np

from joint_response import (OUT,ART,REPRESENTATIONS,histogram,TemplateLikelihood,
    information,fraction_to_r,begin,resources,save)
from report_expert_combination import boot_weights


def support(d,take):
    return dict(N=int(take.sum()),sources=int(len(np.unique(d['group'][take]))),
        low_N=int((take&d['low']).sum()),high_N=int((take&~d['low']).sum()),
        true50_100_N=int((take&(d['truth_E_GeV']<100)).sum()),
        high_y_mix_N=int((take&~d['low']&(d['pz']<100)&(d['y_lepton']>=.8)).sum()),
        missing_inputs_N=int((take&d['missing']).sum()),
        unconfirmed_N=int((take&~d['confirmed']).sum()),
        negative_correction_N=int((take&(d['S']<d['M'])).sum()))


def main():
    start=begin();OUT.mkdir(exist_ok=True)
    assert not (OUT/'fits.json').exists(),'No repeat formal inference'
    p=json.loads((OUT/'protocol_v2.json').read_text())
    with np.load(ART/'observables.npz') as z:d={k:z[k] for k in z.files}
    train=d['role']=='train';unit=np.ones(len(train));f0=p['f0'];n=p['N_selected']
    templates={name:histogram(d[name][train],d['low'][train],unit[train],p['category_counts'][name]) for name in REPRESENTATIONS}
    assert templates['M_mu'].sum(axis=1).tolist()==[4331,37116]
    assert not set(d['group'][train])&set(d['group'][~train])
    fits=[];support_rows=[]
    for role in ['train','cal','eval']:
        take=d['role']==role;support_rows.append(dict(role=role,source='pooled',**support(d,take)))
        for group in np.unique(d['group'][take]):
            support_rows.append(dict(role=role,source=str(group),**support(d,take&(d['group']==group))))
    cases=[('train','reference',train,'nominal',None,1.)]
    for role in ['cal','eval']:
        take=d['role']==role
        cases.append((role,'pooled',take,'nominal',None,1.))
        for pressure,config in p['pressures'].items():
            for factor in config['factors']:
                cases.append((role,'pooled',take,f'{pressure}_{factor}',pressure,factor))
        for group in np.unique(d['group'][take]):
            cases.append((role,str(group),take&(d['group']==group),'nominal',None,1.))
    for ci,(role,source,take,variant,pressure,factor) in enumerate(cases):
        weights=unit[take].copy();low=d['low'][take];ftrue=float(low.mean())
        if pressure=='low_internal':weights[d['truth_E_GeV'][take]<100]*=factor
        if pressure=='high_y_mix':weights[(~low)&(d['pz'][take]<100)&(d['y_lepton'][take]>=.8)]*=factor
        for component in [low,~low]:
            if component.any():weights[component]*=component.sum()/weights[component].sum()
        assert np.all(weights>0)
        np.testing.assert_allclose(weights[low].sum()/weights.sum(),ftrue,rtol=0,atol=1e-14)
        for name in REPRESENTATIONS:
            count=histogram(d[name][take],low,weights,p['category_counts'][name]);data=count.sum(axis=0)/weights.sum()*n
            for finite in [False,True]:
                tick=time.perf_counter();result=TemplateLikelihood(templates[name],data,p,finite).fit(f0)
                rtrue=fraction_to_r(ftrue,f0);sigma=result['sigma_f'];fh=result['f_hat']
                regular=not result['boundary'] and sigma is not None and 0<ftrue<1
                sigma_r=sigma*(1-f0)/f0/(1-fh)**2 if regular else None
                result.update(role=role,source=source,variant=variant,representation=name,finite_MC=finite,
                    f_true=ftrue,r_true=rtrue,case_N=int(take.sum()),weighted_ESS=float(weights.sum()**2/(weights@weights)),
                    data_counts=data.tolist(),sigma_r=sigma_r,
                    bias_f_sigma=float((fh-ftrue)/sigma) if regular else None,
                    bias_r_sigma=float((result['r_hat']-rtrue)/sigma_r) if regular else None,
                    truth_in_profile68=bool(result['f_low68']<=ftrue<=result['f_high68']),
                    wall_s=time.perf_counter()-tick)
                if not 0<ftrue<1:result['relative_sigma_r']=None
                fits.append(result)
        print(f'case {ci+1}/{len(cases)} {role} {source} {variant}',flush=True)
    # Fixed-response Fisher bootstrap only: component-stratified train sources.
    dd={k:v[train] for k,v in d.items()};groups,gid,draw=boot_weights(dd,p['bootstrap_seed'],p['bootstrap_replicates'])
    bootstrap={};reference=[];template_rows=[]
    for name in REPRESENTATIONS:
        group_mc=np.array([histogram(dd[name][gid==g],dd['low'][gid==g],np.ones((gid==g).sum()),p['category_counts'][name]) for g in range(len(groups))])
        samples=np.einsum('bg,gck->bck',draw,group_mc)
        bootstrap[name]=[information(mc,f0,n,True) for mc in samples]
        assert all(v is not None for v in bootstrap[name])
        a,b=templates[name]/templates[name].sum(axis=1)[:,None]
        for j,(ml,mh) in enumerate(templates[name].T):
            template_rows.append(dict(representation=name,bin=j,low_MC_N=int(ml),high_MC_N=int(mh),a=float(a[j]),b=float(b[j])))
        for finite in [False,True]:
            sigma=information(templates[name],f0,n,finite)
            reference.append(dict(representation=name,finite_MC=finite,sigma_f=sigma,relative_sigma_r=sigma/(f0*(1-f0))))
    ratios={}
    for name in ['M_mu','J_joint']:
        ratio=np.asarray(bootstrap[name])/bootstrap['S_scalar']
        nominal=information(templates[name],f0,n,True)/information(templates['S_scalar'],f0,n,True)
        ratios[name+'_over_S']=dict(nominal=nominal,low95=float(np.quantile(ratio,.025)),high95=float(np.quantile(ratio,.975)),replicates=len(ratio))
    # All prespecified acceptance conditions concern finite-MC pooled results.
    pooled=[r for r in fits if r['finite_MC'] and r['source']=='pooled']
    joint=[r for r in pooled if r['representation']=='J_joint'];criteria=p['acceptance']
    differences=[]
    for j in joint:
        s=next(r for r in pooled if r['role']==j['role'] and r['variant']==j['variant'] and r['representation']=='S_scalar')
        differences.append(dict(role=j['role'],variant=j['variant'],J_minus_S_abs_bias_sigma=abs(j['bias_r_sigma'])-abs(s['bias_r_sigma'])))
    nominal=max(abs(r['bias_r_sigma']) for r in joint if r['variant']=='nominal')
    stressed=max(abs(r['bias_r_sigma']) for r in joint if r['variant']!='nominal')
    difference=max(r['J_minus_S_abs_bias_sigma'] for r in differences)
    checks=dict(source_sigma_gain=ratios['J_joint_over_S']['high95']<criteria['sigma_ratio_J_over_S_upper95_lt'],
        pooled_nominal=nominal<=criteria['pooled_nominal_abs_bias_sigma_max'],
        pooled_pressure=stressed<=criteria['pooled_pressure_abs_bias_sigma_max'],
        pooled_bias_relative_to_scalar=difference<=criteria['J_minus_S_abs_bias_sigma_max'])
    save(OUT/'fits.json',fits);save(OUT/'support.json',support_rows);save(OUT/'templates.json',template_rows)
    save(OUT/'bootstrap.json',dict(groups=groups.tolist(),replicates=p['bootstrap_replicates'],ratios=ratios,sigma_f=bootstrap))
    save(OUT/'summary.json',dict(reference_Fisher=reference,ratios=ratios,checks=checks,robust_gain=all(checks.values()),
        largest_J_nominal_abs_bias_r_sigma=nominal,largest_J_pressure_abs_bias_r_sigma=stressed,
        largest_J_minus_S_abs_bias_sigma=difference,paired_bias=differences,
        exact_profile_fits=len(fits),energy_model_fits=0,coverage_toys=0,
        max_simplex_KKT=max(r['max_simplex_KKT'] for r in fits),
        convex_polish_calls=sum(r['convex_polish_calls'] for r in fits),
        fraction_profile_calls=sum(r['fraction_profile_calls'] for r in fits)))
    save(OUT/'batch_resources.json',resources(start))


if __name__=='__main__':
    try:main()
    except Exception:
        OUT.mkdir(exist_ok=True);(OUT/'failure.txt').write_text(traceback.format_exc());raise
