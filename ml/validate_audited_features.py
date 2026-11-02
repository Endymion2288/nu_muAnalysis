#!/usr/bin/env python3
"""Typed sentinel/dependency checks and persisted-model inference verification."""
import json
import resource
import time

import numpy as np
import xgboost as xgb

from audited_features import REPO, SCINTILLATORS, build, clean, configuration, load

tick,cpu=time.perf_counter(),time.process_time();cfg=configuration()
cases=[('nonnegative',[-999,-1,0,2],[np.nan,np.nan,0,2]),
       ('positive',[-.999,-.001,0,999999],[np.nan,np.nan,np.nan,999999]),
       ('count',[-1,0,3,4294967295,4294967296],[np.nan,0,3,np.nan,np.nan]),
       ('charge_sign',[-999,-1,0,1],[np.nan,-1,np.nan,1]),
       ('signed',[-999,-1,-.001,0],[-999,-1,-.001,0])]
for domain,values,expected in cases:
    np.testing.assert_array_equal(clean(values,dict(domain=domain)),expected)
np.testing.assert_array_equal(clean([-999,999999,-1],dict(domain='signed',sentinels=[999999])),[-999,np.nan,-1])
np.testing.assert_array_equal(clean([-999,-1,0,1],cfg['rules']['ML_track_module_eta0']),[np.nan,-1,np.nan,1])
d,s,x=load();rows=s['row'];np.testing.assert_array_equal(rows,np.flatnonzero(d['nominal']))
old=json.loads(str(d['metadata_json']))['features']
one={k:v[:1].copy() for k,v in s.items()};row=one['row'][0]
original=d['x'][row,old.index('ML_mu_x0_mm')];d['x'][row,old.index('ML_mu_x0_mm')]=999999
assert np.isnan(build(d,one)[0,cfg['features'].index('ML_track_chord_slope_x')])
d['x'][row,old.index('ML_mu_x0_mm')]=original
original_charge=d['x'][row,old.index('LeadTrack_charge')]
d['x'][row,old.index('LeadTrack_charge')]=-999
assert np.isnan(build(d,one)[0,cfg['features'].index('ML_track_qOverP0_GeVinv')])
assert np.isnan(build(d,one)[0,cfg['features'].index('ML_track_qOverP1_GeVinv')])
d['x'][row,old.index('LeadTrack_charge')]=original_charge
one['raw_charge'][0,0]=3.;one['status'][0,0]=48
assert build(d,one)[0,cfg['features'].index('VetoNu0_raw_charge')]==3.
one['status'][0,0]=128
assert np.isnan(build(d,one)[0,cfg['features'].index('VetoNu0_raw_charge')])
assert not ({'ML_mu_p_GeV','ML_track_p1_GeV','ML_track_pz1_GeV','ML_track_log_p1_over_p0'}&set(cfg['features']))
assert not ({q+'_charge' for q in SCINTILLATORS}&set(cfg['features']))
np.testing.assert_array_equal(x[:,cfg['features'].index('ML_mu_pz0_GeV')],d['reco_pz_GeV'][rows].astype('float32'))
with np.load(REPO/'ml/artifacts/stage56/predictions.npz') as z:
    ev=z['eval_row'];cal=z['cal_row'];ep=z['eval_raw_log'];cp=z['cal_raw_log'];md=json.loads(str(z['metadata_json']))
ei=np.searchsorted(rows,ev);ci=np.searchsorted(rows,cal)
np.testing.assert_array_equal(ev,rows[d['partition'][rows]=='validation'])
np.testing.assert_array_equal(cal,rows[d['cal_eligible'][rows]])
checks=[]
for j,seed in enumerate(cfg['seeds']):
    b=xgb.Booster(params={'nthread':1});b.load_model(REPO/f'ml/artifacts/stage56/{seed}/model.ubj')
    assert b.feature_names==cfg['features'] and json.loads(b.attr('feature_policy'))==cfg
    for idx,pred in [(ei,ep[j]),(ci,cp[j])]:
        np.testing.assert_array_equal(b.predict(xgb.DMatrix(x[idx],feature_names=cfg['features'],nthread=1)),pred)
    checks.append(dict(seed=seed,feature_names_and_policy_exact=True,calibration_prediction_exact=True,evaluation_prediction_exact=True))
offset=float(np.mean(np.log(d['truth_E_GeV'][cal])-cp.mean(axis=0)))
np.testing.assert_allclose(offset,md['offset_log'],rtol=0,atol=1e-14)
result=dict(formal_fits=len(checks),seed_models=checks,typed_policy_checks=7,dependency_checks=5,cohort_and_pz0_exact=True,
            calibration_offset_absolute_difference=abs(offset-md['offset_log']),
            N=len(rows),events_with_missing=int(np.isnan(x).any(1).sum()),
            wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
(REPO/'workbook/stage56_energy_ml/validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
