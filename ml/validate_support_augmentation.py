#!/usr/bin/env python3
"""Independent reload/row/calibration and fixed-reference validation of stage71."""
import json
import numpy as np
import xgboost as xgb
from support_augmentation import REPO, OUT, ART, CACHE, begin, resources, arrays, save


def review_arrays():
    if (CACHE/'input.npz').exists():
        return arrays(CACHE/'input.npz'),arrays(ART/'predictions.npz')
    from audited_features import load
    d=arrays(ART/'comparison.npz');old,s,x=load();rows=s['row']
    for role in ['cal','eval']:
        idx=np.searchsorted(rows,d[role+'_row'])
        np.testing.assert_array_equal(rows[idx],d[role+'_row'])
        d[role+'_x']=x[idx]
    with np.load(REPO/'ntuples/energy_ml_stage70/support.npz') as z:
        keep=z['new_training_support'];tr=old['train_eligible'][rows]
        d['train_x']=np.concatenate([x[tr],z['x'][keep]])
        d['train_y']=np.r_[np.log(old['truth_E_GeV'][rows[tr]]),np.log(z['truth_E_GeV'][keep])]
        d['train_new_incoming']=z['incoming'][keep]
    return d,dict(d,metadata_json=np.array((OUT/'fit.json').read_text()))


def main():
    start=begin();p=json.loads((OUT/'protocol.json').read_text());d,a=review_arrays()
    md=json.loads(str(a['metadata_json']));assert len(md['records'])==3
    checks=[]
    for j,seed in enumerate(p['seeds']):
        model=xgb.Booster(params={'nthread':1});model.load_model(ART/(str(seed)+'.ubj'))
        assert model.feature_names==p['features'] and model.num_boosted_rounds()==400
        assert json.loads(model.attr('stage71_protocol'))==p
        assert md['records'][j]['params']==dict(p['xgboost'],seed=seed)
        for role in ['cal','eval']:
            np.testing.assert_array_equal(a[role+'_row'],d[role+'_row'])
            values=model.predict(xgb.DMatrix(d[role+'_x'],feature_names=p['features'],nthread=1))
            np.testing.assert_array_equal(values,a[role+'_raw_log'][j])
        checks.append(dict(seed=seed,reloaded_predictions_exact=True,rounds=400,parameters_exact=True))
    base=arrays(REPO/'ml/artifacts/stage56/predictions.npz');bm=json.loads(str(base['metadata_json']))
    assert bm['feature_version']==p['feature_version']
    for record,seed in zip(bm['fits'],p['seeds']):
        assert record['seed']==seed and record['rounds']==400
        assert record['params']==dict(p['xgboost'],seed=seed)
    for role in ['cal','eval']:
        np.testing.assert_array_equal(base[role+'_row'],d[role+'_row'])
        np.testing.assert_array_equal(d[role+'_F7'],base[role+'_raw_log'].mean(axis=0)+bm['offset_log'])
    corrected=a['cal_raw_log'].mean(axis=0)+md['offset_log']
    residual_mean=float(np.mean(np.log(d['cal_truth_E_GeV'])-corrected));assert abs(residual_mean)<1e-12
    with np.load(REPO/'ntuples/energy_ml_stage70/support.npz') as z:
        take=z['new_training_support'];np.testing.assert_array_equal(d['train_x'][-28:],z['x'][take])
        np.testing.assert_array_equal(d['train_y'][-28:],np.log(z['truth_E_GeV'][take]))
        np.testing.assert_array_equal(d['train_new_incoming'],z['incoming'][take])
    assert d['train_x'].shape==(41475,62)
    assert np.isnan(d['train_x'][:41447]).any(1).sum()==21
    assert [np.sum(d[r+'_missing']) for r in ['cal','eval']]==[3,7]
    save(OUT/'validation.json',dict(passed=True,**resources(start),models=checks,formal_fits=3,additional_fits=0,
         F7_prediction_arrays_reused_exact=True,F7_archived_parameters_seeds_rounds_exact=True,
         F7_new_inference=0,reference_x_appended_exact=True,training_labels_log_GeV_exact=True,
         single_global_cal_mean_residual=residual_mean,old_train_cal_eval_N=[41447,8440,14057],new_N=28,
         eligible_missing_N=[21,3,7],protected_unused_missing_N=11,no_OOF_claim=True,locked_test=False))
    print('three reloads, rows, reference x, original F7 arrays and global offset verified')


if __name__=='__main__':main()
