#!/usr/bin/env python3
"""No-fit alignment, identity/calibration QA and measured input preparation for stage71."""
from datetime import datetime, timezone
import json
import numpy as np
import xgboost as xgb
from audited_features import load, configuration, SCINTILLATORS, WAVE_INVALID, clean
from alternative_calibration import reference_matrix
from support_augmentation import REPO, OUT, ART, CACHE, begin, resources, save, table, masks, COST


def main():
    start=begin();OUT.mkdir(exist_ok=True);CACHE.mkdir(exist_ok=True)
    assert not (OUT/'protocol.json').exists() and not ART.exists()
    contract=json.loads((REPO/'ml/configs/alternative_support_augmentation.json').read_text())
    cfg=configuration();d,s,x=load();rows=s['row']
    role=np.full(len(rows),'unused',dtype='<U6')
    role[d['train_eligible'][rows]]='train';role[d['cal_eligible'][rows]]='cal';role[d['partition'][rows]=='validation']='eval'
    assert [int((role==r).sum()) for r in ['train','cal','eval']]==[41447,8440,14057]
    missing=np.isnan(x).any(1)
    assert int(missing.sum())==42 and [int((missing&(role==r)).sum()) for r in ['train','cal','eval']]==[21,3,7]
    protected=rows[missing&(role=='unused')];assert len(protected)==11
    assert not set(cfg['features'])&{'ML_mu_p_GeV','ML_track_p1_GeV','ML_track_pz1_GeV','ML_track_log_p1_over_p0'}
    assert not set(cfg['features'])&{n+'_charge' for n in SCINTILLATORS}
    assert sum(n+'_raw_charge' in cfg['features'] for n in SCINTILLATORS)==11
    np.testing.assert_array_equal(clean([-999,-1,0,1],dict(domain='nonnegative')),[np.nan,np.nan,0,1])
    np.testing.assert_array_equal(clean([-999,-1,0],dict(domain='signed')),[-999,-1,0])
    with np.load(REPO/'ntuples/energy_ml_stage70/support.npz') as z:
        md=json.loads(str(z['metadata_json']));new={k:z[k] for k in z.files if k!='metadata_json'}
    assert md['features']==cfg['features'] and md['feature_version']==cfg['version']
    assert md['calibration_reference']=='WAVE-Calibration-01-LG' and md['calibration_closure']['passed']
    for key,name in [('calibration_amendment','calibration_amendment.json'),('calibration_closure','calibration_closure.json')]:
        assert md[key]==json.loads((REPO/'workbook/stage70_energy_ml'/name).read_text())
    c=[cfg['features'].index(f'ML_calo{i}_E_EM_GeV') for i in range(4)]+[cfg['features'].index('ML_calo_total_E_EM_GeV')]
    other=[j for j in range(62) if j not in c]
    np.testing.assert_array_equal(new['x'][:,other],new['x_produced'][:,other])
    for run in np.unique(new['run']):
        take=new['run']==run
        np.testing.assert_array_equal(new['x'][take],reference_matrix(new['x_produced'][take],int(run)))
    for j,det in enumerate(SCINTILLATORS):
        expected=new['raw_charge'][:,j].astype('float32');expected[(new['status'][:,j].astype(int)&WAVE_INVALID)!=0]=np.nan
        expected[~np.isfinite(expected)]=np.nan
        np.testing.assert_array_equal(new['x'][:,cfg['features'].index(det+'_raw_charge')],expected)
    keep=new['new_training_support'];assert int(keep.sum())==contract['new_unique_training_support_N']==28
    assert np.all(new['source_index'][keep]==0) and np.all(new['component'][keep]=='pi')
    keys=set(map(tuple,new['incoming'][keep]));assert len(keys)==28
    assert not keys&set(map(tuple,d['incoming']))
    assert set(new['group'][keep])<=set(d['group'][rows[role=='train']])
    for a,b in [('train','cal'),('train','eval'),('cal','eval')]:
        assert not set(map(tuple,d['incoming'][rows[role==a]]))&set(map(tuple,d['incoming'][rows[role==b]]))
    with np.load(REPO/'ml/artifacts/stage56/predictions.npz') as z:
        baseline={k:z[k] for k in z.files if k!='metadata_json'};base_md=json.loads(str(z['metadata_json']))
    train=role=='train';payload=dict(train_x=np.concatenate([x[train],new['x'][keep]]),
        train_y=np.r_[np.log(d['truth_E_GeV'][rows[train]]),np.log(new['truth_E_GeV'][keep])],
        train_old_row=rows[train],train_new_incoming=new['incoming'][keep])
    records=[]
    for r in ['cal','eval']:
        use=role==r;idx=rows[use]
        np.testing.assert_array_equal(baseline[r+'_row'],idx)
        for k in ['truth_E_GeV','y_lepton','confirmed','group','source','component','incoming']:
            payload[r+'_'+k]=d[k][idx]
        payload.update({r+'_row':idx,r+'_x':x[use],r+'_pz':d['reco_pz_GeV'][idx],r+'_missing':missing[use],
                        r+'_F7':baseline[r+'_raw_log'].mean(axis=0)+base_md['offset_log']})
    for label,take in [('old_train',train),('new_support',keep)]:
        dd=dict(truth_E_GeV=d['truth_E_GeV'][rows] if label=='old_train' else new['truth_E_GeV'],
                pz=d['reco_pz_GeV'][rows] if label=='old_train' else new['reco_pz_GeV'],
                y_lepton=d['y_lepton'][rows] if label=='old_train' else new['y_lepton'],
                confirmed=d['confirmed'][rows] if label=='old_train' else new['confirmed'],missing=missing if label=='old_train' else np.isnan(new['x']).any(1))
        for name,mask in masks(dd).items():records.append(dict(sample=label,stratum=name,N=int((take&mask).sum())))
    assert payload['train_x'].shape==(41475,62) and np.isfinite(payload['train_y']).all()
    pilot_start=begin();pilot=xgb.DMatrix(payload['train_x'][:512],label=payload['train_y'][:512],feature_names=cfg['features'],nthread=1)
    assert pilot.num_row()==512 and pilot.num_col()==62
    np.testing.assert_array_equal(pilot.get_label(),payload['train_y'][:512].astype('float32'))
    assert pilot.get_weight().size==0  # XGBoost's implicit unit weights.
    pilot_resources=resources(pilot_start)
    assert not (CACHE/'input.npz').exists();np.savez_compressed(CACHE/'input.npz',**payload)
    with np.load(CACHE/'input.npz') as z:
        for key,value in payload.items():np.testing.assert_array_equal(z[key],value)
    table(OUT/'training_support.tsv',records)
    save(OUT/'input_validation.json',dict(passed=True,**resources(start),old_train_cal_eval_N=[41447,8440,14057],new_N=28,
        original_missing_N=42,eligible_missing_N=[21,3,7],protected_missing_rows=protected.tolist(),new_key_intersection_all_stage55=0,
        new_internal_unique=True,reference_matrix_exact=True,unchanged_other_features=57,raw11_status_exact=True,
        original_roles_unchanged=True,forbidden_linear_momenta_absent=True,typed_NaN_signed_policy=True,
        old_F7_prediction_rows_exact=True,F7_new_inference=0,model_fits=0,locked_test_read=False,
        no_fit_DMatrix_N=512,no_fit_DMatrix_resources=pilot_resources,readback_exact=True,
        logical_input_bytes=(CACHE/'input.npz').stat().st_size,uncompressed_array_bytes=sum(v.nbytes for v in payload.values()),
        physical_EOS_network_bytes='未测量'))
    p=dict(stage=71,starting_commit='8ba4c12',frozen_utc=datetime.now(timezone.utc).isoformat(),contract=contract,
        feature_version=cfg['version'],features=cfg['features'],xgboost=cfg['xgboost'],seeds=cfg['seeds'],rounds=cfg['rounds'],
        xgboost_version=xgb.__version__,train_N=41475,cal_N=8440,eval_N=14057,formal_fits=3,formal_jobs=1,
        weights='implicit unit MC',ordering='original sorted nominal train rows, then stable stage70 new_training_support rows',
        target='direct log(E_nu/GeV)',calibration='one global mean log offset of the3seed ensemble on8440cal; raw parallel; main augmented_cal',
        bootstrap_seed=2026110371,bootstrap_replicates=500,bootstrap_scope='component-stratified conservative canonical source groups; paired fixed predictions, no refit/offset or systematics coverage',
        recovery_ratio_upper95_max=1.05,cost_ratio_upper95_max=COST,
        max_tail50_increase_pp=2.,request_cpus=1,request_memory_MB=3000,request_disk_MB=180,
        total_CPU_budget_s=900,wall_budget_s=900,retained_budget_bytes=10000000,
        F7_new_fit=0,F7_new_inference=0,new_ROOT_RDO_production=0,spectral_toys=0,locked_test=False,
        no_fit_QA_only=True,cost_basis='stage56 actual3fit wall13.407717s; current no-fit DMatrix and exact input readback QA; new fit cost not yet measured')
    save(OUT/'protocol.json',p);print(json.dumps(dict(**resources(start),train_N=41475,new_N=28,input_bytes=(CACHE/'input.npz').stat().st_size),indent=2))


if __name__=='__main__':main()
