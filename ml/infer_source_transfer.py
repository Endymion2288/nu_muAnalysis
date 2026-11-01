#!/usr/bin/env python3
"""Only frozen old models/offsets/calibration on new-to-these-models sources."""
import json
import resource
import time
import joblib
import numpy as np
import xgboost as xgb
from source_transfer import REPO,CACHE,configuration,load_inputs

cfg=configuration();tick,cpu=time.perf_counter(),time.process_time();rows,d,x=load_inputs()
path=CACHE/'predictions.npz';assert not path.exists(),'Do not silently repeat successful full inference'
states=joblib.load(CACHE/'original_maps.joblib');n=len(rows)
saved=dict(cache_row=rows,local=np.full(n,np.nan),oracle_z=np.full(n,np.nan),q_local=np.full((n,6),np.nan),q_oracle_z=np.full((n,6),np.nan),prior=np.full((n,6),np.nan))
records=[]
for f in range(3):
    take=d['fold']==f
    for name in cfg['models']:
        state=states[(f,name)];start=time.perf_counter()
        values=x[take] if name=='local' else np.column_stack([x[take],d['vertex_z_mm'][take]]).astype('float32')
        model=xgb.Booster(params={'nthread':1});model.load_model(REPO/state['model_path'])
        assert model.num_features()==values.shape[1] and model.num_boosted_rounds()==400
        log_pred=model.predict(xgb.DMatrix(values)).astype(float)+state['log_offset']
        saved[name][take]=np.exp(log_pred);saved['q_'+name][take]=state['pipe'].predict_proba(log_pred[:,None]);saved['prior'][take]=state['prior']
        records.append(dict(fold=f,model=name,N=int(take.sum()),columns=values.shape[1],wall_s=time.perf_counter()-start))
for key in ['local','oracle_z','q_local','q_oracle_z','prior']:assert np.isfinite(saved[key]).all()
for name in cfg['models']:
    assert (saved[name]>0).all() and (saved['q_'+name]>0).all()
    np.testing.assert_allclose(saved['q_'+name].sum(axis=1),1,atol=1e-12)
saved.update({k:d[k] for k in ['run','eventID','group','component','fold','reco_p_GeV','truth_E_GeV','y_lepton','vertex_z_mm','primary_kinematic_parent_proxy']})
md=dict(stage=48,config=cfg,events=n,sources=len(set(d['group'])),energy_fits=0,target_calibration_fits=0,
        original_calibration_states_only=True,records=records,wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,
        peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,xgboost_version=xgb.__version__,numpy_version=np.__version__)
np.savez_compressed(path,**saved,metadata_json=np.array(json.dumps(md)));print(json.dumps(md),flush=True)
