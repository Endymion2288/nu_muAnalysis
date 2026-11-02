#!/usr/bin/env python3
"""Independent inference and analytic profile/constraint/OOF QA; no refits."""
import csv
import json
import numpy as np

from audited_features import load
from expert_combination import inputs,subset,begin,resources,save,masks,LOW,COST
from profiled_gate import OUT,ART,ProfiledRisk
from lightweight_gate import features,standardized,predict,Risks,initial_parameters


def independent_predict(d,model,p):
    """Reconstruct weights directly from the saved parameter layout."""
    x,active=standardized(d,p);v=np.array(model['parameters']);base=d['raw_F7']+model['offset_log']
    h=np.tanh(np.einsum('ni,ij->nj',x[active],v[:32].reshape(4,8))+v[32:40])
    logits=np.c_[h@v[40:56].reshape(8,2)+v[56:58],np.zeros(active.sum())]
    logits-=logits.max(axis=1)[:,None];prob=np.exp(logits);prob/=prob.sum(axis=1)[:,None]
    w=prob*v[58];w[:,2]+=1-v[58]
    t=np.c_[np.log(d['pz'][active]),np.log(d['pz'][active]/.8),base[active]]
    result=base.copy();result[active]=np.sum(w*t,axis=1)
    return result


start=begin();p=json.loads((OUT/'protocol.json').read_text());models=json.loads((OUT/'models.json').read_text())
assert models['fit_calls']==p['gate_fit_calls']==4
assert len(models['folds'])==3 and all(j['status']=='completed' for j in models['journal'])
d=inputs();roles={role:subset(d,d['role']==role) for role in ['train','cal','eval']}
tr=roles['train'];f,act=features(tr)
np.testing.assert_array_equal(np.median(f[act],axis=0),p['center'])
np.testing.assert_array_equal(np.quantile(f[act],.75,axis=0)-np.quantile(f[act],.25,axis=0),p['scale'])
with np.load(ART/'predictions.npz') as z:a={k:z[k] for k in z.files}
with np.load(OUT.parents[1]/'ml/artifacts/stage58/predictions.npz') as z:old={k:z[k] for k in z.files}
for role in ['cal','eval']:np.testing.assert_array_equal(roles[role]['row'],a[role+'_row'])
cal=roles['cal'];fold=np.array([p['fold_by_group'][str(g)] for g in cal['group']])
np.testing.assert_array_equal(fold,a['cal_fold']);np.testing.assert_array_equal(fold,old['cal_fold'])
for r1,r2 in [('train','cal'),('train','eval'),('cal','eval')]:assert not set(roles[r1]['group']) & set(roles[r2]['group'])
records=[];profile_records=[]
for i,m in enumerate(models['folds']+[models['final']]):
    train=np.ones(len(cal['pz']),bool) if i==3 else fold!=i;fitdata=subset(cal,train)
    assert sorted(set(fitdata['group']))==m['train_groups']
    off=float(np.mean(np.log(fitdata['truth_E_GeV'])-fitdata['raw_F7']))
    assert off==m['offset_log']
    params=np.array(m['parameters']);assert len(params)==59 and (abs(params[:58])<=8+1e-12).all() and 0<=params[58]<=1
    if i<3:
        hold=subset(cal,~train);expected=a['cal_oof_gate'][~train]
        assert not set(fitdata['group']) & set(hold['group'])
        np.testing.assert_array_equal(predict(hold,m,p),expected)
        np.testing.assert_allclose(independent_predict(hold,m,p),expected,rtol=0,atol=1e-13)
        np.testing.assert_array_equal(hold['raw_F7']+off,a['cal_oof_F7'][~train])
    else:
        for role in ['cal','eval']:
            dd=roles[role];expected=a['cal_final_gate' if role=='cal' else 'eval_gate']
            pred,w=predict(dd,m,p,True)
            np.testing.assert_array_equal(pred,expected)
            np.testing.assert_allclose(independent_predict(dd,m,p),expected,rtol=0,atol=1e-13)
            np.testing.assert_allclose(w.sum(axis=1),1,rtol=0,atol=1e-14);assert w.min()>=0
            _,active=features(dd);np.testing.assert_array_equal(pred[~active],(dd['raw_F7']+off)[~active])
            reverse=np.arange(len(pred))[::-1]
            np.testing.assert_array_equal(predict(subset(dd,reverse),m,p),pred[reverse])
    pred=predict(fitdata,m,p);mm=masks(fitdata);y=np.log(fitdata['truth_E_GeV']);base=fitdata['raw_F7']+off
    risk=Risks(fitdata,p,off);ratios,_=risk.evaluate(params)
    for j,key in enumerate(LOW+list(COST)):
        use=mm[key];ref=np.log(fitdata['pz']/.8) if key in LOW else base
        ratio=np.mean((pred[use]-y[use])**2)/np.mean((ref[use]-y[use])**2)
        np.testing.assert_allclose(ratio,m['risk_ratios'][key],rtol=0,atol=1e-11)
        np.testing.assert_allclose(ratio,ratios[j],rtol=0,atol=1e-11)
        if key in COST:assert ratio<=COST[key]**2+p['feasibility_tolerance']
    # Recompute the analytic profile from the selected and terminal networks.
    pr=ProfiledRisk(fitdata,p,off)
    for label,parameters,expected_profile in [('selected',m['parameters'],m['selected_profile']),
                                               ('terminal',m['terminal_parameters'],m['terminal_profile'])]:
        v=np.asarray(parameters);got=pr.evaluate(v[:-1]);coeff=pr.coefficients.copy()
        np.testing.assert_equal(got['rho'],v[-1])
        np.testing.assert_equal(got['rho_max'],expected_profile['rho_max'])
        assert 0<=v[-1]<=got['rho_max']<=1
        assert got['maximum_constraint_violation']<p['inner_feasibility_tolerance']
        td=predict(fitdata,dict(parameters=parameters,offset_log=off),p)
        for key in LOW+list(COST):
            use=mm[key];ref=np.log(fitdata['pz']/.8) if key in LOW else base
            empirical=np.mean((td[use]-y[use])**2)/np.mean((ref[use]-y[use])**2)
            np.testing.assert_allclose(empirical,expected_profile['risk_ratios'][key],rtol=0,atol=1e-11)
        grid=np.linspace(0,got['rho_max'],10001)
        risk_grid=coeff@np.array([grid*grid,grid,np.ones(len(grid))])
        objective_grid=risk_grid[:2].max(axis=0)+p['numerical_secondary_epsilon']*risk_grid[2]
        assert got['objective']<=objective_grid.min()+1e-11
        # Every point up to the analytic cap obeys the training costs.
        assert np.max(risk_grid[2:]-np.array([v*v for v in COST.values()])[:,None])<1e-10
        profile_records.append(dict(fold=i if i<3 else 'final',state=label,rho_profile_exact=True,
            empirical_constraints_exact=True,maximum_violation=got['maximum_constraint_violation'],
            profile_objective_below_dense_grid=True))
    initial=initial_parameters(p['seed'])[:-1]
    np.testing.assert_allclose(pr.evaluate(initial)['objective'],m['initial_profile']['objective'],rtol=0,atol=1e-14)
    assert m['terminal_optimizer_gradient'] is None or len(m['terminal_optimizer_gradient'])==58
    assert m['terminal_coordinate_objective_decreases'] is not None
    records.append(dict(fold=i if i<3 else 'final',prediction_and_offset_exact=True,independent_prediction_checked=True,
                        empirical_risks_checked=True,optimizer_converged=m['success']))
# Check full-cal analytic risk derivatives at the saved candidate, holding rho fixed.
r=Risks(cal,p,models['final']['offset_log']);v=np.array(models['final']['parameters']);_,jac=r.evaluate(v)
step=1e-5;columns=[]
for j in range(len(v)):
    plus=v.copy();minus=v.copy();plus[j]+=step;minus[j]-=step
    columns.append((r.evaluate(plus)[0]-r.evaluate(minus)[0])/(2*step))
error=float(np.max(abs(np.array(columns).T-jac)))
np.testing.assert_allclose(np.array(columns).T,jac,rtol=1e-4,atol=1e-7)
np.testing.assert_array_equal(a['eval_F7'],old['eval_F7']);np.testing.assert_array_equal(a['cal_oof_F7'],old['cal_oof_F7'])
_,_,full=load();full_missing=int(np.isnan(full).any(axis=1).sum());assert full_missing==42
new=list(csv.DictReader((OUT/'metrics.tsv').open(),delimiter='\t'))
oldmetrics=list(csv.DictReader((OUT.parent/'stage58_energy_ml/metrics.tsv').open(),delimiter='\t'))
for role in ['cal_OOF','evaluation']:
    for key in ['all']+LOW+list(COST)[1:]:
        for before,after in [('F7','F7'),('three','four_cell'),('pz0_over0p8','pz0_over0p8')]:
            b=next(r for r in oldmetrics if r['sample']==role and r['stratum']==key and r['model']==before)
            n=next(r for r in new if r['sample']==role and r['stratum']==key and r['model']==after)
            assert b['N']==n['N'];np.testing.assert_allclose(float(b['log_RMSE']),float(n['log_RMSE']),rtol=0,atol=1e-14)
assert not json.loads((OUT/'acceptance.json').read_text())['promotion_allowed']
result=dict(**resources(start),gate_fits_checked=4,additional_fits=0,train_transforms_exact=True,
            grouped_OOF_offsets_exact=True,fold_partition_preserved=True,default_F7_exact=True,
            independent_inference_checked=True,full_cal_gradient_max_error=error,
            original_F7_and_four_cell_metrics_exact=True,full_missing_events=full_missing,
            missing_by_role={r:int(roles[r]['missing'].sum()) for r in roles},per_fit=records,
            numerical_QA_passed=True,optimizer_converged_fits=sum(m['success'] for m in models['folds']+[models['final']]),
            analytic_profile_checks=profile_records,promotion_allowed=False)
save(OUT/'validation.json',result);print(json.dumps(result,indent=2))
