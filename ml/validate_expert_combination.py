#!/usr/bin/env python3
"""Independent reconstruction/constraint and OOF lineage QA; never refits."""
import csv
import json
import numpy as np
from audited_features import load

from expert_combination import (OUT, ART, CELLS, LOW, COST, begin, resources, inputs,
                                subset, route, masks, predict, experts, quadratic, value, gradient, save)

start=begin();p=json.loads((OUT/'protocol.json').read_text());models=json.loads((OUT/'models.json').read_text())
d=inputs();bounds=p['timing_medians_pC']
with np.load(ART/'predictions.npz') as z:arr={k:z[k] for k in z.files}
roles={r:subset(d,d['role']==r) for r in ['train','cal','eval']}
assert not set(roles['cal']['group']) & set(roles['eval']['group'])
assert not set(roles['cal']['group']) & set(roles['train']['group'])
for j,(lo,hi) in enumerate([(50,100),(100,250)]):
    tr=roles['train'];m=(tr['pz']>=lo)&(tr['pz']<hi)&np.isfinite(tr['timing'])
    assert float(np.median(tr['timing'][m]))==bounds[j]
for role in ['cal','eval']:np.testing.assert_array_equal(arr[role+'_row'],roles[role]['row'])
cal=roles['cal'];fold=np.array([p['fold_by_group'][str(g)] for g in cal['group']])
np.testing.assert_array_equal(fold,arr['cal_fold']);records=[]
for family in ['two','three']:
    assert len(models[family]['folds'])==3
    for f,model in enumerate(models[family]['folds']+[models[family]['final']]):
        train=np.ones(len(fold),bool) if f==3 else fold!=f
        off=float(np.mean(np.log(cal['truth_E_GeV'][train])-cal['raw_F7'][train]))
        assert off==model['offset_log']
        w=np.array(model['weights']);assert w.shape==(4,3) and w.min()>=0
        np.testing.assert_allclose(w.sum(axis=1),1,rtol=0,atol=1e-14)
        if family=='two':assert (w[:,0]==0).all()
        if f<3:
            assert not set(cal['group'][train]) & set(cal['group'][~train])
            assert sorted(set(cal['group'][train]))==model['train_groups']
            hold=subset(cal,~train)
            actual=predict(hold['pz'],hold['timing'],hold['raw_F7'],model,bounds)
            np.testing.assert_array_equal(actual,arr['cal_oof_'+family][~train])
            np.testing.assert_array_equal(hold['raw_F7']+off,arr['cal_oof_F7'][~train])
        else:
            for role in ['cal','eval']:
                dd=roles[role];pred=predict(dd['pz'],dd['timing'],dd['raw_F7'],model,bounds)
                np.testing.assert_array_equal(pred,arr[('cal_final_' if role=='cal' else 'eval_')+family])
                cell=route(dd['pz'],dd['timing'],bounds)
                np.testing.assert_array_equal(pred[cell<0],(dd['raw_F7']+off)[cell<0])
        dd=subset(cal,train);logy=np.log(dd['truth_E_GeV']);base=dd['raw_F7']+off
        actual=predict(dd['pz'],dd['timing'],dd['raw_F7'],model,bounds)
        mm=masks(dd)
        for key in LOW+list(COST):
            m=mm[key];reference=np.log(dd['pz']/.8) if key in LOW else base
            ratio=float(np.mean((actual[m]-logy[m])**2)/np.mean((reference[m]-logy[m])**2))
            np.testing.assert_allclose(ratio,model['risk_ratios'][key],rtol=0,atol=1e-12)
            if key in COST:assert ratio <= COST[key]**2+1e-8
        assert model['maximum_constraint_violation']<1e-8
        assert model['projected_KKT_max_abs']<1e-6 and model['complementarity_max_abs']<1e-8
        records.append(dict(family=family,fold='final' if f==3 else f,offset_exact=True,predictions_exact=True,empirical_risks_exact=True))
# Independent dense-form quadratic gradient / sufficient statistics check.
a=np.array([[1.,2.],[-2.,3.],[0.,-1.]]);e=np.array([.1,-.3,.5]);v=np.array([.2,.4])
q=quadratic(a,e,np.ones(3,bool),.8)
np.testing.assert_allclose(value(q,v),np.mean((e+a@v)**2)/.8,rtol=0,atol=1e-14)
g=np.array([(value(q,v+np.eye(2)[j]*1e-5)-value(q,v-np.eye(2)[j]*1e-5))/2e-5 for j in range(2)])
np.testing.assert_allclose(g,gradient(q,v),rtol=0,atol=1e-10)
# The pre-existing F7 evaluation is preserved, including the original offset.
old=list(csv.DictReader((OUT.parent/'stage56_energy_ml/metrics.tsv').open(),delimiter='\t'))
new=list(csv.DictReader((OUT/'metrics.tsv').open(),delimiter='\t'))
for key in ['all','E50_100','E100_200','pz50_100','pz100_250','high_y','unconfirmed']:
    before=next(r for r in old if r['stratum']==key and r['model']=='audited_raw')
    after=next(r for r in new if r['sample']=='evaluation' and r['stratum']==key and r['model']=='F7')
    assert before['N']==after['N']
    np.testing.assert_allclose(float(before['log_RMSE']),float(after['log_RMSE']),rtol=0,atol=1e-14)
checks=dict(**resources(start),combination_problems_checked=8,additional_optimizer_calls=0,
            thresholds_train_only_exact=True,source_groups_disjoint=True,fold_offsets_and_predictions_exact=True,
            empirical_constraints_checked=True,quadratic_gradient_checked=True,F7_stage56_metrics_exact=True,
            missing_events_by_role={r:int(roles[r]['missing'].sum()) for r in roles},
            per_model=records)
# Existing protection exclusions precede this stage; distinguish them from
# dropping an event because one of its detector inputs is missing.
_, supplement, full_matrix=load()
full_missing=int(np.isnan(full_matrix).any(axis=1).sum())
assert full_missing==42
checks['full_nominal_missing_events']=full_missing
checks['missing_outside_preexisting_eligible_roles']=full_missing-sum(checks['missing_events_by_role'].values())
checks.update(resources(start))
save(OUT/'validation.json',checks);print(json.dumps(checks,indent=2))
