#!/usr/bin/env python3
"""Frozen source-nested depth representation and same-input energy/oracle models."""
import argparse
import json
import resource
import time
from pathlib import Path
import numpy as np
import xgboost as xgb
from coarse_depth import REPO, load_inputs, region_labels, inner_roles, smoothed_prior
from information_gap import scalar_mapping
from run_calonu_information import WallLimit


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--fold',type=int,choices=range(3),required=True)
    parser.add_argument('--smoke',action='store_true');args=parser.parse_args()
    tick,cpu=time.perf_counter(),time.process_time()
    cfg=json.loads((REPO/'ml/configs/coarse_depth.json').read_text())
    rows,d,x=load_inputs();lab=region_labels(d['vertex_z_mm'],cfg['regions_mm']);y=np.log(d['truth_E_GeV'])
    tr=np.flatnonzero(d['fold']==(args.fold+1)%3);ca=np.flatnonzero(d['fold']==(args.fold+2)%3);ev=np.flatnonzero(d['fold']==args.fold)
    for left,right in [(tr,ca),(tr,ev),(ca,ev)]:assert not set(d['group'][left])&set(d['group'][right])
    out=REPO/'ml/artifacts/stage45'/('smoke' if args.smoke else 'formal')/str(args.fold);out.mkdir(parents=True,exist_ok=True)
    records=[]

    def classifier(name,train,predict,seed):
        start,cp=time.perf_counter(),time.process_time()
        prior=smoothed_prior(lab[train],5,cfg['depth_prior_alpha'])
        def matrix(ids,labels=None):
            return xgb.DMatrix(x[ids],label=labels,base_margin=np.tile(np.log(prior).astype('float32'),(len(ids),1)))
        model=xgb.train(dict(cfg['depth_xgboost'],seed=seed),matrix(train,lab[train]),
                        num_boost_round=20 if args.smoke else cfg['depth_rounds'],callbacks=[WallLimit(cfg['fit_wall_limit_s'])])
        values={role:model.predict(matrix(ids)).astype(float) for role,ids in predict.items()}
        for q in values.values():assert q.shape[1]==5 and np.isfinite(q).all() and (q>0).all();np.testing.assert_allclose(q.sum(axis=1),1,atol=2e-7)
        model.save_model(out/(name+'.ubj'))
        records.append(dict(model=name,kind='depth',fold=args.fold,train_N=len(train),train_sources=sorted(set(d['group'][train])),
                            predict_N={k:len(v) for k,v in predict.items()},predict_sources={k:sorted(set(d['group'][v])) for k,v in predict.items()},
                            columns=x.shape[1],rounds=model.num_boosted_rounds(),region_train_N=np.bincount(lab[train],minlength=5).tolist(),depth_prior=prior.tolist(),
                            wall_s=time.perf_counter()-start,cpu_s=time.process_time()-cp))
        print(json.dumps(records[-1]),flush=True);return values,prior

    if args.smoke:
        tr,ev=tr[:200],ev[:100]
        q,prior=classifier('depth_smoke',tr,dict(evaluation=ev),cfg['depth_seed']+args.fold)
        saved=dict(cache_row=rows[ev],depth_q=q['evaluation'],depth_prior=prior)
    else:
        inner,mapping=inner_roles(d['group'],d['fold']==(args.fold+1)%3)
        qtr=np.full((len(tr),5),np.nan);ptr=qtr.copy()
        for k in range(2):
            fit=tr[inner[tr]!=k];dest=tr[inner[tr]==k]
            assert not set(d['group'][fit])&set(d['group'][dest])
            q,prior=classifier(f'depth_inner{k}',fit,dict(oof=dest),cfg['depth_seed']+10*args.fold+k)
            qtr[inner[tr]==k]=q['oof'];ptr[inner[tr]==k]=prior
        assert np.isfinite(qtr).all()
        q,pdepth=classifier('depth_full',tr,dict(calibration=ca,evaluation=ev),cfg['depth_seed']+10*args.fold+2)
        xsoft=np.full((len(x),5),np.nan);xsoft[tr]=qtr;xsoft[ca]=q['calibration'];xsoft[ev]=q['evaluation']
        enlab=np.searchsorted(cfg['energy_edges_GeV'],np.exp(y),side='right')-1
        assert ((enlab>=0)&(enlab<6)).all()
        prior=np.bincount(enlab[ca],minlength=6)/len(ca);assert (prior>0).all()
        saved=dict(cache_row=rows[ev],prior=prior,depth_q=q['evaluation'],depth_prior=pdepth,
                   train_cache_row=rows[tr],cal_cache_row=rows[ca],depth_train_oof=qtr,depth_train_prior=ptr,
                   depth_cal=q['calibration'],inner_fold=inner[tr])
        candidates=dict(reco_depth=np.column_stack([x,xsoft]),oracle_z=np.column_stack([x,d['vertex_z_mm']]))
        for name,values in candidates.items():
            start,cp=time.perf_counter(),time.process_time();values=values.astype('float32')
            dt=xgb.DMatrix(values[tr],label=y[tr]);dc=xgb.DMatrix(values[ca]);de=xgb.DMatrix(values[ev])
            model=xgb.train(dict(cfg['xgboost'],seed=cfg['seed']+args.fold),dt,num_boost_round=cfg['rounds'],callbacks=[WallLimit(cfg['fit_wall_limit_s'])])
            cal,pred=model.predict(dc),model.predict(de);offset=float(np.mean(y[ca]-cal))
            saved[name]=np.exp(pred.astype(float)+offset)
            ms=time.perf_counter();saved['q_'+name],iterations=scalar_mapping(cal.astype(float)+offset,enlab[ca],pred.astype(float)+offset,prior)
            mapping_wall=time.perf_counter()-ms
            model.save_model(out/(name+'.ubj'))
            records.append(dict(model=name,kind='energy',fold=args.fold,train_N=len(tr),calibration_N=len(ca),evaluation_N=len(ev),columns=values.shape[1],
                                rounds=model.num_boosted_rounds(),log_offset=offset,mapping_iterations=iterations,mapping_wall_s=mapping_wall,
                                wall_s=time.perf_counter()-start,cpu_s=time.process_time()-cp))
            print(json.dumps(records[-1]),flush=True)
    metadata=dict(stage=45,fold=args.fold,smoke=args.smoke,config=cfg,records=records,wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,
                  peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,xgboost_version=xgb.__version__,numpy_version=np.__version__)
    np.savez_compressed(out/'predictions.npz',**saved,metadata_json=np.array(json.dumps(metadata)))
    print(json.dumps({k:v for k,v in metadata.items() if k not in ['config','records']}),flush=True)


if __name__=='__main__':main()
