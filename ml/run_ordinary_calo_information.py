#!/usr/bin/env python3
"""Two frozen sensitive-sampling oracles; independent source calibration."""
import argparse
import json
import resource
import time
import numpy as np
import xgboost as xgb
from coarse_depth import REPO
from ordinary_calo_information import load_sensitive
from information_gap import scalar_mapping
from run_calonu_information import WallLimit


def main():
    p=argparse.ArgumentParser();p.add_argument('--fold',type=int,choices=range(3),required=True)
    p.add_argument('--smoke',action='store_true');a=p.parse_args();tick,cpu=time.perf_counter(),time.process_time()
    cfg=json.loads((REPO/'ml/configs/ordinary_calo_information.json').read_text())
    rows,d,candidates=load_sensitive();y=np.log(d['truth_E_GeV'])
    tr=np.flatnonzero(d['fold']==(a.fold+1)%3);ca=np.flatnonzero(d['fold']==(a.fold+2)%3);ev=np.flatnonzero(d['fold']==a.fold)
    for left,right in [(tr,ca),(tr,ev),(ca,ev)]:assert not set(d['group'][left])&set(d['group'][right])
    if a.smoke:
        tr,ca,ev=tr[:200],ca[:200],ev[:100];candidates={'ordinary_calo':candidates['ordinary_calo']}
    labels=np.searchsorted(cfg['energy_edges_GeV'],np.exp(y),side='right')-1
    assert ((labels>=0)&(labels<6)).all();prior=np.bincount(labels[ca],minlength=6)/len(ca)
    out=REPO/'ml/artifacts/stage47'/('smoke' if a.smoke else 'formal')/str(a.fold);out.mkdir(parents=True,exist_ok=True)
    assert not any(out.glob('*.ubj')),'Do not silently repeat successful fits'
    saved=dict(cache_row=rows[ev],train_cache_row=rows[tr],cal_cache_row=rows[ca],prior=prior);records=[]
    for name,values in candidates.items():
        start,cp=time.perf_counter(),time.process_time()
        model=xgb.train(dict(cfg['xgboost'],seed=cfg['seed']+a.fold),xgb.DMatrix(values[tr],label=y[tr]),
                        num_boost_round=20 if a.smoke else cfg['rounds'],callbacks=[WallLimit(cfg['fit_wall_limit_s'])])
        cal=model.predict(xgb.DMatrix(values[ca]));pred=model.predict(xgb.DMatrix(values[ev]))
        offset=float(np.mean(y[ca]-cal));saved[name]=np.exp(pred.astype(float)+offset)
        ms=time.perf_counter();iterations=None
        if (prior>0).all():saved['q_'+name],iterations=scalar_mapping(cal.astype(float)+offset,labels[ca],pred.astype(float)+offset,prior)
        elif not a.smoke:raise ValueError('Formal calibration must cover all bins')
        mapping_wall=time.perf_counter()-ms;model.save_model(out/(name+'.ubj'))
        records.append(dict(model=name,kind='energy',fold=a.fold,columns=values.shape[1],rounds=model.num_boosted_rounds(),
                            train_N=len(tr),calibration_N=len(ca),evaluation_N=len(ev),log_offset=offset,
                            train_sources=sorted(set(d['group'][tr])),calibration_sources=sorted(set(d['group'][ca])),evaluation_sources=sorted(set(d['group'][ev])),
                            mapping_iterations=iterations,mapping_wall_s=mapping_wall,wall_s=time.perf_counter()-start,cpu_s=time.process_time()-cp))
    md=dict(stage=47,fold=a.fold,smoke=a.smoke,config=cfg,records=records,wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,
            peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,xgboost_version=xgb.__version__,numpy_version=np.__version__)
    np.savez_compressed(out/'predictions.npz',**saved,metadata_json=np.array(json.dumps(md)));print(json.dumps(md),flush=True)


if __name__=='__main__':main()
