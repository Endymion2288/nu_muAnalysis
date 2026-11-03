#!/usr/bin/env python3
"""Synthetic convex arithmetic and small noncandidate deployment/resource QA."""
import scipy,sklearn,xgboost as xgb
from risk_complementarity import *


def main():
    start=begin();p=json.loads((OUT/'protocol.json').read_text());d=arrays(CACHE/'input.npz')
    assert scipy.__version__==p['scipy_version'] and sklearn.__version__==p['sklearn_version'] and xgb.__version__==p['xgboost_version']
    rng=np.random.default_rng(2026110378);n=4096
    energy=np.exp(rng.uniform(np.log(50),np.log(6400),n));y=np.log(energy)
    dd=dict(truth_E_GeV=energy,pz=np.exp(rng.uniform(np.log(50),np.log(200),n)),y_lepton=rng.uniform(0,1,n),confirmed=rng.random(n)>.2,missing=np.zeros(n,bool))
    x=rng.normal(size=(n,62)).astype('float32');x[::29,3]=np.nan;x[:,61]=np.nan
    h=np.c_[y+.15+.3*rng.normal(size=n),y-.12+.35*rng.normal(size=n),y-.2+.4*rng.normal(size=n)]
    # Region-dependent expert error; fixed synthetic labels, not physical evaluation.
    h[x[:,0]>0,1]+=.2;h[x[:,0]<0,0]+=.3
    part=fit_partition(x,h,y,p);leaf=route(x,part)
    assert part['median'][61]==0 and np.isfinite(transformed(x,np.array(part['median']))).all()
    mm={k:diagnostic_masks(dd)[k] for k in LOW+list(COST)}
    C=moment_matrices(h,y,leaf,mm,int(leaf.max())+1)
    w=rng.uniform(size=(int(leaf.max())+1,3));w/=w.sum(1)[:,None]
    eps=1e-6;key=LOW[0];g=gradient(C[key],w);fd=[]
    for j in range(w.size):
        direction=np.zeros_like(w);direction.ravel()[j]=eps
        fd.append((risk(C[key],w+direction)-risk(C[key],w-direction))/(2*eps))
    grad_diff=float(np.max(abs(np.array(fd)-g)));assert grad_diff<1e-8
    direct=float(np.mean((np.einsum('ij,ij->i',w[leaf[mm[key]]],h[mm[key]])-y[mm[key]])**2))
    risk_diff=abs(direct-risk(C[key],w));assert risk_diff<1e-12
    sols={};solstart=begin()
    for arm,l in [('Q0',np.zeros(n,int)),('Q_local',leaf)]:
        sol=solve_combination(h,y,l,dd,p);assert sol['solved'] and sol['secondary_solved'],sol
        sols[arm]=sol
    solver_resources=resources(solstart)
    # Only a deleted 512-row/two-round noncandidate checks weighted X/NaN interface and cost.
    tr=d['role']=='train';idx=np.r_[np.flatnonzero(tr)[:500],np.flatnonzero(tr&d['missing'])[:12]]
    xx=d['x'][idx];yy=np.log(d['truth_E_GeV'][idx]);ww=weights(d['truth_E_GeV'][idx],1.)[0]
    params=dict(p['xgboost'],seed=p['seed'],base_score=float(yy.mean()),boost_from_average=0)
    dm=xgb.DMatrix(xx,label=yy,weight=ww,feature_names=p['features'],nthread=1)
    fitstart=begin();model=xgb.train(params,dm,num_boost_round=2)
    pred=model.predict(xgb.DMatrix(xx,feature_names=p['features'],nthread=1));assert np.isfinite(pred).all()
    fit_resources=resources(fitstart)
    save(OUT/'pilot.json',dict(passed=True,gradient_max_abs_diff=grad_diff,risk_direct_max_abs_diff=risk_diff,
        synthetic_partition_N=n,synthetic_NaN_and_all_missing_checked=True,synthetic_problems=sols,
        synthetic_solver_resources=solver_resources,tiny_base_pilot_N=len(idx),tiny_base_rounds=2,pilot_model_retained=False,
        tiny_base_resources=fit_resources,pilot_is_scientific_candidate=False,formal_base_fits=0,formal_partition_fits=0,
        versions=dict(scipy=scipy.__version__,sklearn=sklearn.__version__,xgboost=xgb.__version__),**resources(start)))
    save(OUT/'resource_contract.json',dict(passed=True,formal_jobs=4,formal_base_fits=12,formal_partition_fits=4,convex_problems=8,max_solver_calls=16,
        CPUs_each=1,memory_MB_each=3000,CPU_total_s=7200,wall_each_s=3600,worker_timeout_s=3550,
        callback_CPU_each_s=1700,callback_wall_each_s=3500,retained_bytes_max=20000000,
        pilot_limits='512-row2-round cost and4096 synthetic QC not full-cost guarantee; generous original ceilings and worker hard stop remain',
        no_extra_scientific_fits_or_retry=True,**resources(start)))
    print((OUT/'pilot.json').read_text())


if __name__=='__main__':main()
