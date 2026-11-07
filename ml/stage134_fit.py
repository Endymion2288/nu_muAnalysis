"""Exactly three fixed fits for the no-ideal-deposit boundary mechanism."""
import json
import multiprocessing as mp
import resource
import time
import numpy as np
import xgboost as xgb
from audited_features import configuration
from stage134_common import ROOT,OUT,CACHE,ART,load,inputs,protocol
G=None

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
    assert not (OUT/'fit_lock.json').exists(),'Do not repeat the three-fit budget'
    tick=time.perf_counter();d=inputs();p=protocol()
    assert set(d['role'])=={1,2,3} and np.all(d['pz']>50)
    ART.mkdir(parents=True,exist_ok=True);CACHE.mkdir(parents=True,exist_ok=True)
    (OUT/'fit_lock.json').write_text(json.dumps(dict(arms=['AK'],energy_fits=3,reserved_forward=0))+'\n')
    x=np.column_stack([d['x'],d['availability'][:,5:],d['flow']]).astype('float32')
    names=configuration()['features']+[f'oracle_available_{j}' for j in range(7)]+['nonmu_exit_KE']
    matrices=dict(AK=x);np.savez_compressed(CACHE/'fit_matrix.npz',**matrices)
    G=d,p,matrices,dict(AK=names)
    with mp.get_context('fork').Pool(3) as pool:
        results=pool.map(one,[('AK',seed) for seed in p['baseline']['seeds']])
    raw=np.mean([v for _,v in results],axis=0);cal=d['role']==2
    offset=float(np.average(np.log(d['truth_E_GeV'][cal])-raw[cal],weights=d['weight'][cal]))
    frozen=load('ml/artifacts/stage131/energy_predictions.npz')
    pred={name:frozen[name] for name in p['references']};pred['AK']=raw+offset
    np.savez_compressed(ART/'energy_predictions.npz',**pred)
    (OUT/'fits.json').write_text(json.dumps(dict(results=[r for r,_ in results],offset=offset,wall_s=time.perf_counter()-tick,energy_fits=3,reference_retrained=False,GPU=0,reserved_forward=0),indent=2)+'\n')

if __name__=='__main__':main()
