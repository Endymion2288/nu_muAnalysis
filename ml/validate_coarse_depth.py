#!/usr/bin/env python3
"""Read serialized models to prove source OOF provenance and energy input paths; no fits."""
import json
import numpy as np
import xgboost as xgb
from coarse_depth import REPO,load_inputs,region_labels,inner_roles,smoothed_prior

rows,d,x=load_inputs();cfg=json.loads((REPO/'ml/configs/coarse_depth.json').read_text());lab=region_labels(d['vertex_z_mm'],cfg['regions_mm'])
with np.load(REPO/'ntuples/energy_ml_stage45/predictions.npz') as z:joined={k:z[k] for k in z.files}
with np.load(REPO/'ntuples/energy_ml_stage45/depth_predictions.npz') as z:depth={k:z[k] for k in z.files}
for values in [joined,depth]:np.testing.assert_array_equal(values['cache_row'],rows)
fits=[]; energy_roundtrip_relative_errors=[]
for f in range(3):
    path=REPO/f'ml/artifacts/stage45/formal/{f}'
    with np.load(path/'predictions.npz') as z:part={k:z[k] for k in z.files}
    md=json.loads(str(part['metadata_json']));assert md['config']==cfg and md['fold']==f and not md['smoke'];fits+=md['records']
    tr=np.flatnonzero(d['fold']==(f+1)%3);ca=np.flatnonzero(d['fold']==(f+2)%3);ev=np.flatnonzero(d['fold']==f)
    for key,ids in [('cache_row',ev),('train_cache_row',tr),('cal_cache_row',ca)]:np.testing.assert_array_equal(part[key],rows[ids])
    for left,right in [(tr,ca),(tr,ev),(ca,ev)]:assert not set(d['group'][left])&set(d['group'][right])
    inner,_=inner_roles(d['group'],d['fold']==(f+1)%3);np.testing.assert_array_equal(part['inner_fold'],inner[tr])
    for name,train,predict,expected in [
        ('depth_inner0',tr[inner[tr]!=0],{'oof':tr[inner[tr]==0]},{'oof':part['depth_train_oof'][inner[tr]==0]}),
        ('depth_inner1',tr[inner[tr]!=1],{'oof':tr[inner[tr]==1]},{'oof':part['depth_train_oof'][inner[tr]==1]}),
        ('depth_full',tr,{'calibration':ca,'evaluation':ev},{'calibration':part['depth_cal'],'evaluation':part['depth_q']})]:
        rec=next(r for r in md['records'] if r['model']==name);prior=smoothed_prior(lab[train],5,cfg['depth_prior_alpha'])
        np.testing.assert_array_equal(prior,rec['depth_prior']);assert rec['train_sources']==sorted(set(d['group'][train]));assert rec['rounds']==200 and rec['columns']==87
        model=xgb.Booster(params={'nthread':1});model.load_model(path/(name+'.ubj'));assert model.num_boosted_rounds()==200 and model.num_features()==87
        for role,ids in predict.items():
            assert not set(d['group'][ids])&set(d['group'][train]);assert rec['predict_sources'][role]==sorted(set(d['group'][ids]))
            q=model.predict(xgb.DMatrix(x[ids],base_margin=np.tile(np.log(prior).astype('float32'),(len(ids),1))))
            np.testing.assert_array_equal(q,expected[role])
        if name!='depth_full':np.testing.assert_array_equal(part['depth_train_prior'][inner[tr]==int(name[-1])],np.tile(prior,((inner[tr]==int(name[-1])).sum(),1)))
        else:np.testing.assert_array_equal(prior,part['depth_prior'])
    np.testing.assert_array_equal(depth['depth_q'][ev],part['depth_q']);np.testing.assert_array_equal(depth['depth_prior'][ev],np.tile(part['depth_prior'],(len(ev),1)))
    soft=np.full((len(rows),5),np.nan);soft[tr]=part['depth_train_oof'];soft[ca]=part['depth_cal'];soft[ev]=part['depth_q']
    for name,values in [('reco_depth',np.column_stack([x,soft])),('oracle_z',np.column_stack([x,d['vertex_z_mm']]))]:
        values=values.astype('float32');rec=next(r for r in md['records'] if r['model']==name)
        model=xgb.Booster(params={'nthread':1});model.load_model(path/(name+'.ubj'));assert model.num_boosted_rounds()==400 and model.num_features()==(92 if name=='reco_depth' else 88)
        pc=model.predict(xgb.DMatrix(values[ca]));offset=float(np.mean(np.log(d['truth_E_GeV'][ca])-pc));assert offset==rec['log_offset']
        pe=np.exp(model.predict(xgb.DMatrix(values[ev])).astype(float)+offset)
        energy_roundtrip_relative_errors.append(float(np.max(abs(pe/part[name]-1))))
        np.testing.assert_allclose(pe,part[name],rtol=1e-14,atol=0)
        np.testing.assert_array_equal(part[name],joined[name][ev])
        np.testing.assert_array_equal(part['q_'+name],joined['q_'+name][ev]);assert (part['q_'+name]>0).all();np.testing.assert_allclose(part['q_'+name].sum(axis=1),1,atol=1e-10)
assert len(fits)==15 and sum(r['kind']=='depth' for r in fits)==9
for filename,names in [('ntuples/energy_ml_stage42/B_predictions.npz',['I0']),('ntuples/energy_ml_stage44/predictions.npz',['local'])]:
    with np.load(REPO/filename) as z:
        for key in ['cache_row','prior']+names+['q_'+n for n in names]:np.testing.assert_array_equal(z[key],joined[key])
with np.load(REPO/'ml/artifacts/stage45/smoke/0/predictions.npz') as z:
    sm=json.loads(str(z['metadata_json']));assert sm['smoke'] and len(sm['records'])==1 and sm['records'][0]['rounds']==20
summary=dict(events=len(rows),sources=len(set(d['group'])),formal_fits=15,depth_fits=9,energy_fits=6,smoke_fits=1,
             serialized_model_prediction_readback=True,energy_exp_roundtrip_max_relative_error=max(energy_roundtrip_relative_errors),source_OOF_no_overlap=True,cal_eval_disjoint_from_BDT_training=True,
             energy_reco_input_exact_X_plus_OOF_or_fulltrain_probabilities=True,oracle_only_true_z=True,baseline_exact_reuse=True,
             no_dropped_events=True,old_test_opened=False)
(REPO/'workbook/stage45_energy_ml/validation.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
