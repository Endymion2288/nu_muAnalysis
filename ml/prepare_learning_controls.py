#!/usr/bin/env python3
"""Reuse A0/I0 and compute A0's actual independent B-cal predictions for a common offset."""
import json
import resource
import time
import numpy as np
import xgboost as xgb
from learning_capacity import REPO,CACHE,OUT,configuration,load_inputs

cfg=configuration();tick,cpu=time.perf_counter(),time.process_time();d,x=load_inputs();y=np.log(d['truth_E_GeV']);selected=np.flatnonzero(d['selected'])
assert not (CACHE/'support_controls.npz').exists(),'Do not silently regenerate completed controls'
with np.load(REPO/'ntuples/energy_ml_stage42/A_predictions.npz') as z:
    np.testing.assert_array_equal(z['cache_row'],np.arange(len(x)));large=z['A0']
with np.load(REPO/'ntuples/energy_ml_stage42/B_predictions.npz') as z:
    np.testing.assert_array_equal(z['cache_row'],selected);small=z['I0']
common=np.full(len(x),np.nan);records=[]
for f in range(3):
    ca=(d['fold']==(f+2)%3)&d['selected'];ev=(d['fold']==f)&d['selected']
    for part,name,pool in [('A','A0',np.ones(len(x),bool)),('B','I0',d['selected'])]:
        path=REPO/f'ml/artifacts/stage42/{part}/{f}'
        with np.load(path/'predictions.npz') as z:md=json.loads(str(z['metadata_json']));old=z[name];oldrows=z['cache_row']
        rec=next(r for r in md['records'] if r['model']==name);assert md['config']['xgboost']==cfg['xgboost'] and md['config']['seed']==cfg['seed']
        model=xgb.Booster(params={'nthread':1});model.load_model(path/(name+'.ubj'));assert model.num_features()==65 and model.num_boosted_rounds()==400
        orig_ca=pool&(d['fold']==(f+2)%3);orig_ev=pool&(d['fold']==f)
        np.testing.assert_array_equal(oldrows,np.flatnonzero(orig_ev))
        cal=model.predict(xgb.DMatrix(x[orig_ca]));offset=float(np.mean(y[orig_ca]-cal));assert offset==rec['log_offset']
        pred=model.predict(xgb.DMatrix(x[orig_ev]));energy=np.exp(pred.astype(float)+offset)
        np.testing.assert_array_equal(pred,(np.log(old)-offset).astype('float32'));np.testing.assert_allclose(energy,old,rtol=1e-14,atol=0)
        current_cal=model.predict(xgb.DMatrix(x[ca]));boffset=float(np.mean(y[ca]-current_cal))
        if part=='B':assert boffset==offset
        else:
            current_ev=model.predict(xgb.DMatrix(x[ev]));common[ev]=np.exp(current_ev.astype(float)+boffset)
        records.append(dict(fold=f,model=name,part=part,original_log_offset=offset,common_B_log_offset=boffset,
                            common_B_cal_N=int(ca.sum()),original_cal_N=int(orig_ca.sum()),train_N=int((pool&(d['fold']==(f+1)%3)).sum()),
                            raw_float32_prediction_exact=True,energy_max_relative_difference=float(np.max(abs(energy/old-1))),
                            actual_current_model_B_cal_predictions=True,cal_eval_source_disjoint=not bool(set(d['group'][ca])&set(d['group'][ev]))))
assert np.isfinite(common[selected]).all()
np.savez_compressed(CACHE/'support_controls.npz',cache_row=selected,I0=small,A0=large[selected],A0_common_B=common[selected])
md=dict(records=records,old_models_loaded=6,new_energy_fits=0,probability_mapping_fits=0,common_offset_fits=3,
        wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
(OUT/'control_readback.json').write_text(json.dumps(md,indent=2)+'\n');print(json.dumps({k:v for k,v in md.items() if k!='records'}))
