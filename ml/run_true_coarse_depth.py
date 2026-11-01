#!/usr/bin/env python3
"""Stage46: one bounded true-region oracle, with unchanged source roles and X."""
import argparse
import json
import resource
import time
import numpy as np
import xgboost as xgb
from coarse_depth import REPO, load_inputs, region_labels
from information_gap import scalar_mapping
from run_calonu_information import WallLimit


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--fold',type=int,choices=range(3),required=True)
    p.add_argument('--smoke',action='store_true');a=p.parse_args()
    tick,cpu=time.perf_counter(),time.process_time()
    cfg=json.loads((REPO/'ml/configs/true_coarse_depth.json').read_text())
    rows,d,x=load_inputs();regions=region_labels(d['vertex_z_mm'],cfg['regions_mm'])
    values=np.column_stack([x,np.eye(5,dtype='float32')[regions]]).astype('float32')
    assert values.shape==(3703,92)
    y=np.log(d['truth_E_GeV'])
    tr=np.flatnonzero(d['fold']==(a.fold+1)%3)
    ca=np.flatnonzero(d['fold']==(a.fold+2)%3);ev=np.flatnonzero(d['fold']==a.fold)
    for left,right in [(tr,ca),(tr,ev),(ca,ev)]:
        assert not set(d['group'][left])&set(d['group'][right])
    if a.smoke: tr,ca,ev=tr[:200],ca[:200],ev[:100]
    out=REPO/'ml/artifacts/stage46'/('smoke' if a.smoke else 'formal')/str(a.fold)
    out.mkdir(parents=True,exist_ok=True)
    assert not (out/'oracle_region.ubj').exists(), 'Do not silently repeat a fit'
    labels=np.searchsorted(cfg['energy_edges_GeV'],np.exp(y),side='right')-1
    assert ((labels>=0)&(labels<6)).all()
    prior=np.bincount(labels[ca],minlength=6)/len(ca)
    start,cp=time.perf_counter(),time.process_time()
    model=xgb.train(dict(cfg['xgboost'],seed=cfg['seed']+a.fold),
                    xgb.DMatrix(values[tr],label=y[tr]),
                    num_boost_round=20 if a.smoke else cfg['rounds'],
                    callbacks=[WallLimit(cfg['fit_wall_limit_s'])])
    cal=model.predict(xgb.DMatrix(values[ca]));pred=model.predict(xgb.DMatrix(values[ev]))
    offset=float(np.mean(y[ca]-cal));energy=np.exp(pred.astype(float)+offset)
    saved=dict(cache_row=rows[ev],train_cache_row=rows[tr],cal_cache_row=rows[ca],
               prior=prior,oracle_region=energy)
    ms=time.perf_counter();iterations=None
    if (prior>0).all():
        saved['q_oracle_region'],iterations=scalar_mapping(cal.astype(float)+offset,labels[ca],pred.astype(float)+offset,prior)
    elif not a.smoke: raise ValueError('Formal calibration must cover all six bins')
    mapping_wall=time.perf_counter()-ms
    model.save_model(out/'oracle_region.ubj')
    rec=dict(model='oracle_region',kind='energy',fold=a.fold,train_N=len(tr),calibration_N=len(ca),evaluation_N=len(ev),
             columns=92,rounds=model.num_boosted_rounds(),log_offset=offset,
             train_sources=sorted(set(d['group'][tr])),calibration_sources=sorted(set(d['group'][ca])),evaluation_sources=sorted(set(d['group'][ev])),
             region_train_N=np.bincount(regions[tr],minlength=5).tolist(),
             mapping_iterations=iterations,mapping_wall_s=mapping_wall,
             wall_s=time.perf_counter()-start,cpu_s=time.process_time()-cp)
    md=dict(stage=46,fold=a.fold,smoke=a.smoke,config=cfg,records=[rec],
            wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,
            peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
            xgboost_version=xgb.__version__,numpy_version=np.__version__)
    np.savez_compressed(out/'predictions.npz',**saved,metadata_json=np.array(json.dumps(md)))
    print(json.dumps(md),flush=True)


if __name__=='__main__': main()
