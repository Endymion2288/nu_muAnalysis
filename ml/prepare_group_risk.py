#!/usr/bin/env python3
"""Freeze stage68 folds/dual policy after synthetic arithmetic and small resource QA."""
from datetime import datetime,timezone
from pathlib import Path
import tempfile
import shutil
import numpy as np
from group_risk import (OUT,REPO,LOW,COST,configuration,inputs,coefficients,dual_step,fit_pair,masks,begin,resources,save)


def main():
    start=begin();OUT.mkdir(exist_ok=True);assert not (OUT/'protocol.json').exists()
    cfg=configuration();p=dict(stage=68,starting_commit='3cc3955',seed=2026110368,rounds=400,
        features=cfg['features'],feature_version=cfg['version'],xgboost=dict(cfg['xgboost']),
        request_cpus=1,request_memory_MB=3000,formal_jobs=4,formal_fits=8,cpu_budget_s=10800,wall_per_job_s=2700,
        retained_budget_bytes=20000000,dual_step=.05,dual_decay_rounds=50,dual_increment_clip=10.,
        initial_cost_dual=1.,cost_dual_upper=25.,low_probability_floor=1e-8,
        low_groups=LOW,RMSE_cost_limits=COST,
        primal='same train-mean logE base_score for C/R; directly predict logE; one depth5 tree per round,400 terminal only',
        dual='before each tree evaluate train risk ratios; low simplex exponentiated centered ratios; projected cost ascent on ratio-limit^2; eta=.05/sqrt(1+t/50); clip dual increments +/-10 and cost dual[0,25], low probability floor1e-8; no error clipping',
        weight_scale='sum_g dual_g*1_g/(N_g*reference_MSE_g), normalize mean event weight to1 to retain F7 regularization/Hessian scale; overlap contributions add',
        references='low uses pz0/.8 train MSE; protection uses completed matched C fit in-sample train MSE, no held/cal/eval reference',
        inference='only62 audited reco X, no truth/y/identity; no input imputation; typed NaN preserved',
        calibration='one separate mean log offset for final C/R on all8440cal; report raw and calibrated, main candidate R_cal',
        checkpoint='only terminal400; no best/feasible iteration selection, repair, averaging or retries',
        bootstrap_replicates=500,bootstrap_seed=2026110368,recovery_ratio_upper95_max=1.05,
        max_tail50_increase_pp=2.,locked_test=False,new_ROOT_RDO_production=0,coverage_toys=0,
        preparation='small resource pilot at most256 train events20 rounds perfamily; not an extra scientific candidate; synthetic gradient and normalization QA',
        pilot_train_points=256,pilot_rounds=20)
    # Pure weighted quadratic derivative, overlap and mean-Hessian checks.
    rng=np.random.default_rng(68);n=24;gg=[np.arange(n)<8,(np.arange(n)>=8)&(np.arange(n)<16),np.ones(n,bool),np.arange(n)>=8,np.arange(n)%2==0,np.arange(n)%3==0,np.arange(n)%4==0]
    den=np.array([.02,.04,.08,.09,.1,.11,.12]);q=np.array([.4,.6]);lam=np.array([1.,2.,0.,.5,.8]);w,norm=coefficients(gg,den,q,lam)
    err=rng.normal(size=n);direction=rng.normal(size=n);step=1e-6
    def value(e):return .5*sum(mult*np.mean(e[m]**2)/ref for mult,m,ref in zip(np.r_[q,lam],gg,den))/(n*norm)
    numeric=(value(err+step*direction)-value(err-step*direction))/(2*step);analytic=np.mean(w*err*direction)
    assert abs(numeric-analytic)<1e-8 and abs(w.mean()-1)<1e-12
    np.testing.assert_allclose(np.mean(w*direction**2),(value(err+step*direction)+value(err-step*direction)-2*value(err))/step**2,rtol=.002,atol=.002)
    q2,l2,_,_=dual_step(q,lam,np.array([4.,1.,2.,2.,2.,2.,2.]),0,p);assert q2[0]>q[0] and np.all(l2>=lam)
    d=inputs();tr=d['role']=='train';groups=np.unique(d['group'][tr]);parent={str(g):str(g) for g in groups}
    def root(a):
        while parent[a]!=a:parent[a]=parent[parent[a]];a=parent[a]
        return a
    identities={};duplicate_links=0
    for g,identity in zip(d['group'][tr],d['incoming'][tr]):
        key=tuple(identity);g=str(g)
        if key in identities:
            a,b=root(g),root(identities[key])
            if a!=b:parent[max(a,b)]=min(a,b);duplicate_links+=1
        else:identities[key]=g
    units={}
    for g in groups:units.setdefault(root(str(g)),[]).append(str(g))
    total=np.zeros(3,int);loads=np.zeros((3,3),int);fold={}
    units_list=[]
    for unit,gs in units.items():
        count=np.array([int((tr&np.isin(d['group'],gs)&(d['component']==c)).sum()) for c in ['pi','k','charm']])
        units_list.append((unit,gs,count))
    for unit,gs,count in sorted(units_list,key=lambda x:(-int(x[2].sum()),x[0])):
        c=int(count.argmax());f=min(range(3),key=lambda k:(loads[c,k],total[k],k))
        for g in gs:fold[g]=f
        loads[:,f]+=count;total[f]+=count.sum()
    train_fold=np.array([fold[str(g)] for g in d['group'][tr]])
    keys={}
    for identity,f in zip(d['incoming'][tr],train_fold):
        key=tuple(identity)
        if key in keys:assert keys[key]==f
        keys[key]=f
    p.update(fold_by_group=fold,fold_event_N=total.tolist(),identity_union_links=duplicate_links,
        folds='component-balanced greedy by training event counts over unions of conservative groups connected by exact incoming(pdg,px,py,pz); no heldout labels/residuals',
        protected_counts=[dict(role=r,N=int((d['role']==r).sum()),groups=len(np.unique(d['group'][d['role']==r])),missing=int(d['missing'][d['role']==r].sum())) for r in ['train','cal','eval']])
    # Labels are used only to ensure arithmetic pilot has nonempty groups, not to choose policy.
    chosen=[];mm=masks(d)
    for key in LOW+list(COST):chosen.extend(np.flatnonzero(tr&mm[key])[:24].tolist())
    chosen=np.unique(chosen);chosen=np.r_[chosen,np.setdiff1d(np.flatnonzero(tr),chosen)[:max(0,256-len(chosen))]]
    small={k:v[chosen] for k,v in d.items()};scratch=Path(tempfile.mkdtemp(prefix='stage68_arithmetic_'))
    try:
        C,R,diag=fit_pair(small['x'],np.log(small['truth_E_GeV']),small['pz'],masks(small),p,scratch,rounds=20)
        pilot_fit_CPU=diag['C_resources']['cpu_s']+diag['R_resources']['cpu_s']
    finally:shutil.rmtree(scratch)
    p.update(frozen_utc=datetime.now(timezone.utc).isoformat(),pilot_pair_CPU_s=pilot_fit_CPU)
    save(OUT/'pilot.json',dict(**resources(start),synthetic_gradient_error=abs(numeric-analytic),synthetic_checks_pass=True,
        pilot_N=len(chosen),pilot_rounds_per_family=20,pilot_fits_not_candidates=2,pilot_pair_CPU_s=pilot_fit_CPU,
        pilot_C_resources=diag['C_resources'],pilot_R_resources=diag['R_resources'],retained_pilot_models=0))
    save(OUT/'protocol.json',p);print(p)


if __name__=='__main__':main()
