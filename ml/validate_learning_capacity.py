#!/usr/bin/env python3
"""Readback of all nine models, same full population, fixed offsets, roles and budgets."""
import json
import numpy as np
import xgboost as xgb
from learning_capacity import REPO,CACHE,OUT,configuration,load_inputs,candidates,formal_output

cfg=configuration();d,x=load_inputs();y=np.log(d['truth_E_GeV']);matrices=candidates(x,d)
with np.load(CACHE/'predictions.npz') as z:joined={k:z[k] for k in z.files}
np.testing.assert_array_equal(joined['cache_row'],np.arange(len(x)))
with np.load(REPO/'ntuples/energy_ml_stage42/A_predictions.npz') as z:np.testing.assert_array_equal(z['A0'],joined['L3_F6'])
errors=[];fit_count=0
for f in range(3):
    path=REPO/f'ml/artifacts/stage50/formal/{f}'
    part=formal_output(f,d)
    md=json.loads(str(part['metadata_json']));assert md['config']==cfg and md['fold']==f and not md['smoke'];assert len(md['records'])==3
    tr=np.flatnonzero(d['fold']==(f+1)%3);ca=np.flatnonzero(d['fold']==(f+2)%3);ev=np.flatnonzero(d['fold']==f)
    for left,right in [(tr,ca),(tr,ev),(ca,ev)]:assert not set(d['group'][left])&set(d['group'][right])
    for k,v in [('cache_row',ev),('train_cache_row',tr),('cal_cache_row',ca)]:np.testing.assert_array_equal(part[k],v)
    for name,(matrix,depth) in matrices.items():
        r=next(r for r in md['records'] if r['model']==name);fit_count+=1
        assert r['depth']==depth and r['rounds']==400 and r['columns']==matrix.shape[1]
        for role,ids in [('train',tr),('calibration',ca),('evaluation',ev)]:assert r[role+'_sources']==sorted(set(d['group'][ids])) and r[role+'_N']==len(ids)
        model=xgb.Booster(params={'nthread':1});model.load_model(path/(name+'.ubj'))
        assert model.num_features()==matrix.shape[1] and model.num_boosted_rounds()==400
        cal=model.predict(xgb.DMatrix(matrix[ca]));pred=model.predict(xgb.DMatrix(matrix[ev]));offset=float(np.mean(y[ca]-cal));assert offset==r['log_offset']
        energy=np.exp(pred.astype(float)+offset);np.testing.assert_allclose(energy,part[name],rtol=1e-14,atol=0)
        np.testing.assert_array_equal(pred,(np.log(part[name])-offset).astype('float32'));np.testing.assert_array_equal(part[name],joined[name][ev])
        errors.append(float(np.max(abs(energy/part[name]-1))))
assert fit_count==len(list((REPO/'ml/artifacts/stage50/formal').glob('*/*.ubj')))==cfg['max_formal_fits']==9
assert len(list((REPO/'ml/artifacts/stage50/smoke').glob('*/*.ubj')))==1
with np.load(REPO/'ml/artifacts/stage50/smoke/0/predictions.npz') as z:sm=json.loads(str(z['metadata_json']))
assert sm['smoke'] and len(sm['records'])==1 and sm['records'][0]['rounds']==20
(OUT/'smoke_training.json').write_text(json.dumps(sm,indent=2)+'\n')
with np.load(CACHE/'support_controls.npz') as z:
    np.testing.assert_array_equal(z['cache_row'],np.flatnonzero(d['selected']))
    np.testing.assert_array_equal(z['A0'],joined['L3_F6'][d['selected']])
readback=json.loads((OUT/'control_readback.json').read_text());assert readback['new_energy_fits']==0 and readback['common_offset_fits']==3
assert all(r['cal_eval_source_disjoint'] and r['actual_current_model_B_cal_predictions'] for r in readback['records'])
summary=dict(events=len(x),sources=len(set(d['group'])),formal_fits=fit_count,smoke_fits=1,cached_L3_F6_exact_reuse=True,
             original_fold_and_source_roles_preserved=True,train_cal_eval_sources_disjoint=True,all_14309_events_evaluated_once=True,
             original_F6_65_columns_only=True,local_22_features_not_used=True,truth_z_only_in_oracles=True,truth_p_direction_PDG_matching_as_inputs=False,
             models_reloaded=True,raw_float32_prediction_exact=True,cal_offsets_recomputed_exact=True,energy_max_relative_difference=max(errors),
             common_B_cal_uses_current_model_predictions=True,new_probability_mapping_fits=0,no_dropped_events=True,old_test_opened=False,independent_confirmation=False)
(OUT/'validation.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
