#!/usr/bin/env python3
"""Fixed source-disjoint training, calibration and scalar mapping for stage42."""
import argparse
import json
import resource
import time
from pathlib import Path
import numpy as np
import xgboost as xgb
from information_gap import scalar_mapping


class WallLimit(xgb.callback.TrainingCallback):
    def __init__(self, seconds): self.seconds=seconds; self.start=time.perf_counter()
    def after_iteration(self, model, epoch, evals_log):
        if time.perf_counter()-self.start>self.seconds:
            raise TimeoutError('Frozen per-fit wall limit exceeded')
        return False


def main():
    p=argparse.ArgumentParser(); p.add_argument('--part',choices=['A','B','C'],required=True)
    p.add_argument('--fold',type=int,choices=range(3),required=True); p.add_argument('--smoke',action='store_true')
    a=p.parse_args(); tick,cpu=time.perf_counter(),time.process_time(); repo=Path(__file__).resolve().parents[1]
    cfg=json.loads((repo/'ml/configs/calonu_information.json').read_text()); cache=repo/'ntuples/energy_ml_stage42'
    with np.load(cache/'development.npz') as z: d={k:z[k] for k in z.files}
    chosen=np.arange(len(d['x'])) if a.part=='A' else np.flatnonzero(d['selected'])
    if a.part!='A':
        with np.load(cache/'sensitive.npz') as z:
            np.testing.assert_array_equal(z['cache_row'],chosen); np.testing.assert_array_equal(z['eventID'],d['eventID'][chosen])
            signal=z['hit_energy_MeV']
    x=d['x'][chosen]; y=np.log(d['truth_E_GeV'][chosen]); fold=d['fold'][chosen]
    candidates={'A0':x,'A_zero':np.column_stack([x,d['zero'][chosen]]),'A_readout':np.column_stack([x,d['calo'][chosen]])} if a.part=='A' else {
        'I0':x,'Iz':np.column_stack([x,d['vertex_z_mm'][chosen]]),'Is':np.column_stack([x,signal]),
        'Isz':np.column_stack([x,signal,d['vertex_z_mm'][chosen]])}
    if a.part=='C':
        with np.load(cache/'synthetic.npz') as z:
            np.testing.assert_array_equal(z['cache_row'],chosen)
            candidates={k:np.column_stack([x,z[k]]) for k in cfg['synthetic_if_gate']['candidates']}
    tr=np.flatnonzero(fold==(a.fold+1)%3); ca=np.flatnonzero(fold==(a.fold+2)%3); ev=np.flatnonzero(fold==a.fold)
    if a.smoke:
        tr=tr[:200]; ca=ca[:200]; ev=ev[:100]; candidates=dict(list(candidates.items())[:2])
    labels=np.searchsorted(cfg['energy_edges_GeV'],np.exp(y),side='right')-1
    assert ((labels>=0)&(labels<6)).all()
    for l,r in [(tr,ca),(tr,ev),(ca,ev)]: assert not set(d['group'][chosen[l]])&set(d['group'][chosen[r]])
    pri=np.bincount(labels[ca],minlength=6)/len(ca)
    out=repo/'ml/artifacts/stage42'/('smoke' if a.smoke else a.part)/str(a.fold); out.mkdir(parents=True,exist_ok=True)
    saved={'cache_row':chosen[ev],'prior':pri}; records=[]
    for name,values in candidates.items():
        start,cp=time.perf_counter(),time.process_time(); values=values.astype('float32'); values[~np.isfinite(values)]=np.nan
        dt=xgb.DMatrix(values[tr],label=y[tr]); dc=xgb.DMatrix(values[ca]); de=xgb.DMatrix(values[ev])
        model=xgb.train(dict(cfg['xgboost'],seed=cfg['seed']+a.fold),dt,num_boost_round=20 if a.smoke else cfg['rounds'],
                        callbacks=[WallLimit(cfg['fit_wall_limit_s'])])
        cal=model.predict(dc); pred=model.predict(de); offset=float(np.mean(y[ca]-cal))
        saved[name]=np.exp(pred.astype(float)+offset)
        # Same calibration source predictions are independent of the trained BDT.
        # Offset is redundant for a scalar map but applied consistently to both sides.
        map_start=time.perf_counter()
        if (pri>0).all():
            q,it=scalar_mapping(cal.astype(float)+offset,labels[ca],pred.astype(float)+offset,pri)
            saved['q_'+name]=q
        else: it=None
        map_wall=time.perf_counter()-map_start
        model.save_model(out/(name+'.ubj'))
        records.append(dict(model=name,part=a.part,fold=a.fold,train_N=len(tr),calibration_N=len(ca),evaluation_N=len(ev),
                            columns=values.shape[1],rounds=model.num_boosted_rounds(),log_offset=offset,
                            scalar_mapping_measured=it is not None,mapping_iterations=it,mapping_wall_s=map_wall,
                            wall_s=time.perf_counter()-start,cpu_s=time.process_time()-cp))
        print(json.dumps(records[-1]),flush=True)
    metadata=dict(part=a.part,fold=a.fold,smoke=a.smoke,records=records,wall_s=time.perf_counter()-tick,
                  cpu_s=time.process_time()-cpu,peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                  config=cfg,xgboost_version=xgb.__version__,numpy_version=np.__version__)
    np.savez_compressed(out/'predictions.npz',**saved,metadata_json=np.array(json.dumps(metadata)))
    print(json.dumps({k:v for k,v in metadata.items() if k not in ['config','records']}),flush=True)

if __name__=='__main__': main()
