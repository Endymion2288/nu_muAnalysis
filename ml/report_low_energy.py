#!/usr/bin/env python3
"""Paired low-energy metrics, keeping truth energy and reco momentum separate."""
import csv,json,resource,time
from pathlib import Path
import numpy as np
import xgboost as xgb
from train_bdt import write_table

repo=Path(__file__).resolve().parents[1];cache=repo/'ntuples/energy_ml_stage55';out=repo/'workbook/stage55_energy_ml'
cfg=json.loads((repo/'ml/configs/low_energy.json').read_text())


def metrics(logy,pred,w=None):
 w=np.ones(len(logy)) if w is None else w
 good=w>0;logy=logy[good];pred=pred[good];w=w[good]
 if w.sum()==0:return dict(log_RMSE=np.nan,mean_bias_pct=np.nan,median_bias_pct=np.nan,R68_pct=np.nan,relative_RMS_pct=np.nan,tail50_pct=np.nan,tail100_pct=np.nan)
 delta=pred-logy;relative=np.expm1(delta)
 def quantile(q):
  # Exact repeat-frequency quantile for integer source bootstrap weights.
  order=np.argsort(relative);v=relative[order];c=np.cumsum(w[order]);pos=q*(c[-1]-1)
  lo=np.searchsorted(c,np.floor(pos),side='right');hi=np.searchsorted(c,np.ceil(pos),side='right')
  return v[lo]+(pos-np.floor(pos))*(v[hi]-v[lo])
 return dict(log_RMSE=float(np.sqrt(np.average(delta**2,weights=w))),mean_bias_pct=float(100*np.average(relative,weights=w)),median_bias_pct=float(100*quantile(.5)),R68_pct=float(50*(quantile(.84)-quantile(.16))),relative_RMS_pct=float(100*np.sqrt(np.average(relative**2,weights=w))),tail50_pct=float(100*np.average(abs(relative)>.5,weights=w)),tail100_pct=float(100*np.average(abs(relative)>1,weights=w)))


def main():
 tick,cpu=time.perf_counter(),time.process_time()
 with np.load(cache/'dataset.npz') as z:d={k:z[k] for k in z.files if k!='metadata_json'}
 ev=np.flatnonzero(d['partition']=='validation');cal=np.flatnonzero(d['cal_eligible'])
 logy=np.log(d['truth_E_GeV'][ev]);ref=np.log(d['reco_p_GeV'][ev]/.8)
 logs=dict(mu_p=np.log(d['reco_p_GeV'][ev]),mu_p_over0p8=ref)
 records=[];offsets={};raw={}
 archived=None;archived_metadata={}
 if (cache/'seed_predictions.npz').exists():
  with np.load(cache/'seed_predictions.npz') as z:archived={k:z[k] for k in z.files}
  np.testing.assert_array_equal(archived['eval_row'],ev);np.testing.assert_array_equal(archived['cal_row'],cal)
  archived_metadata={(m['model'],m['seed']):m for m in json.loads((out/'training_metadata.json').read_text())}
 for name in cfg['candidates']:
  seeds=[];calseeds=[]
  for seed in cfg['seed_indices']:
   path=repo/f'ml/artifacts/stage55/{name}/{seed}/predictions.npz'
   if path.exists():
    with np.load(path) as z:
     md=json.loads(str(z['metadata_json']));records.append(md)
     np.testing.assert_array_equal(z['eval_row'],ev);np.testing.assert_array_equal(z['cal_row'],cal)
     seeds.append(z['eval_raw_log']);calseeds.append(z['cal_raw_log'])
   else:
    j=list(archived['model_names']).index(name);k=cfg['seed_indices'].index(seed)
    records.append(archived_metadata[(name,seed)])
    seeds.append(archived['eval_raw_log'][j,k]);calseeds.append(archived['cal_raw_log'][j,k])
  raw[name]=np.mean(seeds,axis=0)
  offsets[name]=float(np.mean(np.log(d['truth_E_GeV'][cal])-np.mean(calseeds,axis=0)))
  logs[name]=raw[name]+offsets[name]
 # Original F6 is fixed; old global offset and new common-cohort offset both shown.
 frozen={};fcal={}
 for seed in range(3):
  model=xgb.Booster(params={'nthread':1});model.load_model(repo/f'ml/artifacts/stage31/seed_{seed}/nu_F6.ubj')
  frozen[seed]=model.inplace_predict(d['x'][ev],iteration_range=(0,model.best_iteration+1)).astype(float)
  fcal[seed]=model.inplace_predict(d['x'][cal],iteration_range=(0,model.best_iteration+1)).astype(float)
 raw['frozen_F6']=np.mean(list(frozen.values()),axis=0)
 # Verify each historical seed on its exact original validation identities.
 oldmask=d['nominal'][ev]&(d['reco_pz_GeV'][ev]>100)&(d['truth_pz_GeV'][ev]>100)
 for seed in range(3):
  with np.load(repo/f'ml/artifacts/stage31/seed_{seed}/predictions.npz') as z:
   lookup={tuple(k):i for i,k in enumerate(zip(z['run'],z['eventID']))}
   order=np.array([lookup[k] for k in zip(d['run'][ev][oldmask],d['eventID'][ev][oldmask])])
   np.testing.assert_array_equal(np.exp(frozen[seed][oldmask].astype('float32')),z['nu_F6'][order])
 offsets['frozen_F6_common']=float(np.mean(np.log(d['truth_E_GeV'][cal])-np.mean(list(fcal.values()),axis=0)))
 old_offset=json.loads((repo/'workbook/stage34_energy_ml/calibration_state.json').read_text())['offset_log']['F6']
 logs['frozen_F6_oldcal']=raw['frozen_F6']+old_offset
 logs['frozen_F6_common']=raw['frozen_F6']+offsets['frozen_F6_common']
 # Exact old validation prediction reproduction; complete known >100 support.
 with np.load(repo/'ntuples/energy_ml_stage31/validation_tracks.npz') as z:
  available=list(z.files)
 # Previous stage34 validation has all model outputs and was explicitly exposed.
 old_path=repo/'ntuples/energy_ml_stage34/validation.npz'
 reproduced='three historical seed energy predictions exactly reproduced on original validation'
 if old_path.exists():
  with np.load(old_path) as z:
   lookup={tuple(k):i for i,k in enumerate(zip(z['run'],z['eventID']))}
   mask=d['nominal'][ev]&(d['reco_pz_GeV'][ev]>100)&(d['truth_pz_GeV'][ev]>100)
   order=np.array([lookup[k] for k in zip(d['run'][ev][mask],d['eventID'][ev][mask])])
   expected=np.mean([z[f'F6_log_seed{s}'][order].astype(float) for s in range(3)],axis=0)
   np.testing.assert_array_equal(raw['frozen_F6'][mask],expected);reproduced=True
 np.savez_compressed(cache/'predictions.npz',eval_row=ev,**logs,**{'raw_'+k:v for k,v in raw.items()})
 write_table(out/'training_resources.tsv',[{k:r[k] for k in ['model','seed','train_N','weight_sum','weight_Neff','cal_N','eval_N','fit_wall_s','wall_s','cpu_s','rss_MiB','model_reload_exact']} for r in records])
 (out/'offsets.json').write_text(json.dumps(dict(common_offsets=offsets,frozen_original_offset=old_offset),indent=2)+'\n')
 masks={'all':np.ones(len(ev),bool),'reco_p50_100':(d['reco_p_GeV'][ev]>=50)&(d['reco_p_GeV'][ev]<100),'reco_p100_250':(d['reco_p_GeV'][ev]>=100)&(d['reco_p_GeV'][ev]<250),'reco_p250_1000':(d['reco_p_GeV'][ev]>=250)&(d['reco_p_GeV'][ev]<1000),'reco_p100_1000':(d['reco_p_GeV'][ev]>=100)&(d['reco_p_GeV'][ev]<1000),'reco_p1000_inf':d['reco_p_GeV'][ev]>=1000,'confirmed':d['confirmed'][ev],'unconfirmed':~d['confirmed'][ev],'y0.8_inf':d['y_lepton'][ev]>=.8,'E6400_inf':d['truth_E_GeV'][ev]>=6400,'primary_invalid':~d['primary_valid'][ev],'y_nonfinite':~np.isfinite(d['y_lepton'][ev])}
 for lo,hi in [(50,100),(100,200)]:masks[f'E{lo}_{hi}']=(d['truth_E_GeV'][ev]>=lo)&(d['truth_E_GeV'][ev]<hi)
 for variable,edges,label in [('truth_E_GeV',cfg['energy_edges_GeV'],'E'),('reco_p_GeV',cfg['momentum_edges_GeV'],'p')]:
  for lo,hi in zip(edges[:-1],edges[1:]):masks[f'{label}{lo}_{hi}']=(d[variable][ev]>=lo)&(d[variable][ev]<hi)
 for lo,hi in [(50,100),(100,250),(250,1000)]:
  masks[f'confirmed_true_p{lo}_{hi}']=d['confirmed'][ev]&(d['primary_p_GeV'][ev]>=lo)&(d['primary_p_GeV'][ev]<hi)
 comparisons=[(name,'mu_p_over0p8') for name in logs if name not in ['mu_p','mu_p_over0p8']]+[('nominal50','nominal100'),('mixture50','nominal50'),('residual50','mixture50'),('matched_flux50','nominal50'),('matched_flux50','mixture50')]
 rng=np.random.default_rng(cfg['bootstrap_seed']);groups=np.unique(d['group'][ev][d['nominal'][ev]])
 weights=[]
 for _ in range(cfg['bootstrap_replicates']):
  counts={}
  for comp in ['pi','k','charm']:
   g=[s for s in groups if s.startswith(comp+':')];chosen=rng.choice(g,len(g),replace=True)
   counts.update({s:int(np.sum(chosen==s)) for s in g})
  weights.append(np.array([counts.get(g,0) for g in d['group'][ev]]))
 rows=[];paired=[]
 for sample,sm in [('nominal',d['nominal'][ev]),('alternative',~d['nominal'][ev])]:
  for stratum,mm in masks.items():
   m=sm&mm;N=int(m.sum())
   if not N:continue
   n_groups=len(set(d['group'][ev][m]));n_sources=len(set(d['source'][ev][m]))
   for name,pred in logs.items():
    values=metrics(logy[m],pred[m]);rows.append(dict(sample=sample,stratum=stratum,model=name,N=N,groups=n_groups,sources=n_sources,**values))
   for name,reference in comparisons:
    a=metrics(logy[m],logs[name][m]);b=metrics(logy[m],logs[reference][m]);gain=100*(1-a['log_RMSE']/b['log_RMSE'])
    boot=[]
    if sample=='nominal' and n_groups>=3:
     for w in weights:
      ww=w[m]
      if ww.sum():
       aa=np.sqrt(np.average((logs[name][m]-logy[m])**2,weights=ww));bb=np.sqrt(np.average((logs[reference][m]-logy[m])**2,weights=ww))
       boot.append(100*(1-aa/bb))
    low,high=np.quantile(boot,[.025,.975]) if boot else [np.nan,np.nan]
    paired.append(dict(sample=sample,stratum=stratum,model=name,reference=reference,N=N,groups=n_groups,gain_pct=gain,gain_low95_pct=low,gain_high95_pct=high,bootstrap_valid=len(boot),interval_scope='fixed models and calibration; component-stratified paired source bootstrap' if boot else 'not measured: insufficient generation-range group support; alternative has one per component'))
 # Raw risks separately prevent a global scale offset from hiding conditional bias.
 rawrows=[]
 for sample,sm in [('nominal',d['nominal'][ev]),('alternative',~d['nominal'][ev])]:
  for stratum,mm in masks.items():
   m=sm&mm
   if m.any():
    for name,pred in raw.items():rawrows.append(dict(sample=sample,stratum=stratum,model=name,N=int(m.sum()),**metrics(logy[m],pred[m])))
 write_table(out/'metrics.tsv',rows);write_table(out/'paired.tsv',paired);write_table(out/'raw_metrics.tsv',rawrows)
 # Component, run and matched/migration support, no residual selection.
 details=[]
 for name in ['mixture50','residual50','nominal50','frozen_F6_oldcal','mu_p_over0p8']:
  for run in np.unique(d['run'][ev]):
   for stratum in ['reco_p50_100','E50_100','E100_200','E50_75','E75_100','reco_p100_250']:
    m=(d['run'][ev]==run)&masks[stratum]
    if m.any():details.append(dict(run=int(run),stratum=stratum,model=name,N=int(m.sum()),**metrics(logy[m],logs[name][m])))
 write_table(out/'run_metrics.tsv',details)
 # Describe the physical mixture behind reco-low-p versus true-low-energy
 # risks; these truth subdivisions never enter the deployed model choice.
 composition=[]
 for sample,sm in [('nominal',d['nominal'][ev]),('alternative',~d['nominal'][ev])]:
  for plo,phi in [(50,100),(100,250)]:
   for elo,ehi in [(50,100),(100,200),(200,400),(400,1e9)]:
    m=sm&(d['reco_p_GeV'][ev]>=plo)&(d['reco_p_GeV'][ev]<phi)&(d['truth_E_GeV'][ev]>=elo)&(d['truth_E_GeV'][ev]<ehi)
    if not m.any():continue
    x=d['x'][ev][m];y=d['y_lepton'][ev][m]
    composition.append(dict(sample=sample,reco_p_low_GeV=plo,reco_p_high_GeV=phi,truth_E_low_GeV=elo,truth_E_high_GeV=ehi,N=int(m.sum()),confirmed_N=int(d['confirmed'][ev][m].sum()),y_ge0p8_N=int((y>=.8).sum()),median_y=float(np.nanmedian(y)),median_clusters=float(np.nanmedian(x[:,17:21].sum(1))),median_spacepoints=float(np.nanmedian(x[:,21])),median_segments=float(np.nanmedian(x[:,22])),median_Timing_total_pC=float(np.nanmedian(x[:,29:33].sum(1))),median_calo_EM_GeV=float(np.nanmedian(x[:,41]))))
 write_table(out/'low_energy_composition.tsv',composition)
 summary=dict(formal_fits=len(records),seeds_per_candidate=3,fit_wall_sum_s=sum(r['fit_wall_s'] for r in records),frozen_validation_reproduced=reproduced,wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,intervals='conditional on fitted models and common calibration; do not include model retraining, calibration uncertainty or detector/flux systematics',alternative_support='16 runs but only 3 conservative generation-range groups; descriptive transfer check, no source CI claimed')
 (out/'report_resources.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)

if __name__=='__main__':main()
