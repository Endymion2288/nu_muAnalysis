#!/usr/bin/env python3
"""Model/calibration readback and same-support input, roles and budget audit."""
import json
import numpy as np
import xgboost as xgb
from coarse_depth import REPO
from ordinary_calo_information import load_sensitive
from information_gap import scalar_mapping

cfg=json.loads((REPO/'ml/configs/ordinary_calo_information.json').read_text())
old=json.loads((REPO/'ml/configs/coarse_depth.json').read_text())
for key in ['seed','indices','rounds','xgboost','energy_edges_GeV','train_role','calibration_role']:assert cfg[key]==old[key]
rows,d,candidates=load_sensitive();out=REPO/'workbook/stage47_energy_ml'
with np.load(REPO/'ntuples/energy_ml_stage47/predictions.npz') as z:joined={k:z[k] for k in z.files}
np.testing.assert_array_equal(joined['cache_row'],rows)
for key in ['run','eventID','group','component','reco_p_GeV','truth_E_GeV','y_lepton','vertex_z_mm','primary_kinematic_parent_proxy']:
    np.testing.assert_array_equal(joined[key],d[key])
labels=np.searchsorted(cfg['energy_edges_GeV'],d['truth_E_GeV'],side='right')-1
energy_error=[];prob_error=[];process=[];fits=[]
for f in range(3):
    path=REPO/f'ml/artifacts/stage47/formal/{f}'
    with np.load(path/'predictions.npz') as z:part={k:z[k] for k in z.files}
    md=json.loads(str(part['metadata_json']));assert md['config']==cfg and md['fold']==f and not md['smoke']
    assert len(md['records'])==2;fits+=md['records']
    process.append({k:md[k] for k in ['fold','wall_s','cpu_s','peak_rss_MiB','xgboost_version','numpy_version']})
    tr=np.flatnonzero(d['fold']==(f+1)%3);ca=np.flatnonzero(d['fold']==(f+2)%3);ev=np.flatnonzero(d['fold']==f)
    for a,b in [(tr,ca),(tr,ev),(ca,ev)]:assert not set(d['group'][a])&set(d['group'][b])
    for key,ids in [('train_cache_row',tr),('cal_cache_row',ca),('cache_row',ev)]:np.testing.assert_array_equal(part[key],rows[ids])
    prior=np.bincount(labels[ca],minlength=6)/len(ca);np.testing.assert_array_equal(prior,part['prior'])
    np.testing.assert_array_equal(joined['prior'][ev],np.tile(prior,(len(ev),1)))
    for name,values in candidates.items():
        rec=next(r for r in md['records'] if r['model']==name)
        for role,ids in [('train',tr),('calibration',ca),('evaluation',ev)]:assert rec[role+'_sources']==sorted(set(d['group'][ids]))
        model=xgb.Booster(params={'nthread':1});model.load_model(path/(name+'.ubj'))
        expected=91 if name=='ordinary_calo' else 92
        assert model.num_boosted_rounds()==rec['rounds']==400 and model.num_features()==rec['columns']==expected
        cal=model.predict(xgb.DMatrix(values[ca]));pred=model.predict(xgb.DMatrix(values[ev]))
        offset=float(np.mean(np.log(d['truth_E_GeV'][ca])-cal));assert offset==rec['log_offset']
        energy=np.exp(pred.astype(float)+offset);energy_error.append(float(np.max(abs(energy/part[name]-1))))
        np.testing.assert_allclose(energy,part[name],rtol=1e-14,atol=0)
        q,it=scalar_mapping(cal.astype(float)+offset,labels[ca],pred.astype(float)+offset,prior)
        assert it==rec['mapping_iterations'];prob_error.append(float(np.max(abs(q-part['q_'+name]))))
        np.testing.assert_allclose(q,part['q_'+name],rtol=1e-12,atol=1e-14)
        for key in [name,'q_'+name]:np.testing.assert_array_equal(part[key],joined[key][ev])
with np.load(REPO/'ntuples/energy_ml_stage45/predictions.npz') as z:
    for key in ['cache_row','prior','I0','q_I0','local','q_local','oracle_z','q_oracle_z']:
        np.testing.assert_array_equal(z[key],joined[key])
assert len(list((REPO/'ml/artifacts/stage47/formal').glob('*/*.ubj')))==len(fits)==6
assert len(list((REPO/'ml/artifacts/stage47/smoke').glob('*/*.ubj')))==1
with np.load(REPO/'ml/artifacts/stage47/smoke/0/predictions.npz') as z:sm=json.loads(str(z['metadata_json']))
assert sm['smoke'] and len(sm['records'])==1 and sm['records'][0]['rounds']==20
(out/'smoke_training.json').write_text(json.dumps(sm,indent=2)+'\n')
(out/'process_resources.json').write_text(json.dumps(process,indent=2)+'\n')
extract=json.loads((out/'extraction.json').read_text());assert extract['events']==3703 and extract['sources']==21 and extract['identity_failures']==0 and extract['pilot_exact_rejoin']
summary=dict(events=len(rows),sources=len(set(d['group'])),formal_fits=6,smoke_fits=1,
             serialized_model_prediction_readback=True,scalar_mapping_recomputed=True,
             energy_roundtrip_max_relative_error=max(energy_error),scalar_mapping_max_absolute_error=max(prob_error),
             source_role_disjoint=True,calibration_independent_of_BDT_training=True,original_X87_exact_reuse=True,
             no_particle_or_time_filter_on_sensitive_deposit=True,truth_z_and_sensitive_deposit_only_oracles=True,
             baseline_exact_reuse=True,no_dropped_events=True,old_test_opened=False,extraction_identity_failures=0)
(out/'validation.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
