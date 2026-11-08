"""Batch-only model reload, independent row-space uncertainty and extraction audit."""
import csv,math
import xgboost as xgb
from stage186_common import *
from stage119_curve_common import LAYERS
if __name__=='__main__':
 assert json.loads((OUT/'input_controls.json').read_text())['passed']
 d,x,labels=inputs();active=d['role']>0;protocol=json.loads((ROOT/'workbook/stage87_energy_ml/protocol.json').read_text())['baseline'];allp={};reloads=0
 for arm in ['A','R','I']:
  target=xgb.DMatrix(x[arm][active],feature_names=labels[arm],nthread=1);pred=[]
  for seed in protocol['seeds']:
   b=xgb.Booster(params={'nthread':1});b.load_model(ART/f'energy_{arm}_{seed}.ubj');pred.append(b.predict(target).astype(float));reloads+=1
  raw=np.full(len(active),np.nan);raw[active]=np.mean(pred,axis=0);saved=load(ART/f'energy_{arm}_prediction.npz');np.testing.assert_array_equal(raw,saved['raw'])
  cal=d['role']==2;_,gid,cnt=np.unique(d['incoming'][cal],axis=0,return_inverse=True,return_counts=True);w=1/cnt[gid]
  offset=float(np.average(np.log(d['truth_E_GeV'][cal])-raw[cal],weights=w));np.testing.assert_array_equal(raw+offset,saved['cal']);assert np.isnan(saved['cal'][~active]).all();allp[arm]=saved['cal']
 saved=load(ART/'energy_predictions.npz')
 for k in ['direct_cal','traditional']:allp[k]=saved[k]
 old=load(ROOT/'ml/artifacts/stage87/predictions.npz');baseline=np.full(len(active),np.nan);baseline[old['row']]=old['direct_cal'];np.testing.assert_array_equal(baseline,allp['direct_cal'])
 np.testing.assert_array_equal(np.where(active,np.log(d['pz']/.8),np.nan),allp['traditional'])
 # Independent exact rejoin against pre-admission train-only pilot in every source.
 pilot=load(CACHE/'pilot_0.npz');rows={int(r):i for i,r in enumerate(pilot['row'])};joined=0
 cohort=load(CACHE/'cohort.npz');np.testing.assert_array_equal(cohort['row'],np.arange(len(active)));np.testing.assert_array_equal(cohort['role'],d['role'])
 for g in range(35):
  a=load(CACHE/f'full_{g}.npz')
  for key in set(cohort)-{'row','role'}:np.testing.assert_array_equal(cohort[key][a['row']],a[key])
  take=[(j,rows[int(r)]) for j,r in enumerate(a['row']) if int(r) in rows]
  if not take:continue
  ia,ib=map(np.array,zip(*take))
  for k in pilot:np.testing.assert_array_equal(a[k][ia],pilot[k][ib])
  joined+=len(ia)
 assert joined==len(rows)
 metrics=list(csv.DictReader((OUT/'energy_metrics.tsv').open(),delimiter='\t'));pairs=list(csv.DictReader((OUT/'energy_paired.tsv').open(),delimiter='\t'));checks=[];maxerr=0.;maxinterval=0.
 for role in [2,3]:
  ix=np.flatnonzero(d['role']==role);incoming=d['incoming'][ix];keys,first,gid,cnt=np.unique(incoming,axis=0,return_index=True,return_inverse=True,return_counts=True);w=1/cnt[gid]
  rng=np.random.default_rng(20261108186+role);draw=np.zeros((500,len(keys)),np.int16)
  for component in sorted(set(d['component'][ix[first]])):
   u=np.flatnonzero(d['component'][ix[first]]==component);draw[:,u]=rng.multinomial(len(u),np.full(len(u),1/len(u)),size=500)
  # Build the eight gates independently of production mask helper.
  E=d['truth_E_GeV'][ix];pz=d['pz'][ix];y=d['y_lepton'][ix];physical=d['primary_valid'][ix].astype(bool)&np.isfinite(y)&(y>=0)&(y<1)
  masks=dict(E50_100=(E>=50)&(E<100),E100_200=(E>=100)&(E<200),all=np.ones(len(ix),bool),E200_inf=E>=200,pz50_100=(pz>=50)&(pz<100),pz50_100_trueE200=(pz>=50)&(pz<100)&(E>=200),high_y=physical&(y>=.8),unconfirmed=~d['confirmed'][ix].astype(bool))
  for layer in LAYERS:
   mask=masks[layer];select=ix[mask];ww=w[mask];sw=draw[:,gid[mask]]*ww[None,:];den=sw.sum(1);good=den>0;names=list(allp)
   err=np.column_stack([allp[k][select]-np.log(d['truth_E_GeV'][select]) for k in names]);squared=sw@(err**2);relative=np.expm1(err)
   for j,k in enumerate(names):
    row=next(r for r in metrics if int(r['role'])==role and r['stratum']==layer and r['model']==k);norm=math.fsum(map(float,ww));rmse=math.sqrt(math.fsum(float(v)*float(e)**2 for v,e in zip(ww,err[:,j]))/norm);delta=abs(rmse-float(row['log_RMSE']))
    for key,flag in [('tail50_pct',abs(relative[:,j])>.5),('positive_tail50_pct',relative[:,j]>.5),('negative_tail50_pct',relative[:,j]<-.5)]:
     delta=max(delta,abs(100*math.fsum(float(v)*int(f) for v,f in zip(ww,flag))/norm-float(row[key])))
    assert delta<1e-10;maxerr=max(maxerr,delta)
   for row in [r for r in pairs if int(r['role'])==role and r['stratum']==layer]:
    j,k=names.index(row['candidate']),names.index(row['reference']);ok=good&(squared[:,k]>0);values=np.sqrt(squared[ok,j]/squared[ok,k]);bounds=np.quantile(values,[.025,.975]);delta=max(abs(bounds-np.array([float(row['low95']),float(row['high95'])])))
    for sign,flag in [('total',abs(relative)>.5),('positive',relative>.5),('negative',relative<-.5)]:
     values=100*(sw[ok]@(flag[:,j].astype(float)-flag[:,k].astype(float)))/den[ok];bounds=np.quantile(values,[.025,.975]);delta=max(delta,max(abs(bounds-np.array([float(row[sign+'_tail_low95_pp']),float(row[sign+'_tail_high95_pp'])]))))
    assert delta<1e-10;maxinterval=max(maxinterval,delta);checks.append(dict(role=role,stratum=layer,candidate=row['candidate'],reference=row['reference'],row_space_interval_max_delta=float(delta)))
 # Independently recover every baseline-refit closure from exact rational sums.
 from fractions import Fraction
 rounding=[]
 for g in range(35):
  summary=json.loads((OUT/f'full_{g}_summary.json').read_text())
  for r in summary.get('baseline_rounding_records',[]):
   assert r['baseline_ULPs']<=1
   for prefix in ['old','new']:
    exact=Fraction.from_float(r[prefix+'_baseline_mV'])*r['sample_N']-Fraction.from_float(r['ADC_mV_per_code'])*r['ADC_sum_codes']
    q=np.float32(np.float32(float(2*exact))/np.float32(50));np.testing.assert_array_equal(q,np.float32(r[prefix+'_raw_pC']))
   rounding.append(r)
 write('baseline_rounding_validation.json',dict(passed=True,records_N=len(rounding),all_exact_rational_signed_integral_closures=True,records=rounding,ideal_tolerance_unchanged=True,representation_unchanged=True,parents_removed=0))
 # Frozen Stage137 expansion requires both low bins, both cal/test, point <=.95 and upper<1, with all tails.
 gates=list(csv.DictReader((OUT/'energy_gates.tsv').open(),delimiter='\t'));expansion={}
 for candidate,reference in [('I','R'),('I','A'),('R','A')]:
  rows=[r for r in pairs if int(r['role']) in [2,3] and r['stratum'] in LAYERS[:2] and r['candidate']==candidate and r['reference']==reference]
  tailrows=[r for r in pairs if int(r['role']) in [2,3] and r['stratum'] in LAYERS and r['candidate']==candidate and r['reference']==reference]
  expansion[candidate+'/'+reference]=len(rows)==4 and all(float(r['RMSE_ratio'])<=.95 and float(r['high95'])<1 for r in rows) and all(float(r[s+'_tail_high95_pp'])<=2 for r in tailrows for s in ['total','positive','negative'])
 write('independent_validation.json',dict(passed=True,reloaded_models=reloads,all_active_prediction_and_cal_offset_exact=True,Stage87_baseline_exact=True,cohort_cache_all_full_scalars_exact=True,pilot_parents_all_fields_exact=joined,scalar_metric_max_delta=maxerr,independent_row_space_bootstrap_checks=len(checks),interval_max_delta=maxinterval,interval_checks=checks,expansion_gate=expansion,roles_original=True,quarantine_predictions=0,reserved_predictions=0,overall_complete=False,promotion=False))
 print('INDEPENDENT AUDIT PASSED',expansion,flush=True)

 import subprocess,sys
 assert subprocess.run([sys.executable,"ml/stage186_resources.py"]).returncode==0

 assert subprocess.run([sys.executable,"ml/stage186_decisions.py"]).returncode==0
