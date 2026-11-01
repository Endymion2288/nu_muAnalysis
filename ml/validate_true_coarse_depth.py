#!/usr/bin/env python3
"""Read back the three oracle models, calibration, roles and unchanged baselines."""
import json
import numpy as np
import xgboost as xgb
from coarse_depth import REPO, load_inputs, region_labels
from information_gap import scalar_mapping


cfg=json.loads((REPO/'ml/configs/true_coarse_depth.json').read_text())
old=json.loads((REPO/'ml/configs/coarse_depth.json').read_text())
for key in ['seed','indices','rounds','xgboost','energy_edges_GeV','regions_mm','region_names','train_role','calibration_role']:
    assert cfg[key]==old[key],key
rows,d,x=load_inputs();labels=region_labels(d['vertex_z_mm'],cfg['regions_mm'])
np.testing.assert_array_equal(np.bincount(labels,minlength=5),[62,246,568,2510,317])
onehot=np.eye(5,dtype='float32')[labels]
assert (onehot.sum(axis=1)==1).all()
values=np.column_stack([x,onehot]).astype('float32');assert values.shape==(3703,92)
energy_labels=np.searchsorted(cfg['energy_edges_GeV'],d['truth_E_GeV'],side='right')-1
out=REPO/'workbook/stage46_energy_ml'
with np.load(REPO/'ntuples/energy_ml_stage46/predictions.npz') as z: joined={k:z[k] for k in z.files}
for key in ['run','eventID','group','component','reco_p_GeV','truth_E_GeV','y_lepton','vertex_z_mm','primary_kinematic_parent_proxy']:
    np.testing.assert_array_equal(joined[key],d[key])
np.testing.assert_array_equal(joined['cache_row'],rows)
records=[];process=[];energy_diff=[];prob_diff=[];roles=[]
for f in range(3):
    path=REPO/f'ml/artifacts/stage46/formal/{f}'
    with np.load(path/'predictions.npz') as z: part={k:z[k] for k in z.files}
    md=json.loads(str(part['metadata_json']));assert md['config']==cfg and md['fold']==f and not md['smoke']
    assert len(md['records'])==1;rec=md['records'][0];records.append(rec)
    process.append({k:md[k] for k in ['fold','wall_s','cpu_s','peak_rss_MiB','xgboost_version','numpy_version']})
    tr=np.flatnonzero(d['fold']==(f+1)%3);ca=np.flatnonzero(d['fold']==(f+2)%3);ev=np.flatnonzero(d['fold']==f)
    for left,right in [(tr,ca),(tr,ev),(ca,ev)]: assert not set(d['group'][left])&set(d['group'][right])
    for key,ids,role in [('train_cache_row',tr,'train'),('cal_cache_row',ca,'calibration'),('cache_row',ev,'evaluation')]:
        np.testing.assert_array_equal(part[key],rows[ids]);assert rec[role+'_sources']==sorted(set(d['group'][ids]))
        roles.append(dict(fold=f,role=role,N=len(ids),sources=len(set(d['group'][ids])),region_N=np.bincount(labels[ids],minlength=5).tolist()))
    model=xgb.Booster(params={'nthread':1});model.load_model(path/'oracle_region.ubj')
    assert model.num_boosted_rounds()==rec['rounds']==400 and model.num_features()==rec['columns']==92
    cal=model.predict(xgb.DMatrix(values[ca]));pred=model.predict(xgb.DMatrix(values[ev]))
    offset=float(np.mean(np.log(d['truth_E_GeV'][ca])-cal));assert offset==rec['log_offset']
    energy=np.exp(pred.astype(float)+offset);energy_diff.append(float(np.max(abs(energy/part['oracle_region']-1))))
    np.testing.assert_allclose(energy,part['oracle_region'],rtol=1e-14,atol=0)
    prior=np.bincount(energy_labels[ca],minlength=6)/len(ca)
    np.testing.assert_array_equal(prior,part['prior'])
    q,it=scalar_mapping(cal.astype(float)+offset,energy_labels[ca],pred.astype(float)+offset,prior)
    assert it==rec['mapping_iterations'];prob_diff.append(float(np.max(abs(q-part['q_oracle_region']))))
    np.testing.assert_allclose(q,part['q_oracle_region'],rtol=1e-12,atol=1e-14)
    for key in ['oracle_region','q_oracle_region']: np.testing.assert_array_equal(joined[key][ev],part[key])
    np.testing.assert_array_equal(joined['prior'][ev],np.tile(prior,(len(ev),1)))
with np.load(REPO/'ntuples/energy_ml_stage45/predictions.npz') as z:
    for key in z.files: np.testing.assert_array_equal(z[key],joined[key])
formal=list((REPO/'ml/artifacts/stage46/formal').glob('*/*.ubj'))
smoke=list((REPO/'ml/artifacts/stage46/smoke').glob('*/*.ubj'))
assert len(formal)==3 and len(smoke)==1
with np.load(REPO/'ml/artifacts/stage46/smoke/0/predictions.npz') as z: sm=json.loads(str(z['metadata_json']))
assert sm['smoke'] and len(sm['records'])==1 and sm['records'][0]['rounds']==20
(out/'smoke_training.json').write_text(json.dumps(sm,indent=2)+'\n')
(out/'process_resources.json').write_text(json.dumps(process,indent=2)+'\n')
(out/'role_support.json').write_text(json.dumps(roles,indent=2)+'\n')
summary=dict(events=len(rows),sources=len(set(d['group'])),formal_fits=3,smoke_fits=1,depth_fits=0,
             serialized_model_prediction_readback=True,scalar_mapping_recomputed=True,
             energy_roundtrip_max_relative_error=max(energy_diff),scalar_mapping_max_absolute_error=max(prob_diff),
             source_role_disjoint=True,calibration_independent_of_BDT_training=True,
             X87_exact_reuse=True,oracle_only_true_region_onehot=True,baseline_exact_reuse=True,
             no_dropped_events=True,old_test_opened=False)
(out/'validation.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
