#!/usr/bin/env python3
"""Independent persisted-model predictions, source roles and weighted metric QA."""
import csv,json,resource,time
from pathlib import Path
import numpy as np
import xgboost as xgb
from report_low_energy import metrics

repo=Path(__file__).resolve().parents[1];cache=repo/'ntuples/energy_ml_stage55';out=repo/'workbook/stage55_energy_ml'
tick,cpu=time.perf_counter(),time.process_time();cfg=json.loads((repo/'ml/configs/low_energy.json').read_text())
with np.load(cache/'dataset.npz') as z:d={k:z[k] for k in z.files if k!='metadata_json'}
with np.load(cache/'predictions.npz') as z:pred={k:z[k] for k in z.files}
ev=np.flatnonzero(d['partition']=='validation');cal=np.flatnonzero(d['cal_eligible']);np.testing.assert_array_equal(ev,pred['eval_row'])
keys=[tuple(v) for v in d['incoming']]
assert not ({keys[i] for i in np.flatnonzero(d['train_eligible'])}&{keys[i] for i in np.flatnonzero(d['partition']!='train')})
assert not ({keys[i] for i in cal}&{keys[i] for i in ev})
assert not (set(d['group'][d['train_eligible']])&set(d['group'][ev]) or set(d['group'][d['train_eligible']])&set(d['group'][cal]))
offsets=json.loads((out/'offsets.json').read_text())['common_offsets'];checks=[]
archived=None
if (cache/'seed_predictions.npz').exists():
 with np.load(cache/'seed_predictions.npz') as z:archived={k:z[k] for k in z.files}
for name in cfg['candidates']:
 cols=list(range(65));parts=[];cp=[];max_seed_difference=0.
 for seed in cfg['seed_indices']:
  b=xgb.Booster(params={'nthread':1});b.load_model(repo/f'ml/artifacts/stage55/{name}/{seed}/model.ubj')
  p=b.inplace_predict(d['x'][ev][:,cols]).astype(float);c=b.inplace_predict(d['x'][cal][:,cols]).astype(float)
  if name=='residual50':p+=np.log(d['reco_p_GeV'][ev]/.8);c+=np.log(d['reco_p_GeV'][cal]/.8)
  path=repo/f'ml/artifacts/stage55/{name}/{seed}/predictions.npz'
  if path.exists():
   with np.load(path) as z:sp=z['eval_raw_log'];sc=z['cal_raw_log']
  else:
   j=list(archived['model_names']).index(name);k=cfg['seed_indices'].index(seed)
   sp=archived['eval_raw_log'][j,k];sc=archived['cal_raw_log'][j,k]
  for actual,expected in [(p,sp),(c,sc)]:
   max_seed_difference=max(max_seed_difference,float(np.max(np.abs(actual-expected))))
   if name=='residual50':np.testing.assert_allclose(actual,expected,rtol=0,atol=8e-15)
   else:np.testing.assert_array_equal(actual,expected)
  parts.append(p);cp.append(c)
 p=np.mean(parts,axis=0);offset=float(np.mean(np.log(d['truth_E_GeV'][cal])-np.mean(cp,axis=0)))
 raw_difference=float(np.max(abs(pred['raw_'+name]-p)));offset_difference=abs(offsets[name]-offset)
 calibrated_difference=float(np.max(abs(pred[name]-(p+offset))))
 if name=='residual50':
  # The remote worker and lxplus libm log differ by a few float64 ulps.
  # Tree predictions for all other candidates must still reproduce exactly.
  np.testing.assert_allclose(pred['raw_'+name],p,rtol=0,atol=8e-15)
  np.testing.assert_allclose(offsets[name],offset,rtol=0,atol=8e-15)
  np.testing.assert_allclose(pred[name],p+offset,rtol=0,atol=8e-15)
 else:
  np.testing.assert_array_equal(pred['raw_'+name],p);assert offsets[name]==offset
  np.testing.assert_array_equal(pred[name],p+offset)
 assert np.isfinite(p).all()
 checks.append(dict(model=name,seed_models=3,max_seed_log_difference=max_seed_difference,raw_prediction_exact=raw_difference==0,offset_exact=offset_difference==0,calibrated_prediction_exact=calibrated_difference==0,max_raw_log_difference=raw_difference,offset_difference=offset_difference,max_calibrated_log_difference=calibrated_difference,allowed_absolute_log_difference=8e-15 if name=='residual50' else 0))
# Validate all metric outputs against explicit repeated events, rather than the
# cumulative-frequency quantile implementation, on fixed integer weights.
rng=np.random.default_rng(2026110256);metric_error=0.
for _ in range(12):
 take=rng.choice(len(ev),80,replace=False);w=rng.integers(0,5,len(take));a=metrics(np.log(d['truth_E_GeV'][ev][take]),pred['mixture50'][take],w)
 yy=np.repeat(np.log(d['truth_E_GeV'][ev][take]),w);pp=np.repeat(pred['mixture50'][take],w);rel=np.expm1(pp-yy);q=np.quantile(rel,[.16,.5,.84])
 b=dict(log_RMSE=np.sqrt(np.mean((pp-yy)**2)),mean_bias_pct=100*rel.mean(),median_bias_pct=100*q[1],R68_pct=50*(q[2]-q[0]),relative_RMS_pct=100*np.sqrt(np.mean(rel**2)),tail50_pct=100*np.mean(abs(rel)>.5),tail100_pct=100*np.mean(abs(rel)>1))
 for k in a:metric_error=max(metric_error,abs(a[k]-b[k]));np.testing.assert_allclose(a[k],b[k],rtol=1e-12,atol=1e-12)
result=dict(formal_fits=15,all_models_reloaded=checks,train_protected_incoming_overlap=0,cal_evaluation_incoming_overlap=0,source_role_overlap=0,metric_repeat_checks=12,metric_max_absolute_difference=metric_error,N=len(d['run']),evaluation_N=len(ev),calibration_N=len(cal),wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
(out/'validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
