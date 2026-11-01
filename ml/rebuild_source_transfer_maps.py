#!/usr/bin/env python3
"""Reconstruct only OLD calibration mappings; exactly verify all historical predictions."""
import json
import resource
import time
import joblib
import numpy as np
import xgboost as xgb
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import SplineTransformer,StandardScaler
from sklearn.linear_model import LogisticRegression
from coarse_depth import load_inputs
from source_transfer import REPO,CACHE,OUT,configuration

cfg=configuration();tick,cpu=time.perf_counter(),time.process_time();rows,d,x=load_inputs()
labels=np.searchsorted(cfg['energy_edges_GeV'],d['truth_E_GeV'],side='right')-1
states={};records=[]
for f in range(3):
    ca=d['fold']==(f+2)%3;ev=d['fold']==f;prior=np.bincount(labels[ca],minlength=6)/ca.sum()
    with np.load(CACHE/'selection.npz') as z:new_groups=set(z['group'])
    assert not new_groups&set(d['group'])
    for name,stage in [('local',44),('oracle_z',45)]:
        p=REPO/f'ml/artifacts/stage{stage}/formal/{f}'
        with np.load(p/'predictions.npz') as z:old={k:z[k] for k in z.files}
        md=json.loads(str(old['metadata_json']));rec=next(r for r in md['records'] if r['model']==name)
        np.testing.assert_array_equal(old['cache_row'],rows[ev]);np.testing.assert_array_equal(old['prior'],prior)
        values=x if name=='local' else np.column_stack([x,d['vertex_z_mm']]).astype('float32')
        model=xgb.Booster(params={'nthread':1});model.load_model(p/(name+'.ubj'))
        assert model.num_features()==(87 if name=='local' else 88) and model.num_boosted_rounds()==400
        cal=model.predict(xgb.DMatrix(values[ca]));pred=model.predict(xgb.DMatrix(values[ev]))
        offset=float(np.mean(np.log(d['truth_E_GeV'][ca])-cal));assert offset==rec['log_offset']
        energy=np.exp(pred.astype(float)+offset)
        np.testing.assert_array_equal(pred,(np.log(old[name])-offset).astype('float32'))
        np.testing.assert_allclose(energy,old[name],rtol=1e-14,atol=0)
        # Identical construction to information_gap.scalar_mapping, using its ORIGINAL calibration rows only.
        pipe=make_pipeline(SplineTransformer(n_knots=8,degree=3,knots='quantile'),StandardScaler(),LogisticRegression(C=1.,max_iter=1000,solver='lbfgs'))
        weights=prior[labels[ca]]/(np.bincount(labels[ca],minlength=6)/ca.sum())[labels[ca]]
        pipe.fit((cal.astype(float)+offset)[:,None],labels[ca],logisticregression__sample_weight=weights)
        q=pipe.predict_proba((pred.astype(float)+offset)[:,None]);np.testing.assert_allclose(q,old['q_'+name],rtol=1e-12,atol=1e-14)
        assert int(pipe[-1].n_iter_.max())==rec['mapping_iterations']
        states[(f,name)]=dict(pipe=pipe,log_offset=offset,prior=prior,model_path=str((p/(name+'.ubj')).relative_to(REPO)))
        records.append(dict(fold=f,model=name,original_calibration_N=int(ca.sum()),original_evaluation_N=int(ev.sum()),
                            original_calibration_sources=sorted(set(d['group'][ca])),original_training_sources=sorted(set(d['group'][d['fold']==(f+1)%3])),
                            log_offset=offset,raw_float32_log_prediction_exact=True,energy_max_relative_difference=float(np.max(abs(energy/old[name]-1))),probability_max_absolute_difference=float(np.max(abs(q-old['q_'+name]))),mapping_iterations=rec['mapping_iterations']))
joblib.dump(states,CACHE/'original_maps.joblib',compress=3)
loaded=joblib.load(CACHE/'original_maps.joblib');assert set(loaded)==set(states)
md=dict(old_support_events=len(rows),old_sources=len(set(d['group'])),original_mapping_reconstructions=len(records),energy_fits=0,target_calibration_fits=0,
        new_support_labels_used=False,new_source_overlap=0,records=records,wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,
        peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
(OUT/'historical_readback.json').write_text(json.dumps(md,indent=2)+'\n');print(json.dumps({k:v for k,v in md.items() if k!='records'}))
