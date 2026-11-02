#!/usr/bin/env python3
"""Three fixed direct-energy fits on the identical nominal50 training cohort."""
import json
import resource
import time

import numpy as np
import xgboost as xgb

from audited_features import REPO, configuration, load

tick,cpu=time.perf_counter(),time.process_time();cfg=configuration()
dest=REPO/'ml/artifacts/stage56';assert not dest.exists(),'Never repeat successful fits'
d,s,x=load();rows=s['row'];tr=np.flatnonzero(d['train_eligible'][rows]);cal=np.flatnonzero(d['cal_eligible'][rows]);ev=np.flatnonzero(d['partition'][rows]=='validation')
assert (len(tr),len(cal),len(ev))==(41447,8440,14057)
assert all(not n.startswith(('truth','t_','run','eventID')) for n in cfg['features'])
dm=xgb.DMatrix(x[tr],label=np.log(d['truth_E_GeV'][rows][tr]),feature_names=cfg['features'],nthread=1)
preds=[];cals=[];records=[]
for seed in cfg['seeds']:
    params=dict(cfg['xgboost'],seed=seed);start=time.perf_counter()
    model=xgb.train(params,dm,num_boost_round=cfg['rounds']);fit_wall=time.perf_counter()-start
    model.set_attr(feature_version=cfg['version'],feature_policy=json.dumps(cfg))
    path=dest/str(seed)/'model.ubj';path.parent.mkdir(parents=True);model.save_model(path)
    restored=xgb.Booster(params={'nthread':1});restored.load_model(path)
    p=model.predict(xgb.DMatrix(x[ev],feature_names=cfg['features'],nthread=1)).astype(float)
    np.testing.assert_array_equal(p,restored.predict(xgb.DMatrix(x[ev],feature_names=cfg['features'],nthread=1)))
    c=model.predict(xgb.DMatrix(x[cal],feature_names=cfg['features'],nthread=1)).astype(float)
    preds.append(p);cals.append(c)
    records.append(dict(seed=seed,train_N=len(tr),cal_N=len(cal),eval_N=len(ev),features=x.shape[1],rounds=cfg['rounds'],fit_wall_s=fit_wall,model_reload_exact=True,params=params))
offset=float(np.mean(np.log(d['truth_E_GeV'][rows][cal])-np.mean(cals,axis=0)))
metadata=dict(feature_version=cfg['version'],fits=records,offset_log=offset,wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
np.savez_compressed(dest/'predictions.npz',eval_row=rows[ev],cal_row=rows[cal],eval_raw_log=np.asarray(preds),cal_raw_log=np.asarray(cals),metadata_json=np.array(json.dumps(metadata)))
print(json.dumps(metadata),flush=True)
