#!/usr/bin/env python3
"""Fixed L5 models on identical complete source roles; no truth input or scan."""
import argparse
import json
import resource
import time
import numpy as np
import xgboost as xgb
from segment_information import REPO,CACHE,configuration
from learning_capacity import load_inputs
from run_learning_capacity import WallLimit


def inputs():
    d,x=load_inputs()
    with np.load(CACHE/'features.npz') as z:
        np.testing.assert_array_equal(z['cache_row'],np.arange(len(x)))
        angles=z['angles'];conv=z['convergence'];null=z['shuffle']
    return d,dict(angles=np.column_stack([x,angles]),convergence=np.column_stack([x,angles,conv]),shuffle=np.column_stack([x,angles,null]))


def main():
    p=argparse.ArgumentParser();p.add_argument('--fold',type=int,choices=range(3),required=True);p.add_argument('--smoke',action='store_true');a=p.parse_args();cfg=configuration()
    tick,cpu=time.perf_counter(),time.process_time();d,values=inputs();y=np.log(d['truth_E_GeV'])
    tr=np.flatnonzero(d['fold']==(a.fold+1)%3);ca=np.flatnonzero(d['fold']==(a.fold+2)%3);ev=np.flatnonzero(d['fold']==a.fold)
    if a.smoke:tr,ca,ev=tr[:200],ca[:200],ev[:100];values={'convergence':values['convergence']}
    for l,r in [(tr,ca),(tr,ev),(ca,ev)]:assert not set(d['group'][l])&set(d['group'][r])
    out=REPO/'ml/artifacts/stage51'/('smoke' if a.smoke else 'formal')/str(a.fold);out.mkdir(parents=True,exist_ok=True);assert not any(out.glob('*.ubj')),'Do not repeat successful fits'
    saved=dict(cache_row=ev,train_cache_row=tr,cal_cache_row=ca);records=[]
    for name,matrix in values.items():
        start,cp=time.perf_counter(),time.process_time();params=dict(cfg['xgboost'],seed=cfg['seed']+a.fold)
        model=xgb.train(params,xgb.DMatrix(matrix[tr],label=y[tr]),num_boost_round=20 if a.smoke else cfg['rounds'],callbacks=[WallLimit(cfg['fit_wall_limit_s'])])
        cal=model.predict(xgb.DMatrix(matrix[ca]));pred=model.predict(xgb.DMatrix(matrix[ev]));offset=float(np.mean(y[ca]-cal))
        saved[name]=np.exp(pred.astype(float)+offset);model.save_model(out/(name+'.ubj'))
        records.append(dict(model=name,fold=a.fold,columns=matrix.shape[1],rounds=model.num_boosted_rounds(),train_N=len(tr),calibration_N=len(ca),evaluation_N=len(ev),log_offset=offset,
            train_sources=sorted(set(d['group'][tr])),calibration_sources=sorted(set(d['group'][ca])),evaluation_sources=sorted(set(d['group'][ev])),
            wall_s=time.perf_counter()-start,cpu_s=time.process_time()-cp))
    md=dict(stage=51,fold=a.fold,smoke=a.smoke,config=cfg,records=records,wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,xgboost_version=xgb.__version__,numpy_version=np.__version__)
    np.savez_compressed(out/'predictions.npz',**saved,metadata_json=np.array(json.dumps(md)));print(json.dumps({k:v for k,v in md.items() if k!='config'}),flush=True)


if __name__=='__main__':main()
