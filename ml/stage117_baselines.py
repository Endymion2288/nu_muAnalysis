"""Actually fit source/incoming-purged baseline ensembles using train only."""
import json
import multiprocessing as mp
import time

import numpy as np

from audited_features import configuration
from stage117_common import ART, ROOT, save, table
from stage117_folds import weights

G = None
MU_NAMES = configuration()['features'][:14] + ['ML_track_qOverP0_GeVinv',
    'ML_track_qOverP1_GeVinv','ML_track_bend_x','ML_track_bend_y']


def fit_one(spec):
    import xgboost as xgb
    name, seed, ids, columns, features = spec
    d,x=G;start=time.perf_counter();cpu=time.process_time()
    p=json.loads((ROOT/'workbook/stage87_energy_ml/protocol.json').read_text())['baseline']
    w=weights(d,ids);y=np.log(d['truth_E_GeV'][ids]);params=dict(p['xgboost'],seed=seed,
        base_score=float(np.average(y,weights=w)),boost_from_average=0)
    dm=xgb.DMatrix(x[ids][:,columns],label=y,weight=w,feature_names=features,nthread=1)
    model=xgb.train(params,dm,num_boost_round=p['rounds'])
    path=ART/f'{name}_{seed}.ubj';model.save_model(path)
    reload=xgb.Booster(params={'nthread':1});reload.load_model(path)
    pred=model.predict(dm);np.testing.assert_array_equal(pred,reload.predict(dm))
    return dict(name=name,seed=seed,N=len(ids),incoming=len(np.unique(d['key_id'][ids])),
        features=len(columns),rounds=p['rounds'],CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-start,
        reload_exact=True,params=params)


def generate(d,x,train,pairs):
    import xgboost as xgb
    global G
    G=d,x;ART.mkdir(parents=True,exist_ok=True)
    params=json.loads((ROOT/'workbook/stage87_energy_ml/protocol.json').read_text())['baseline']
    names=configuration()['features'];tasks=[]
    allpairs=dict(pairs);allpairs['mu_only']=(train,np.flatnonzero(d['role']!=1))
    for name,(fit,valid) in allpairs.items():
        cols=[names.index(n) for n in MU_NAMES] if name=='mu_only' else list(range(62))
        features=MU_NAMES if name=='mu_only' else names
        tasks.extend((name,seed,fit,cols,features) for seed in params['seeds'])
    assert len(tasks)==18
    with mp.get_context('fork').Pool(8) as pool:records=pool.map(fit_one,tasks)
    raw={};offset={}
    for name,(fit,valid) in allpairs.items():
        cols=[names.index(n) for n in MU_NAMES] if name=='mu_only' else list(range(62))
        features=MU_NAMES if name=='mu_only' else names
        # Fold prediction only on original train. The mu-only candidate is frozen
        # now, but its external forward happens after all four heads are locked.
        dm=xgb.DMatrix(x[train][:,cols],feature_names=features,nthread=1);pred=[]
        for seed in params['seeds']:
            model=xgb.Booster(params={'nthread':1});model.load_model(ART/f'{name}_{seed}.ubj')
            pred.append(model.predict(dm).astype(float))
        raw[name]=np.mean(pred,axis=0)
        ix=np.searchsorted(train,fit);w=weights(d,fit)
        offset[name]=float(np.average(np.log(d['truth_E_GeV'][fit])-raw[name][ix],weights=w))
    full_offset=float(np.average(np.log(d['truth_E_GeV'][train])-d['base_raw'][train],weights=weights(d,train)))
    full_IS=d['base_raw'][train]+full_offset
    full_OOF=np.full(len(train),np.nan)
    for j in range(3):
        name=f'outer{j}';valid=pairs[name][1];pos=np.searchsorted(train,valid)
        full_OOF[pos]=raw[name][pos]+offset[name]
    discovery,dev=pairs['outer0'];ipos=np.searchsorted(train,discovery)
    inner_OOF=np.full(len(discovery),np.nan)
    for j in [1,2]:
        name=f'inner{j}';valid=pairs[name][1];pos=np.searchsorted(discovery,valid)
        inner_OOF[pos]=raw[name][np.searchsorted(train,valid)]+offset[name]
    assert np.isfinite(full_OOF).all() and np.isfinite(inner_OOF).all()
    save('baseline_fits.json',dict(actual_model_fits=18,fold_models=15,mu_only_models=3,records=records,
        full_IS_train_offset=full_offset,fold_train_only_offsets=offset,
        full_stage87_cal_offset=float(d['base'][train[0]]-d['base_raw'][train[0]]),
        all_folds_train_only=True,external_forward_before_heads_locked=False,
        mu_features=MU_NAMES,fold_models_retention='transient; fit evidence and compact residuals retained'))
    np.savez_compressed(ART/'train_bases.npz',row=d['row'][train],IS=full_IS,OOF=full_OOF,
                        discovery_row=d['row'][discovery],inner_OOF=inner_OOF,
                        development_base=raw['outer0'][np.searchsorted(train,dev)]+offset['outer0'])
    return dict(IS=full_IS,OOF=full_OOF),dict(IS=raw['outer0'][ipos]+offset['outer0'],OOF=inner_OOF),raw['outer0'][np.searchsorted(train,dev)]+offset['outer0']


def mu_predict(d,x):
    import xgboost as xgb
    assert (ART/'candidates_locked.json').exists()
    names=configuration()['features'];cols=[names.index(n) for n in MU_NAMES]
    p=json.loads((ROOT/'workbook/stage87_energy_ml/protocol.json').read_text())['baseline'];pred=[]
    dm=xgb.DMatrix(x[:,cols],feature_names=MU_NAMES,nthread=1)
    for seed in p['seeds']:
        model=xgb.Booster(params={'nthread':1});model.load_model(ART/f'mu_only_{seed}.ubj')
        pred.append(model.predict(dm).astype(float))
    raw=np.mean(pred,axis=0);cal=d['role']==2
    offset=float(np.average(np.log(d['truth_E_GeV'][cal])-raw[cal],weights=d['weight'][cal]))
    save('mu_calibration.json',dict(offset=offset,method='same original full-cal mean log residual as Stage87 direct',
        external_model_locked_before_calibration=True,variant_selection=False))
    return raw+offset
