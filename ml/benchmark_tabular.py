#!/usr/bin/env python3
"""Small common-device inference check: 2048 frozen validation rows, no fitting."""
import argparse
import json
import time
from pathlib import Path

import cupy as cp
import numpy as np
import torch
import xgboost as xgb
import yaml

from train_bdt import check_features, write_table
from train_tabular import make_model


def transform(raw,state):
    missing=~np.isfinite(raw)
    x=np.arcsinh(np.where(missing,np.nan,raw)/np.array(state['scale']))
    x=np.where(missing,np.array(state['fill']),x)
    return np.column_stack([(x-np.array(state['mean']))/np.array(state['std']),missing]).astype('float32')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
    args=p.parse_args();repo=args.repo;out=repo/'workbook/stage16_energy_ml';art=repo/'ml/artifacts/stage16'
    cfg=yaml.safe_load((repo/'ml/configs/tabular.yaml').read_text())
    base=yaml.safe_load((repo/'ml/configs/baseline.yaml').read_text());torch.set_num_threads(1)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    rows=[];checks=[]
    with np.load(repo/'ntuples/energy_ml_stage12/dataset/validation.npz') as d:
        # Only this small prefix is evaluated for timing and checkpoint readback.
        val={k:d[k][:2048] for k in sum(base['feature_groups'].values(),[])+['run','eventID']}
    for arch in cfg['architectures']:
        for version in cfg['versions']:
            name=f'{arch}_{version}';folder=art/name
            meta=json.loads((folder/'preprocessing.json').read_text());names=meta['features']
            check_features(names,sum(base['feature_groups'].values(),[]))
            tick=time.perf_counter();x=transform(np.column_stack([val[k] for k in names]),meta['preprocessor']);prewall=time.perf_counter()-tick
            if arch=='bdt':
                model=xgb.Booster();model.load_model(folder/'best.ubj');model.set_param({'nthread':1,'device':'cuda'})
                gpu_x=cp.asarray(x)
                def forward_gpu(batch):
                    values=[model.inplace_predict(a,iteration_range=(0,model.best_iteration+1)) for a in cp.array_split(gpu_x,len(x)//batch)]
                    return cp.concatenate(values)
                sync=cp.cuda.get_current_stream().synchronize
            else:
                checkpoint=torch.load(folder/'best.pt',map_location='cpu',weights_only=True)
                if names!=checkpoint['features']:raise RuntimeError('Checkpoint feature mismatch')
                model=make_model(arch,x.shape[1],checkpoint['trial'],cfg).cuda().eval();model.load_state_dict(checkpoint['state_dict'])
                gpu_x=torch.as_tensor(x,device='cuda')
                def forward_gpu(batch):
                    with torch.no_grad():return torch.cat([model(a).reshape(len(a),-1).mean(1) for a in gpu_x.split(batch)])
                sync=torch.cuda.synchronize
            for batch in [256,2048]:
                elapsed=[]
                for i in range(7):
                    sync();tick=time.perf_counter();raw=forward_gpu(batch);sync()
                    if i:elapsed.append(time.perf_counter()-tick)
                prediction=np.exp((cp.asnumpy(raw) if arch=='bdt' else raw.cpu().numpy()).astype(float)*meta['target_spread']+meta['target_center'])
                with np.load(folder/'predictions.npz') as d:
                    for key in ['run','eventID']:np.testing.assert_array_equal(val[key],d[key][:len(x)])
                    reference=d['seed_0'][:len(x)]
                np.testing.assert_allclose(prediction,reference,rtol=2e-5,atol=.001)
                checks.append(dict(model=name,batch_size=batch,N=len(x),max_relative_checkpoint_difference=float(np.max(abs(prediction/reference-1)))))
                path=folder/('best.ubj' if arch=='bdt' else 'best.pt')
                rows.append(dict(model=name,device=torch.cuda.get_device_name(0),batch_size=batch,N=len(x),
                                 median_wall_s=float(np.median(elapsed)),events_per_s=len(x)/float(np.median(elapsed)),
                                 preprocessing_wall_s=prewall,model_bytes=path.stat().st_size,host_device_transfer_included=False))
            if arch=='bdt':
                model.set_param({'device':'cpu'})
                def forward_cpu(batch):
                    return np.concatenate([model.inplace_predict(a,iteration_range=(0,model.best_iteration+1)) for a in np.array_split(x,len(x)//batch)])
            else:
                model=model.cpu();cpu_x=torch.from_numpy(x)
                def forward_cpu(batch):
                    with torch.no_grad():return torch.cat([model(a).reshape(len(a),-1).mean(1) for a in cpu_x.split(batch)])
            elapsed=[]
            for i in range(7):
                tick=time.perf_counter();forward_cpu(2048)
                if i:elapsed.append(time.perf_counter()-tick)
            rows.append(dict(model=name,device='CPU 1 thread',batch_size=2048,N=len(x),median_wall_s=float(np.median(elapsed)),
                             events_per_s=len(x)/float(np.median(elapsed)),preprocessing_wall_s=prewall,model_bytes=path.stat().st_size,
                             host_device_transfer_included=False))
            del model,gpu_x
            torch.cuda.empty_cache();cp.get_default_memory_pool().free_all_blocks()
    write_table(out/'common_device_inference.tsv',rows);write_table(out/'checkpoint_readback.tsv',checks)
    print(json.dumps(dict(models=8,events_per_check=2048,all_checkpoints_verified=True,gpu=torch.cuda.get_device_name(0))))


if __name__=='__main__':main()
