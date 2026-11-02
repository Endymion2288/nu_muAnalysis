#!/usr/bin/env python3
"""Four predetermined source-cross-fitted gate fits; no F7 retraining."""
from datetime import datetime,timezone
import json
import resource
import numpy as np

from expert_combination import inputs,subset,begin,resources,save
from lightweight_gate import OUT,ART,fit,predict

start=begin();p=json.loads((OUT/'protocol.json').read_text())
assert not (OUT/'models.json').exists() and not (ART/'predictions.npz').exists(), 'Never repeat completed/started fits'
d=inputs();cal=subset(d,d['role']=='cal')
fold=np.array([p['fold_by_group'][str(g)] for g in cal['group']])
models=dict(protocol_version='stage59_4x8_softmax_rho_v1',fit_calls=0,folds=[],final=None,journal=[])
save(OUT/'models.json',models)
oof=np.full(len(fold),np.nan);oof_f7=np.full(len(fold),np.nan)
for f in range(4):
    train=np.ones(len(fold),bool) if f==3 else fold!=f
    dd=subset(cal,train)
    if f<3:assert not set(cal['group'][train]) & set(cal['group'][~train])
    models['fit_calls']+=1;models['journal'].append(dict(fold=f if f<3 else 'final',status='started'))
    save(OUT/'models.json',models)
    model=fit(dd,p);model['held_fold']=f if f<3 else 'final'
    if f<3:
        models['folds'].append(model);hold=subset(cal,~train)
        oof[~train]=predict(hold,model,p);oof_f7[~train]=hold['raw_F7']+model['offset_log']
    else:models['final']=model
    models['journal'][-1]['status']='completed';save(OUT/'models.json',models)
    print('fold',f,'converged',model['success'],'iterations',model['iterations'],'low MSE ratio',model['max_low_MSE_ratio'],
          'wall',model['wall_s'],'selection',model['selection'],flush=True)
assert models['fit_calls']==p['gate_fit_calls']==4
assert np.isfinite(oof).all()
models['frozen_before_eval_utc']=datetime.now(timezone.utc).isoformat();save(OUT/'models.json',models)
# Evaluation starts after the final parameters have been persisted and frozen.
ev=subset(d,d['role']=='eval');final=models['final']
arrays=dict(cal_row=cal['row'],eval_row=ev['row'],cal_fold=fold,
            cal_oof_gate=oof,cal_oof_F7=oof_f7,cal_final_gate=predict(cal,final,p),
            eval_gate=predict(ev,final,p),eval_F7=ev['raw_F7']+final['offset_log'])
ART.mkdir(parents=True,exist_ok=True);np.savez_compressed(ART/'predictions.npz',**arrays)
result=dict(**resources(start),gate_fit_calls=models['fit_calls'],new_energy_model_fits=0,
            optimizer_wall_sum_s=sum(m['wall_s'] for m in models['folds']+[final]),
            optimizer_cpu_sum_s=sum(m['cpu_s'] for m in models['folds']+[final]),
            converged_fits=sum(m['success'] for m in models['folds']+[final]),
            retained_prediction_bytes=(ART/'predictions.npz').stat().st_size)
assert result['cpu_s']<=p['cpu_budget_s']
assert result['peak_rss_MiB']<=p['rss_budget_MiB']
assert result['retained_prediction_bytes']<=p['retained_prediction_budget_bytes']
save(OUT/'fit_resources.json',result)
print(json.dumps(result,indent=2),flush=True)
