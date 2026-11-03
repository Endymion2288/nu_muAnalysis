#!/usr/bin/env python3
"""Exactly three fixed F7 fits with the released stage70 pi support appended."""
import json
import time
import numpy as np
import xgboost as xgb
from support_augmentation import OUT, ART, CACHE, arrays, begin, resources, save


class Budget(xgb.callback.TrainingCallback):
    def __init__(self,start):
        self.start=start

    def after_iteration(self,model,epoch,evals_log):
        if time.perf_counter()-self.start[0]>850 or time.process_time()-self.start[1]>850:
            raise RuntimeError('stage71 budget stop; no retry or shortened candidate')
        return False


def main():
    start=begin();p=json.loads((OUT/'protocol.json').read_text())
    assert not ART.exists(), 'never repeat successful or partially started formal fits'
    ART.mkdir(parents=True);(ART/'started.txt').write_text('one candidate; no restart\n')
    d=arrays(CACHE/'input.npz');assert d['train_x'].shape==(41475,62)
    assert xgb.__version__==p['xgboost_version']
    dm=xgb.DMatrix(d['train_x'],label=d['train_y'],feature_names=p['features'],nthread=1)
    assert dm.get_weight().size==0
    matrices={r:xgb.DMatrix(d[r+'_x'],feature_names=p['features'],nthread=1) for r in ['cal','eval']}
    predictions={r+'_row':d[r+'_row'] for r in ['cal','eval']};seed_preds={r:[] for r in matrices};records=[]
    for seed in p['seeds']:
        fit_start=begin();params=dict(p['xgboost'],seed=seed)
        model=xgb.train(params,dm,num_boost_round=p['rounds'],callbacks=[Budget(start)])
        measured=resources(fit_start);assert model.num_boosted_rounds()==400
        model.set_attr(feature_version=p['feature_version'],stage71_protocol=json.dumps(p))
        path=ART/(str(seed)+'.ubj');model.save_model(path)
        restored=xgb.Booster(params={'nthread':1});restored.load_model(path)
        for role,matrix in matrices.items():
            value=model.predict(matrix).astype(float)
            np.testing.assert_array_equal(value,restored.predict(matrix))
            seed_preds[role].append(value)
        records.append(dict(seed=seed,rounds=model.num_boosted_rounds(),train_N=41475,params=params,model_reload_exact=True,**measured))
        print('fit completed',json.dumps(records[-1]),flush=True)
    for r in matrices:predictions[r+'_raw_log']=np.asarray(seed_preds[r])
    offset=float(np.mean(np.log(d['cal_truth_E_GeV'])-predictions['cal_raw_log'].mean(axis=0)))
    measured=resources(start);assert measured['CPU_s']<900 and measured['wall_s']<900
    metadata=dict(status='completed',formal_fits=3,records=records,offset_log=offset,xgboost_version=xgb.__version__,
                  feature_version=p['feature_version'],**measured)
    np.savez_compressed(ART/'predictions.npz',**predictions,metadata_json=np.array(json.dumps(metadata)))
    save(OUT/'fit.json',metadata)
    (ART/'started.txt').unlink()
    print(json.dumps(metadata,indent=2),flush=True)


if __name__=='__main__':main()
