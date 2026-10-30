#!/usr/bin/env python3
"""Small checkpoint readback and common-device throughput for spatial BDTs."""
import json
import time
from pathlib import Path

import cupy as cp
import numpy as np
import torch
import xgboost as xgb
import yaml

from benchmark_tabular import transform
from train_bdt import write_table
from train_spatial import inputs


def main():
    repo=Path(__file__).resolve().parents[1];out=repo/'workbook/stage18_energy_ml';folder=repo/'ml/artifacts/stage18/seed_0'
    cfg=yaml.safe_load((repo/'ml/configs/spatial.yaml').read_text());n=2048
    with np.load(repo/'ntuples/energy_ml_stage12/dataset/validation.npz') as d:
        base={k:d[k][:n] for k in d.files if not k.endswith('_json')}
    with np.load(repo/'ntuples/energy_ml_stage18/validation.npz') as d:
        spatial={k:d[k][:n] for k in d.files if not k.endswith('_json')}
    extra,_,moments,_=inputs(base,spatial,cfg);data=dict(**base,**extra)
    metadata=json.loads((folder/'preprocessing.json').read_text());rows=[];usage=[]
    with np.load(folder/'predictions.npz') as d:reference={k:d[k][:n] for k in d.files}
    for k in ['run','eventID']:np.testing.assert_array_equal(base[k],reference[k])
    for name in cfg['models']:
        state=metadata[name];raw=np.column_stack([data[k] for k in state['features']])
        if name=='reassigned':raw[:,-len(moments):]=spatial['reassigned_0']
        tick=time.perf_counter();x=transform(raw,state['preprocessor']);prewall=time.perf_counter()-tick
        model=xgb.Booster();path=folder/f'{name}.ubj';model.load_model(path);model.set_param({'device':'cuda','nthread':1})
        selected=model[:model.best_iteration+1]
        splits=selected.get_score(importance_type='weight');gains=selected.get_score(importance_type='total_gain');width=len(state['features'])
        for group in ['original','layer_counts','station_moments','tangent','missing_masks']:
            indices=[j for j,k in enumerate(state['features']) if ('original' if j<46 else 'layer_counts' if j<58 else 'tangent' if 'tangent' in k else 'station_moments')==group]
            if group=='missing_masks':indices=list(range(width,2*width))
            usage.append(dict(model=name,group=group,feature_columns=len(indices),splits=int(sum(splits.get(f'f{j}',0) for j in indices)),
                              total_gain=float(sum(gains.get(f'f{j}',0) for j in indices)),interpretation='selected-tree use diagnostic, not conditional physical importance'))
        gpu_x=cp.asarray(x);elapsed=[]
        for i in range(7):
            cp.cuda.get_current_stream().synchronize();tick=time.perf_counter()
            pred=model.inplace_predict(gpu_x,iteration_range=(0,model.best_iteration+1))
            cp.cuda.get_current_stream().synchronize()
            if i:elapsed.append(time.perf_counter()-tick)
        prediction=np.exp(cp.asnumpy(pred).astype(float)*state['target_spread']+state['target_center'])
        np.testing.assert_allclose(prediction,reference[name],rtol=2e-5,atol=.001)
        row=dict(model=name,N=n,device=torch.cuda.get_device_name(0),features=len(state['features']),
                 preprocessing_wall_s=prewall,gpu_median_wall_s=float(np.median(elapsed)),gpu_events_per_s=n/float(np.median(elapsed)),
                 checkpoint_bytes=path.stat().st_size,max_relative_prediction_difference=float(np.max(abs(prediction/reference[name]-1))))
        model.set_param({'device':'cpu'});elapsed=[]
        for i in range(7):
            tick=time.perf_counter();model.inplace_predict(x,iteration_range=(0,model.best_iteration+1))
            if i:elapsed.append(time.perf_counter()-tick)
        row.update(cpu_median_wall_s=float(np.median(elapsed)),cpu_events_per_s=n/float(np.median(elapsed)),host_device_transfer_included=False)
        rows.append(row);del gpu_x,model;cp.get_default_memory_pool().free_all_blocks()
    write_table(out/'checkpoint_and_inference.tsv',rows);write_table(out/'feature_use.tsv',usage)
    print(json.dumps(dict(models=len(rows),all_checkpoint_readbacks_verified=True)))


if __name__=='__main__':main()
