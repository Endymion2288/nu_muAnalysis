#!/usr/bin/env python3
"""Train-only transforms, immutable gate protocol, and no-fit numerical pilot."""
from datetime import datetime,timezone
import json
import numpy as np

from expert_combination import inputs,subset,begin,resources,save,REPO,COST
from lightweight_gate import (OUT,INPUTS,NPARAM,features,standardized,initial_parameters,
                              forward,predict,Risks)
from report_expert_combination import table,support

start=begin();OUT.mkdir(exist_ok=True)
assert not (OUT/'protocol.json').exists(), 'Protocol is immutable after preparation'
d=inputs();tr=subset(d,d['role']=='train');f,active=features(tr)
center=np.median(f[active],axis=0);scale=np.quantile(f[active],.75,axis=0)-np.quantile(f[active],.25,axis=0)
assert np.all(scale>0)
old=json.loads((OUT.parent/'stage58_energy_ml/protocol.json').read_text())
p=dict(stage=59,frozen_utc=datetime.now(timezone.utc).isoformat(),starting_commit='7bc479e',
       input_contract='F7_pz0_raw_v1',inputs=INPUTS,transforms=['log(pz/GeV)','asinh(Timing_raw_total/pC)','log1p(total_clusters)','asinh(calo_EM_total/GeV)'],
       center=center.tolist(),scale=scale.tolist(),standardization='train eligible complete pz in [50,250), median/IQR; no clipping',
       architecture='4 -> tanh(8) -> 2 relative logits + fixed F7 logit 0 -> 3-softmax; scalar rho blends with exact F7',
       parameter_count=NPARAM,seed=2026110259,parameter_bounds=[-8,8],rho_bounds=[0,1],
       routing='any missing/invalid gate input or pz outside [50,250) uses F7 exactly; no event deletion',
       initial_point='rho=0 (exact F7), hidden N(0,.5), output N(0,.1/sqrt(8)), relative biases -1, same fixed seed per fold',
       objective='min maximum low-E MSE relative to traditional, plus fixed numerical secondary all/F7 MSE term',
       numerical_secondary_epsilon=1e-6,RMSE_cost_limits=COST,fold_by_group=old['fold_by_group'],
       gate_fit_calls=4,new_energy_model_fits=0,optimizer='SLSQP, analytic gradients, one start, no retry',
       optimizer_ftol=1e-10,optimizer_maxiter=500,feasibility_tolerance=1e-8,
       per_fit_wall_budget_s=90,total_fit_wall_budget_s=360,cpu_budget_s=400,rss_budget_MiB=1200,
       retained_prediction_budget_bytes=2000000,
       failure_policy='report failure/nonconvergence; select best training-feasible iterate including exact F7; do not retune or promote failed optimizer',
       nonconvex=True,global_optimality_claimed=False,
       bootstrap_replicates=500,bootstrap_seed=2026110259,recovery_upper95_limit=1.05,maximum_key_tail50_increase_pp=2,
       no_new_ROOT_RDO_or_production=True,no_locked_test_evaluation=True)
# Numerical pilot uses 48 cal rows with two supported low-E groups; no optimizer.
cal=subset(d,d['role']=='cal');idx=np.r_[np.flatnonzero(cal['truth_E_GeV']<100)[:16],
    np.flatnonzero((cal['truth_E_GeV']>=100)&(cal['truth_E_GeV']<200))[:16],
    np.flatnonzero(cal['y_lepton']>=.8)[:16]]
small=subset(cal,idx);off=float(np.mean(np.log(small['truth_E_GeV'])-small['raw_F7']))
theta=initial_parameters(p['seed']);theta[-1]=.35
x,act=standardized(small,p);base=small['raw_F7']+off
q=np.column_stack([np.log(small['pz'][act])-base[act],np.log(small['pz'][act]/.8)-base[act]])
cor,w,jac=forward(x[act],theta,q,True)
step=1e-6;numeric=[]
for j in range(NPARAM):
    plus=theta.copy();minus=theta.copy();plus[j]+=step;minus[j]-=step
    numeric.append((forward(x[act],plus,q)[0]-forward(x[act],minus,q)[0])/(2*step))
np.testing.assert_allclose(np.array(numeric).T,jac,rtol=1e-5,atol=1e-8)
r=Risks(small,p,off);rv,rj=r.evaluate(theta);numeric=[]
for j in range(NPARAM):
    plus=theta.copy();minus=theta.copy();plus[j]+=step;minus[j]-=step
    numeric.append((r.evaluate(plus)[0]-r.evaluate(minus)[0])/(2*step))
np.testing.assert_allclose(np.array(numeric).T,rj,rtol=1e-4,atol=1e-7)
np.testing.assert_allclose(w.sum(axis=1),1,atol=1e-14)
ref=initial_parameters(p['seed']);model=dict(parameters=ref.tolist(),offset_log=off)
np.testing.assert_array_equal(predict(small,model,p),small['raw_F7']+off)
injected={k:v.copy() for k,v in small.items()};injected['timing'][0]=np.nan;injected['calo'][1]=np.nan;injected['pz'][2]=250
model['parameters']=theta.tolist();out=predict(injected,model,p)
np.testing.assert_array_equal(out[:3],(injected['raw_F7']+off)[:3])
neg={k:v[:1].copy() for k,v in small.items()};neg['pz'][0]=60;neg['timing'][0]=-1;neg['calo'][0]=-1
assert features(neg)[1][0]
save(OUT/'protocol.json',p)
records=[]
for role in ['train','cal','eval']:
    dd=subset(d,d['role']==role);_,a=features(dd)
    for name,m in [('all',np.ones(len(a),bool)),('gate_active',a),('default_F7',~a),('input_missing',dd['missing'])]:
        records.append(dict(role=role,stratum=name,**support(dd,m)))
table(OUT/'routing_support.tsv',records)
save(OUT/'pilot.json',dict(**resources(start),pilot_N=len(idx),optimizer_calls=0,train_transform_N=int(active.sum()),
    risk_jacobian_max_error=float(np.max(abs(np.array(numeric).T-rj))),risk_jacobian_checked=True,
    exact_F7_reference=True,default_and_signed_checks=True,parameter_count=NPARAM))
print(json.dumps(p,indent=2))
