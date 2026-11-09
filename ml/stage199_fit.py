"""Six fixed direct62 fits: incoming loss versus train-bin-flat loss."""
import json
import subprocess
import time

import numpy as np
import xgboost as xgb

from audited_features import configuration
from stage199_common import DATA_ROOT,OUT,CACHE,ART,load,save,resources


def main():
    tick,cpu=time.perf_counter(),time.process_time()
    p=json.loads((OUT/'protocol.json').read_text())
    d=load(DATA_ROOT/'ntuples/energy_ml_stage199/input.npz')
    tr=d['role']==1;cal=d['role']==2;y=np.log(d['truth_E_GeV'])
    names=configuration()['features'];params=dict(p['model']['params'],objective=p['model']['objective']);trainids=np.flatnonzero(tr)[:2048]
    assert not ART.exists(),'Models already started; no automatic duplicate fit'
    ART.mkdir(parents=True);(ART/'started.txt').write_text('Six fixed direct62 fits\n')
    # Train-only numerical/performance check, no held-out labels or model selection.
    small=xgb.DMatrix(d['x'][trainids],label=y[trainids],weight=d['weight'][trainids],feature_names=names,nthread=8)
    checks=[];device='cpu';gpu_available=False
    try:
        info=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total,driver_version','--format=csv,noheader'],text=True)
        gpu_available=bool(info.strip())
    except (FileNotFoundError,subprocess.CalledProcessError):info='No accessible GPU'
    for choice in ['cpu']+(['cuda'] if gpu_available else []):
        wall,pcpu=time.perf_counter(),time.process_time()
        try:
            m=xgb.train(dict(params,device=choice,seed=p['model']['seeds'][0],base_score=float(np.average(y[trainids],weights=d['weight'][trainids])),boost_from_average=0),small,num_boost_round=20)
        except xgb.core.XGBoostError as error:
            if choice=='cpu':raise
            checks.append(dict(requested_device=choice,success=False,error=str(error),**resources(wall,pcpu)))
            continue
        pr=m.predict(small)
        assert np.isfinite(pr).all()
        actual=json.loads(m.save_config())['learner']['generic_param']['device']
        checks.append(dict(requested_device=choice,actual_device=actual,success=True,prefix_train_N=len(trainids),rounds=20,**resources(wall,pcpu)))
        if choice=='cuda' and actual.startswith('cuda'):device='cuda'
    save('platform.json',dict(xgboost=xgb.__version__,gpu=info,device=device,train_only_QA=checks,
        GPU_full_training_speedup_unmeasured=True,no_test_based_selection=True))
    target=xgb.DMatrix(d['x'],feature_names=names,nthread=8)
    predictions={};fitted=[];offsets={}
    for arm,weightname in [('incoming','weight'),('flat','flat_weight')]:
        w=d[weightname];matrix=xgb.DMatrix(d['x'][tr],label=y[tr],weight=w[tr],feature_names=names,nthread=8)
        init=float(np.average(y[tr],weights=w[tr]));ensemble=[]
        for seed in p['model']['seeds']:
            wall,pcpu=time.perf_counter(),time.process_time()
            config=dict(params,device=device,seed=seed,base_score=init,boost_from_average=0)
            model=xgb.train(config,matrix,num_boost_round=400)
            actual_device=json.loads(model.save_config())['learner']['generic_param']['device']
            assert actual_device.startswith(device)
            path=ART/f'{arm}_{seed}.ubj';model.save_model(path)
            back=xgb.Booster(params=dict(device=device,nthread=8));back.load_model(path)
            pred=model.predict(target).astype(float)
            np.testing.assert_array_equal(pred,back.predict(target));assert np.isfinite(pred).all()
            ensemble.append(pred);fitted.append(dict(arm=arm,seed=seed,rounds=400,params=config,actual_device=actual_device,
                model_reload_exact=True,**resources(wall,pcpu)))
            print(json.dumps(fitted[-1]),flush=True)
        raw=np.mean(ensemble,axis=0);predictions[arm+'_raw']=raw
        offsets[arm]={}
        for name,weight in [('cal',d['weight']),('flatcal',d['flat_weight'])]:
            off=float(np.average(y[cal]-raw[cal],weights=weight[cal]))
            predictions[arm+'_'+name]=raw+off;offsets[arm][name]=off
    CACHE.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(CACHE/'predictions.npz',**predictions,run=d['run'],eventID=d['eventID'],role=d['role'])
    save('fit.json',dict(passed=True,formal_fits_N=len(fitted),models=fitted,offsets=offsets,device=device,
        all_response_views_predicted=True,train_N=int(tr.sum()),cal_N=int(cal.sum()),test_N=int((d['role']==3).sum()),
        no_early_stopping=True,no_test_parameter_selection=True,**resources(tick,cpu)))


if __name__=='__main__':main()
