#!/usr/bin/env python3
"""Immutable stage60 protocol and analytic-profile pilot; zero model fits."""
from datetime import datetime,timezone
import json
import numpy as np

from expert_combination import inputs,subset,begin,resources,save,COST
from lightweight_gate import features,initial_parameters,predict,Risks
from profiled_gate import OUT,profile,feasible_cap,polynomial_roots,ProfiledRisk

start=begin();OUT.mkdir(exist_ok=True)
assert not (OUT/'protocol.json').exists(),'Do not rewrite the frozen protocol'
p=json.loads((OUT.parent/'stage59_energy_ml/protocol.json').read_text())
p.update(stage=60,starting_commit='5ab5c95',frozen_utc=datetime.now(timezone.utc).isoformat(),
         parameter_count=58,profiled_parameter='rho (same gate family, solved analytically per network evaluation)',
         initial_point='same seed/58 network coordinates as stage59; analytic feasible rho profile including rho=0',
         optimizer='L-BFGS-B, bounded two-point finite differences, single start, no retry',
         optimizer_maxiter=500,optimizer_maxfun=50000,optimizer_ftol=1e-10,optimizer_gtol=1e-5,
         finite_difference_rel_step=1e-6,stationarity_probe_steps=[1e-4,1e-5],
         inner_feasibility_tolerance=1e-10,inner_numerical_rule='stable quadratic roots, nextafter cap toward zero, polynomial coefficient cutoff 1e-14 after scaling',
         profile='global 1D minimum of max(two low-E quadratic risks)+1e-6 all-event risk on analytic feasible [0,rho_max]',
         failure_policy='report terminal status/parameters/gradient/all slacks; failed optimizer uses best feasible profiled training callback including initial profile; never retry',
         nonsmooth_note='finite differences follow the actual profiled objective; branch switches may be nonsmooth; report solver termination, projected gradient and coordinate probes separately')
# Exact known cases; grid comparisons validate only the analytic 1D arithmetic.
limits=np.array([v*v for v in COST.values()]);constant=np.tile([0.,0.,1.],(5,1))
known=[]
q=np.vstack([[1.,-.4,1.04],[1.,-1.6,1.64],constant])
a=profile(q,1e-6);np.testing.assert_allclose(a['rho'],.5,atol=1e-14);known.append('interior_intersection')
q0=q.copy();q0[:2]=[[1.,-.6,2.09],[0,0,1]]
np.testing.assert_allclose(profile(q0,1e-6)['rho'],.3,atol=1e-14);known.append('single_active_vertex')
qc=q.copy();qc[2]=[1,0,1];cap,_=feasible_cap(qc[2:],limits)
np.testing.assert_allclose(cap,np.sqrt(1.01**2-1),atol=1e-14)
np.testing.assert_allclose(profile(qc,1e-6)['rho'],cap,atol=1e-14);known.append('cost_boundary')
ql=q.copy();ql[2]=[0,.1,1];cap,_=feasible_cap(ql[2:],limits)
np.testing.assert_allclose(cap,(1.01**2-1)/.1,atol=1e-14);known.append('linear_cost')
flat=np.vstack([[0,0,2],[0,0,1],constant]);assert profile(flat,1e-6)['rho']==0;known.append('zero_response')
np.testing.assert_allclose(sorted(polynomial_roots(1,-2,1)),[1,1],atol=1e-14);known.append('tangent_root')
rng=np.random.default_rng(2026110260);grid_gaps=[]
for _ in range(100):
    A=rng.uniform(.01,2,7);B=rng.uniform(-.5,.5,7);C=np.r_[rng.uniform(.7,3,2),np.ones(5)]
    coeff=np.c_[A,B,C];got=profile(coeff,1e-6);grid=np.linspace(0,got['rho_max'],10001)
    values=coeff@np.array([grid**2,grid,np.ones(len(grid))]);obj=values[:2].max(axis=0)+1e-6*values[2]
    gap=float(obj.min()-got['objective']);assert gap>=-1e-12;grid_gaps.append(gap)
# Preserve the original train-only transformation and source mapping exactly.
d=inputs();tr=subset(d,d['role']=='train');f,active=features(tr)
np.testing.assert_array_equal(np.median(f[active],axis=0),p['center'])
np.testing.assert_array_equal(np.quantile(f[active],.75,axis=0)-np.quantile(f[active],.25,axis=0),p['scale'])
cal=subset(d,d['role']=='cal');idx=np.r_[np.flatnonzero(cal['truth_E_GeV']<100)[:16],
    np.flatnonzero((cal['truth_E_GeV']>=100)&(cal['truth_E_GeV']<200))[:16],np.flatnonzero(cal['y_lepton']>=.8)[:16]]
small=subset(cal,idx);off=float(np.mean(np.log(small['truth_E_GeV'])-small['raw_F7']))
risk=ProfiledRisk(small,p,off);theta=initial_parameters(p['seed'])[:-1];result=risk.evaluate(theta).copy();coeff=risk.coefficients.copy()
model=dict(parameters=np.r_[theta,result['rho']].tolist(),offset_log=off)
y=np.log(small['truth_E_GeV']);pred=predict(small,model,p)
from expert_combination import masks,LOW
mm=masks(small)
for key,ratio in result['risk_ratios'].items():
    ref=np.log(small['pz']/.8) if key in LOW else small['raw_F7']+off
    empirical=np.mean((pred[mm[key]]-y[mm[key]])**2)/np.mean((ref[mm[key]]-y[mm[key]])**2)
    np.testing.assert_allclose(empirical,ratio,rtol=0,atol=1e-12)
# Step refinement checks the derivative of the actual profiled objective.
gradients=[]
for step in [1e-5,5e-6]:
    g=[]
    for j in range(58):
        plus=theta.copy();minus=theta.copy();plus[j]+=step;minus[j]-=step
        g.append((risk.evaluate(plus)['objective']-risk.evaluate(minus)['objective'])/(2*step))
    gradients.append(np.array(g))
np.testing.assert_allclose(*gradients,rtol=1e-3,atol=1e-6)
# Reuse stage59's deployment function; exercise signed and missing defaults.
injected={k:v.copy() for k,v in small.items()};injected['timing'][0]=np.nan;injected['calo'][1]=np.nan;injected['pz'][2]=250
np.testing.assert_array_equal(predict(injected,model,p)[:3],(injected['raw_F7']+off)[:3])
neg={k:v[:1].copy() for k,v in small.items()};neg['pz'][0]=60;neg['timing'][0]=-1;neg['calo'][0]=-1;assert features(neg)[1][0]
save(OUT/'protocol.json',p)
save(OUT/'pilot.json',dict(**resources(start),optimizer_calls=0,small_cal_N=len(idx),synthetic_known_cases=known,
                         random_quadratic_cases=100,max_dense_grid_gap=max(grid_gaps),
                         profiled_derivative_refinement_max_abs=float(np.max(abs(gradients[0]-gradients[1]))),
                         train_transforms_exact=True,empirical_constraints_checked=True,signed_and_missing_checks=True))
print(json.dumps(p,indent=2))
