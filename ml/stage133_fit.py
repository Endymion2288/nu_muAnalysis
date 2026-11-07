"""Exactly four source-crossfit boundary proxies and three energy fits."""
import json
import multiprocessing as mp
import resource
import time
import numpy as np
import xgboost as xgb
from audited_features import configuration
from stage133_common import ROOT, OUT, CACHE, ART, inputs, protocol, load, table

G = None

def one(seed):
    d,p,x,names = G
    start = time.perf_counter(); cpu = time.process_time()
    train = d['role'] == 1
    y = np.log(d['truth_E_GeV'][train]); w = d['weight'][train]
    w = w/w.mean()
    params = dict(p['baseline']['xgboost'], seed=seed,
                  base_score=float(np.average(y,weights=w)), boost_from_average=0)
    model = xgb.train(params, xgb.DMatrix(x[train],label=y,weight=w,
                      feature_names=names,nthread=1),
                      num_boost_round=p['baseline']['rounds'])
    model.save_model(ART/f'B_{seed}.ubj')
    pred = model.predict(xgb.DMatrix(x,feature_names=names,nthread=1)).astype(float)
    reload = xgb.Booster(params=dict(nthread=1)); reload.load_model(ART/f'B_{seed}.ubj')
    np.testing.assert_array_equal(pred,reload.predict(xgb.DMatrix(x,feature_names=names,nthread=1)))
    return dict(seed=seed,train_N=int(train.sum()),features=63,
                CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-start,
                RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                reload_exact=True),pred

def main():
    global G
    assert not (OUT/'fit_lock.json').exists(), 'Do not repeat the seven-fit budget'
    d = inputs(); p = protocol(); cfg = p['policy']['proxy']
    assert set(d['role']) == {1, 2, 3}
    assert d['x'].shape == (len(d['role']), 62)
    assert np.all(d['pz'] > 50)
    CACHE.mkdir(parents=True, exist_ok=True)
    start=time.perf_counter(); cpu=time.process_time()
    ART.mkdir(parents=True,exist_ok=True)
    (OUT/'fit_lock.json').write_text(json.dumps(dict(proxy_tasks=4,energy_fits=3,
        repeat_X=False,reserved_forward=0,adaptive_followup=True),indent=2)+'\n')
    train=d['role']==1; fold=d['source']%3; target=d['flow'][:,0]
    z=np.full(len(train),np.nan); reports=[]; masks={}
    for f in [0,1,2,'final']:
        fit=train&np.isfinite(target)
        use=(train&(fold==f)) if f!='final' else ~train
        if f!='final':
            fit &= fold!=f
            assert not set(d['source'][fit]) & set(d['source'][use])
        masks[str(f)]=fit
        y=target[fit]; w=d['weight'][fit]; w=w/w.mean() if len(w) else w
        tick=time.perf_counter(); cost=time.process_time()
        mean=float(np.average(y,weights=w)) if len(y) else 0.
        if len(y)>=20 and np.ptp(y)>0:
            pars=dict(max_depth=cfg['max_depth'],eta=cfg['eta'],
                min_child_weight=cfg['min_child_weight'],reg_lambda=cfg['reg_lambda'],
                tree_method='hist',nthread=1,objective='reg:squarederror',
                seed=cfg['seed'],base_score=mean,boost_from_average=0)
            model=xgb.train(pars,xgb.DMatrix(d['x'][fit],label=y,weight=w,nthread=1),
                            num_boost_round=cfg['rounds'])
            value=model.predict(xgb.DMatrix(d['x'][use],nthread=1))
            model.save_model(ART/f'boundary_{f}.ubj'); method='fixed150tree'
        else:
            value=np.full(use.sum(),mean); method='frozen scarce-or-constant mean'
        z[use]=np.maximum(value,0)
        reports.append(dict(fold=f,train_label_N=int(fit.sum()),
            train_zero_label_N=int((y==0).sum()),prediction_N=int(use.sum()),
            train_weighted_mean_logKE=mean,method=method,
            CPU_s=time.process_time()-cost,wall_s=time.perf_counter()-tick,
            cal_test_label_fit_N=0))
    assert np.isfinite(z).all() and (z>=0).all()
    x=np.column_stack([d['x'],z]).astype('float32')
    np.savez_compressed(CACHE/'fit_matrix.npz',B=x,**{'proxy_fit_'+k:v for k,v in masks.items()})
    np.savez_compressed(ART/'proxy_predictions.npz',value=z)
    table('proxy_fits.tsv',reports)
    diagnostics=[]
    for role in [1,2,3]:
        use=(d['role']==role)&np.isfinite(target); w=d['weight'][use]
        diagnostics.append(dict(role=role,N=int((d['role']==role).sum()),
            finite_label_N=int(use.sum()),zero_label_N=int((target[use]==0).sum()),
            logKE_RMSE=float(np.sqrt(np.average((z[use]-target[use])**2,weights=w))),
            label='log1p(nonmu first-exit KE_GeV); not H or detector-visible energy',
            train_scope='source out-of-fold' if role==1 else 'train-only final proxy'))
    table('proxy_diagnostics.tsv',diagnostics)
    names=configuration()['features']+['predicted_nonmu_first_exit_logKE']
    G=d,p,x,names
    with mp.get_context('fork').Pool(3) as pool:
        results=pool.map(one,p['baseline']['seeds'])
    raw=np.mean([pred for _,pred in results],axis=0); cal=d['role']==2
    offset=float(np.average(np.log(d['truth_E_GeV'][cal])-raw[cal],weights=d['weight'][cal]))
    old=load('ml/artifacts/stage131/energy_predictions.npz')
    pred={k:old[k] for k in p['references']};pred['B']=raw+offset
    np.savez_compressed(ART/'energy_predictions.npz',**pred)
    (OUT/'fits.json').write_text(json.dumps(dict(proxy=reports,
        energy=[r for r,_ in results],offset=offset,
        parent_CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-start,
        actual_proxy_fits=sum(r['method']=='fixed150tree' for r in reports),
        energy_fits=len(results),X_retrained=False,GPU=0,
        cal_only_one_global_ensemble_offset=True,reserved_forward=0),indent=2)+'\n')

if __name__=='__main__':main()
