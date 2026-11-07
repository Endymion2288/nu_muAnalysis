"""One frozen matched-support energy experiment and source-crossfit supervision."""
import json
import multiprocessing as mp
import resource
import time
import numpy as np
import xgboost as xgb
from audited_features import configuration
from stage131_common import ROOT,OUT,CACHE,ART,load,protocol

G=None

def proxy(d,p):
    start=time.perf_counter();train=d['role']==1;fold=d['source']%3;value=np.full((len(train),5),np.nan);reports=[]
    cfg=p['proxy'];params=dict(max_depth=cfg['max_depth'],eta=cfg['eta'],min_child_weight=20,reg_lambda=10,tree_method='hist',nthread=1,objective='reg:squarederror',seed=cfg['seed'],boost_from_average=0)
    for j in range(5):
        for f in [0,1,2,'final']:
            fit=train&np.isfinite(d['lineage'][:,j+5]);use=(train&(fold==f)) if f!='final' else ~train
            if f!='final':fit&=fold!=f
            target=d['lineage'][fit,j+5];w=d['weight'][fit];w=w/w.mean() if len(w) else w
            if len(target)>=20 and np.ptp(target)>0:
                pars=dict(params,base_score=float(np.average(target,weights=w)))
                model=xgb.train(pars,xgb.DMatrix(d['x'][fit],label=target,weight=w,nthread=1),num_boost_round=cfg['rounds'])
                pred=model.predict(xgb.DMatrix(d['x'][use],nthread=1));model.save_model(ART/f'proxy_{j}_{f}.ubj');method='frozen150tree'
            else:
                pred=np.full(use.sum(),float(np.average(target,weights=w)) if len(target) else 0.);method='prespecified scarce-or-constant-label mean'
            value[use,j]=np.clip(pred,0,1)
            reports.append(dict(target=j,fold=f,train_label_N=int(fit.sum()),predicted_N=int(use.sum()),method=method,source_overlap_N=0 if f!='final' else None))
            if f!='final':assert not set(d['source'][fit])&set(d['source'][use])
    assert np.isfinite(value).all();np.savez_compressed(ART/'proxy_predictions.npz',value=value)
    (OUT/'proxy_fits.json').write_text(json.dumps(dict(reports=reports,wall_s=time.perf_counter()-start,cal_test_label_fit_N=0,scope='new G4 lineage supervision on existing measured X; no new sensor input and no truthavailability at deployment'),indent=2)+'\n')
    return value

def one(spec):
    arm,seed=spec;d,p,matrices,names=G;start=time.perf_counter();cpu=time.process_time();train=d['role']==1
    x=matrices[arm];y=np.log(d['truth_E_GeV'][train]);w=d['weight'][train];w=w/w.mean()
    pars=dict(p['baseline']['xgboost'],seed=seed,base_score=float(np.average(y,weights=w)),boost_from_average=0)
    model=xgb.train(pars,xgb.DMatrix(x[train],label=y,weight=w,feature_names=names[arm],nthread=1),num_boost_round=p['baseline']['rounds'])
    model.save_model(ART/f'{arm}_{seed}.ubj');pred=model.predict(xgb.DMatrix(x,feature_names=names[arm],nthread=1)).astype(float)
    reload=xgb.Booster(params=dict(nthread=1));reload.load_model(ART/f'{arm}_{seed}.ubj')
    np.testing.assert_array_equal(pred,reload.predict(xgb.DMatrix(x,feature_names=names[arm],nthread=1)))
    return dict(arm=arm,seed=seed,features=x.shape[1],train_N=int(train.sum()),CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-start,reload_exact=True,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),pred

def main():
    global G
    assert not (OUT/'fit_lock.json').exists(),'Do not repeat frozen fit budget'
    start=time.perf_counter();p=protocol();d=load(CACHE/'matched_input.npz');ART.mkdir(parents=True,exist_ok=True)
    assert set(d['role'])=={1,2,3}
    (OUT/'fit_lock.json').write_text(json.dumps(dict(arms=list(p['arms']),energy_fits=18,proxy_tasks=20,roles=[1,2,3],reserve_forward=0))+'\n')
    z=proxy(d,p);base=configuration()['features'];a=[f'oracle_available_{j}' for j in range(7)];u=[f'unsplit_prompt_deposit_{j}' for j in range(5)];l=[f'rootmu_prompt_fraction_{j}' for j in range(5)];flow=['nonmu_exit_KE'];proxy_names=[f'predicted_rootmu_prompt_fraction_{j}' for j in range(5)]
    available=d['availability'][:,5:];total=d['total'][:,5:];lineage=d['lineage'][:,5:]
    matrices=dict(X=d['x'],A=np.column_stack([d['x'],available]),U=np.column_stack([d['x'],available,total]),L=np.column_stack([d['x'],available,total,lineage]),F=np.column_stack([d['x'],available,total,d['flow']]),P=np.column_stack([d['x'],z]))
    matrices={k:v.astype('float32') for k,v in matrices.items()};names=dict(X=base,A=base+a,U=base+a+u,L=base+a+u+l,F=base+a+u+flow,P=base+proxy_names)
    np.savez_compressed(CACHE/'fit_matrices.npz',**matrices)
    G=d,p,matrices,names;tasks=[(arm,seed) for arm in p['arms'] for seed in p['baseline']['seeds']]
    with mp.get_context('fork').Pool(8) as pool:results=pool.map(one,tasks)
    predictions={};offsets={};cal=d['role']==2
    for arm in p['arms']:
        raw=np.mean([v for r,v in results if r['arm']==arm],axis=0)
        offset=float(np.average(np.log(d['truth_E_GeV'][cal])-raw[cal],weights=d['weight'][cal]));offsets[arm]=offset;predictions[arm]=raw+offset
    # Preserve the large-pool f0 as a reference; it is not the matched information control.
    original=[]
    for seed in p['baseline']['seeds']:
        model=xgb.Booster(params=dict(nthread=1));model.load_model(ROOT/f'ml/artifacts/stage87/direct_{seed}.ubj');assert model.feature_names==base
        original.append(model.predict(xgb.DMatrix(d['x'],feature_names=base,nthread=1)).astype(float))
    cached=load(ROOT/'ml/artifacts/stage87/predictions.npz');delta=cached['direct_cal']-cached['direct_raw'];assert np.ptp(delta)<1e-12
    predictions['direct_cal']=np.mean(original,axis=0)+float(delta[0]);predictions['traditional']=np.log(d['pz']/.8)
    np.savez_compressed(ART/'energy_predictions.npz',**predictions)
    (OUT/'fits.json').write_text(json.dumps(dict(results=[r for r,_ in results],offsets=offsets,wall_s=time.perf_counter()-start,train_only_supervision=True,cal_only_offsets=True,reserve_forward=0,GPU=0,reference='f0 largepool,not matched baseline'),indent=2)+'\n');print('Completed frozen18 energy fits',time.perf_counter()-start)

if __name__=='__main__':main()
