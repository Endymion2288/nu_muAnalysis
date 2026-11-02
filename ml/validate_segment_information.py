#!/usr/bin/env python3
"""Independent model readback, original source roles, pilot replay and control invariants."""
import json
import awkward as ak
import numpy as np
import xgboost as xgb
from segment_information import REPO,OUT,CACHE,configuration,summarize,formal_output
from run_segment_information import inputs
from local_activity import axes

cfg=configuration();d,matrices=inputs();y=np.log(d['truth_E_GeV'])
with np.load(CACHE/'predictions.npz') as z:joined={k:z[k] for k in z.files}
with np.load(CACHE/'features.npz') as z:features={k:z[k] for k in z.files}
np.testing.assert_array_equal(joined['cache_row'],np.arange(len(y)))
with np.load(REPO/'ntuples/energy_ml_stage50/predictions.npz') as z:np.testing.assert_array_equal(joined['F6'],z['L5_F6'])
errors=[];records=[]
for f in range(3):
    path=REPO/f'ml/artifacts/stage51/formal/{f}'
    p=formal_output(f,d)
    md=json.loads(str(p['metadata_json']));assert md['config']==cfg and not md['smoke'] and md['fold']==f and len(md['records'])==3
    tr=np.flatnonzero(d['fold']==(f+1)%3);ca=np.flatnonzero(d['fold']==(f+2)%3);ev=np.flatnonzero(d['fold']==f)
    for k,v in [('train_cache_row',tr),('cal_cache_row',ca),('cache_row',ev)]:np.testing.assert_array_equal(p[k],v)
    for a,b in [(tr,ca),(tr,ev),(ca,ev)]:assert not set(d['group'][a])&set(d['group'][b])
    for name,matrix in matrices.items():
        r=next(r for r in md['records'] if r['model']==name);records.append(r)
        for role,ids in [('train',tr),('calibration',ca),('evaluation',ev)]:assert r[role+'_sources']==sorted(set(d['group'][ids])) and r[role+'_N']==len(ids)
        model=xgb.Booster(params={'nthread':1});model.load_model(path/(name+'.ubj'));assert model.num_features()==matrix.shape[1] and model.num_boosted_rounds()==400
        pred=model.predict(xgb.DMatrix(matrix[ev]));cal=model.predict(xgb.DMatrix(matrix[ca]));offset=float(np.mean(y[ca]-cal));assert offset==r['log_offset']
        np.testing.assert_array_equal(pred,(np.log(p[name])-offset).astype('float32'));np.testing.assert_allclose(np.exp(pred.astype(float)+offset),p[name],rtol=1e-14,atol=0)
        np.testing.assert_array_equal(p[name],joined[name][ev]);errors.append(float(np.max(abs(np.exp(pred.astype(float)+offset)/p[name]-1))))
assert len(records)==9==len(list((REPO/'ml/artifacts/stage51/formal').glob('*/*.ubj')))
assert len(list((REPO/'ml/artifacts/stage51/smoke').glob('*/*.ubj')))==1
with np.load(REPO/'ml/artifacts/stage51/smoke/0/predictions.npz') as z:sm=json.loads(str(z['metadata_json']))
assert sm['smoke'] and len(sm['records'])==1 and sm['records'][0]['rounds']==20
(OUT/'smoke_training.json').write_text(json.dumps(sm,indent=2)+'\n')
np.testing.assert_array_equal(np.isnan(features['convergence']),np.isnan(features['shuffle']))
np.testing.assert_array_equal(features['convergence'][:,2::6],features['shuffle'][:,2::6])
np.testing.assert_array_equal(matrices['convergence'][:,:111],matrices['shuffle'][:,:111])
pilot_path=CACHE/'pilot.json' if (CACHE/'pilot.json').exists() else OUT/'pilot.json'
pilot=json.loads(pilot_path.read_text());events=pilot['event_records'];axis,_,_,_=axes(ak.Array([e['tracks'] for e in events]),json.loads((REPO/'ml/configs/local_activity.json').read_text()))
for j,e in enumerate(events):
    a=np.array(e['collections'][cfg['collection']]['raw']).reshape(-1,8);theta,c,n,counts,diag=summarize(a,axis[j],e['run'],e['eventID'],e['index'],cfg);row=e['cache_row']
    for key,value in [('angles',theta),('convergence',c),('shuffle',n),('valid_unique_counts',counts)]:np.testing.assert_array_equal(value,features[key][row])
ex=json.loads((OUT/'extraction.json').read_text());assert ex['events']==14309 and ex['sources']==81 and ex['identity_failures']==0 and ex['all_events_seen_once']
md=dict(events=14309,sources=81,formal_fits=9,smoke_fits=1,baseline_fits=0,baseline_exact_reuse=True,original_source_roles_disjoint=True,
    models_reloaded=True,cal_offsets_exact=True,raw_float32_predictions_exact=True,energy_max_relative_difference=max(errors),
    full_feature_pilot_replay_exact_events=len(events),same_control_angular_features=True,same_control_missing=True,same_control_center_dispersion=True,control_changed_event_N=int((np.isfinite(features['convergence'])&(features['convergence']!=features['shuffle'])).any(axis=1).sum()),
    no_dropped_events=True,truth_inputs=[],new_probability_mapping_fits=0,old_test_opened=False,independent_confirmation=False)
(OUT/'validation.json').write_text(json.dumps(md,indent=2)+'\n');print(json.dumps(md))
