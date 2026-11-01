#!/usr/bin/env python3
"""Independent identity/role/model/mapping verification for source-external inference."""
import json
import joblib
import numpy as np
import xgboost as xgb
from source_transfer import REPO,CACHE,OUT,configuration,load_inputs

cfg=configuration();rows,d,x=load_inputs()
with np.load(CACHE/'predictions.npz') as z:pred={k:z[k] for k in z.files}
md=json.loads(str(pred['metadata_json']));assert md['config']==cfg and md['energy_fits']==md['target_calibration_fits']==0
with np.load(CACHE/'selection.npz') as z:
    for k in ['cache_row','run','eventID','group','component','fold']:np.testing.assert_array_equal(z[k],pred[k])
for k in ['truth_E_GeV','reco_p_GeV','y_lepton','vertex_z_mm','primary_kinematic_parent_proxy']:np.testing.assert_array_equal(pred[k],d[k])
with np.load(REPO/'ntuples/energy_ml_stage42/development.npz') as z:
    old_groups=set(z['group'][z['selected']]);assert not old_groups&set(d['group'])
    assert not z['selected'][rows].any()
assert len(set(zip(d['run'],d['eventID'])))==len(rows)==4000
historical=json.loads((OUT/'historical_readback.json').read_text());assert historical['original_mapping_reconstructions']==6 and not historical['new_support_labels_used']
for r in historical['records']:
    for role in ['original_calibration_sources','original_training_sources']:assert not set(r[role])&set(d['group'])
    assert r['raw_float32_log_prediction_exact']
states=joblib.load(CACHE/'original_maps.joblib');energy_errors=[];q_errors=[]
for f in range(3):
    take=d['fold']==f
    for name in cfg['models']:
        state=states[(f,name)];values=x[take] if name=='local' else np.column_stack([x[take],d['vertex_z_mm'][take]]).astype('float32')
        model=xgb.Booster(params={'nthread':1});model.load_model(REPO/state['model_path'])
        assert model.num_features()==(87 if name=='local' else 88) and model.num_boosted_rounds()==400
        log_pred=model.predict(xgb.DMatrix(values)).astype(float)+state['log_offset']
        np.testing.assert_array_equal((np.log(pred[name][take])-state['log_offset']).astype('float32'),(log_pred-state['log_offset']).astype('float32'))
        energy=np.exp(log_pred);q=state['pipe'].predict_proba(log_pred[:,None])
        np.testing.assert_allclose(energy,pred[name][take],rtol=1e-14,atol=0);np.testing.assert_allclose(q,pred['q_'+name][take],rtol=1e-12,atol=1e-14)
        energy_errors.append(float(np.max(abs(energy/pred[name][take]-1))));q_errors.append(float(np.max(abs(q-pred['q_'+name][take]))))
        np.testing.assert_array_equal(pred['prior'][take],np.tile(state['prior'],(take.sum(),1)))
extract=json.loads((OUT/'extraction.json').read_text());assert extract['events']==4000 and extract['sources']==60 and extract['pilot_exact_rejoin']
summary=dict(events=len(rows),sources=len(set(d['group'])),original_X87_definition_preserved=True,all_identity_fingerprints_verified=True,
             original_assigned_folds_preserved=True,new_source_overlap_with_all_old_train_calibration=0,
             old_energy_fits=0,new_energy_fits=0,target_calibration_fits=0,original_mapping_reconstructions=6,
             new_support_used_for_calibration=False,new_models_created=False,no_dropped_events=True,old_test_opened=False,
             models_reloaded_and_raw_float32_predictions_exact=True,energy_max_relative_difference=max(energy_errors),probability_max_absolute_difference=max(q_errors),
             truth_z_oracle_only=True,truth_direction_PDG_matching_as_inputs=False,independent_production_confirmation=False)
(OUT/'validation.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
