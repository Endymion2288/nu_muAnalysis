#!/usr/bin/env python3
"""Fixed-budget support/prior/parameterization contrasts; no early stopping grid."""
import argparse,json,resource,time
from pathlib import Path
import numpy as np
import xgboost as xgb

repo=Path(__file__).resolve().parents[1]

def main():
 p=argparse.ArgumentParser();p.add_argument('--model',required=True);p.add_argument('--seed',type=int,default=0);p.add_argument('--smoke',action='store_true');p.add_argument('--smoke-input',type=Path);a=p.parse_args()
 assert a.smoke or a.smoke_input is None
 cfg=json.loads((repo/'ml/configs/low_energy.json').read_text());assert a.model in cfg['candidates']
 output=repo/f"ml/artifacts/stage55/{'smoke' if a.smoke else a.model}/{a.seed}"
 assert not (output/'model.ubj').exists(),'Do not repeat successful fit'
 tick,cpu=time.perf_counter(),time.process_time()
 with np.load(a.smoke_input or repo/'ntuples/energy_ml_stage55/dataset.npz') as z:d={k:z[k] for k in z.files if k!='metadata_json'}
 train=d['train_eligible'].copy()
 if a.model in ['nominal100','nominal50']:train &= d['nominal']
 if a.model=='nominal100':train &= (d['truth_pz_GeV']>100)&(d['reco_pz_GeV']>100)
 tr=np.flatnonzero(train); cal=np.flatnonzero(d['cal_eligible']);ev=np.flatnonzero(d['partition']=='validation')
 if a.smoke:tr=tr[:200];cal=cal[:100];ev=ev[:100]
 cols=list(range(65))
 x=d['x'][:,cols];ref=np.log(d['reco_p_GeV']/.8)
 y=np.log(d['truth_E_GeV'])-(ref if a.model=='residual50' else 0)
 params=dict(cfg['xgboost']);params['seed']=2026110255+a.seed
 weights=np.ones(len(tr));weight_cells=[]
 if a.model=='matched_flux50':
  edges=np.array(cfg['energy_edges_GeV']+[float('inf')]);bins=np.searchsorted(edges,d['truth_E_GeV'][tr],side='right')-1
  for component in ['pi','k','charm']:
   for b in np.unique(bins):
    cell=(d['component'][tr]==component)&(bins==b);n=int(cell.sum());nominal_n=int((cell&d['nominal'][tr]).sum())
    if n:weights[cell]=nominal_n/n
    weight_cells.append(dict(component=component,energy_bin=int(b),mixture_N=n,nominal_N=nominal_n,weight=nominal_n/n if n else 0))
  np.testing.assert_allclose(weights.sum(),d['nominal'][tr].sum(),rtol=1e-12)
 dm=xgb.DMatrix(x[tr],label=y[tr],weight=weights,nthread=1)
 start=time.perf_counter();model=xgb.train(params,dm,num_boost_round=20 if a.smoke else cfg['rounds'])
 fit_wall=time.perf_counter()-start
 pred={}
 for part,idx in [('cal',cal),('eval',ev)]:
  pred[part+'_raw_log']=model.inplace_predict(x[idx]).astype(float)+(ref[idx] if a.model=='residual50' else 0)
 offset=float(np.mean(np.log(d['truth_E_GeV'][cal])-pred['cal_raw_log']))
 output.mkdir(parents=True,exist_ok=True)
 model.save_model(output/'model.ubj')
 restored=xgb.Booster(params={'nthread':1});restored.load_model(output/'model.ubj')
 np.testing.assert_array_equal(model.inplace_predict(x[ev]),restored.inplace_predict(x[ev]))
 md=dict(model=a.model,seed=a.seed,smoke=a.smoke,train_N=len(tr),weight_sum=float(weights.sum()),weight_Neff=float(weights.sum()**2/np.sum(weights**2)),weight_cells=weight_cells,cal_N=len(cal),eval_N=len(ev),columns=cols,offset=offset,params=params,rounds=20 if a.smoke else cfg['rounds'],fit_wall_s=fit_wall,wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,model_reload_exact=True)
 np.savez_compressed(output/'predictions.npz',train_row=tr,cal_row=cal,eval_row=ev,**pred,metadata_json=np.array(json.dumps(md)))
 print(json.dumps(md),flush=True)

if __name__=='__main__':main()
