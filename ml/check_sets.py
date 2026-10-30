#!/usr/bin/env python3
"""Small numerical, point-order, null-invariance and inference checks."""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
import yaml

from set_data import PointBatches,load_data
from train_sets import SetRegressor
from train_bdt import write_table
from check_set_preprocessing import compare_preprocessing


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--smoke-artifacts',action='store_true');args=p.parse_args()
    root=Path(__file__).resolve().parents[1];out=root/'workbook/stage19_energy_ml'
    cfg=yaml.safe_load((root/'ml/configs/sets.yaml').read_text());geo=yaml.safe_load((root/cfg['geometry_config']).read_text());base=yaml.safe_load((root/'ml/configs/baseline.yaml').read_text())
    torch.set_num_threads(1);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    def folder(name):return Path(f'/tmp/nu_mu_stage19_smoke_{name}') if args.smoke_artifacts else root/f'ml/artifacts/stage19/{name}'
    first=torch.load(folder('summary')/'best.pt',map_location='cpu',weights_only=True)
    parts,pre=load_data(root,root,cfg,base,smoke=True,fixed_preprocessing=first['preprocessing']);part=parts[1];n=len(part['y'])
    rows=[];order_checks=[];rng=np.random.default_rng(20261029)
    for name in cfg['models']:
        ckpt=torch.load(folder(name)/'best.pt',map_location='cpu',weights_only=True)
        preprocessing_difference=compare_preprocessing(pre,ckpt['preprocessing'])
        assert ckpt['study']==cfg and ckpt['variant']==name
        scalar_difference=0.
        if ckpt['preprocessing']!=pre:
            own_parts,_=load_data(root,root,cfg,base,smoke=True,fixed_preprocessing=ckpt['preprocessing'])
            scalar_difference=max(float(np.max(abs(a['scalar']-b['scalar']))) for a,b in zip(parts,own_parts))
            np.testing.assert_allclose(part['scalar'],own_parts[1]['scalar'],rtol=1e-7,atol=1e-7)
            ts={k:torch.as_tensor(own_parts[1][k],device='cuda') for k in ['scalar','summary']}
        else:ts={k:torch.as_tensor(part[k],device='cuda') for k in ['scalar','summary']}
        model=SetRegressor(name,part['scalar'].shape[1],ckpt['trial'],cfg).cuda().eval();model.load_state_dict(ckpt['state_dict'])
        cloud=None if name=='summary' else PointBatches(part['points'],part['counts'],part['metadata'],geo,name,cfg['seeds'][0])
        tick=time.perf_counter();points,counts=(None,None) if cloud is None else cloud.batch(np.arange(n));torch.cuda.synchronize();gather=time.perf_counter()-tick
        with torch.no_grad():
            raw=model(ts['scalar'],ts['summary'],points,counts)
            if points is not None:
                lengths=part['counts'].sum(2).reshape(-1);starts=np.r_[0,lengths.cumsum()]
                order=np.concatenate([rng.permutation(np.arange(lo,hi)) for lo,hi in zip(starts[:-1],starts[1:])])
                permuted=points[torch.as_tensor(order,device='cuda')]
                shuffled=model(ts['scalar'],ts['summary'],permuted,counts)
                difference=float((raw-shuffled).abs().max());np.testing.assert_allclose(raw.cpu(),shuffled.cpu(),rtol=2e-5,atol=2e-5)
                if name=='global':
                    starts=part['metadata']['offsets'];order=np.concatenate([rng.permutation(np.arange(lo,hi)) for lo,hi in zip(starts[:-1],starts[1:])])
                    shuffled=model(ts['scalar'],ts['summary'],points[torch.as_tensor(order,device='cuda')],counts)
                    global_difference=float((raw-shuffled).abs().max());np.testing.assert_allclose(raw.cpu(),shuffled.cpu(),rtol=2e-5,atol=2e-5)
                else:global_difference='not_applicable'
            else:difference=0.;global_difference='not_applicable'
            prediction=np.exp(raw.cpu().numpy().astype(float)*pre['target_spread']+pre['target_center'])
            with np.load(folder(name)/'predictions.npz') as d:
                for k in ['run','eventID']:np.testing.assert_array_equal(d[k][:n],part['metadata'][k])
                reference=d['seed_0'][:n]
            np.testing.assert_allclose(prediction,reference,rtol=2e-5,atol=.001)
            association_max='not_applicable';association_mean='not_applicable'
            if name=='full':
                null=PointBatches(part['points'],part['counts'],part['metadata'],geo,'reassigned',cfg['seeds'][0])
                null_points,null_counts=null.batch(np.arange(n))
                changed=model(ts['scalar'],ts['summary'],null_points,null_counts)
                association_max=float((raw-changed).abs().max());association_mean=float((raw-changed).abs().mean())
                assert association_max>1e-5
                del null,null_points,null_counts,changed
            order_checks.append(dict(model=name,N=n,within_station_max_abs_standardized_log_difference=difference,
                                     global_xy_permutation_max_difference=global_difference,max_checkpoint_relative_difference=float(np.max(abs(prediction/reference-1))),
                                     reassignment_max_abs_standardized_log_change=association_max,reassignment_mean_abs_standardized_log_change=association_mean,
                                     max_transformed_scalar_difference=scalar_difference,**preprocessing_difference))
            # Sustained warmup avoids comparing transient GPU power states.
            torch.cuda.synchronize();warm_start=time.perf_counter();warm_iterations=0
            while time.perf_counter()-warm_start<.5:
                model(ts['scalar'],ts['summary'],points,counts);torch.cuda.synchronize();warm_iterations+=1
            elapsed=[]
            for i in range(20):
                torch.cuda.synchronize();tick=time.perf_counter();model(ts['scalar'],ts['summary'],points,counts);torch.cuda.synchronize()
                elapsed.append(time.perf_counter()-tick)
            row=dict(model=name,N=n,points=0 if cloud is None else len(points),gpu=torch.cuda.get_device_name(0),gpu_median_wall_s=float(np.median(elapsed)),
                     gpu_events_per_s=n/float(np.median(elapsed)),gpu_min_wall_s=min(elapsed),gpu_max_wall_s=max(elapsed),
                     gpu_warmup_iterations=warm_iterations,gpu_measured_repeats=len(elapsed),
                     gather_wall_s=gather,parameters=sum(p.numel() for p in model.parameters()),checkpoint_bytes=(folder(name)/'best.pt').stat().st_size)
            model=model.cpu();cpu_scalar=ts['scalar'].cpu();cpu_summary=ts['summary'].cpu();cpu_points=None if points is None else points.cpu();cpu_counts=None if counts is None else counts.cpu()
            elapsed=[]
            for i in range(7):
                tick=time.perf_counter();model(cpu_scalar,cpu_summary,cpu_points,cpu_counts)
                if i:elapsed.append(time.perf_counter()-tick)
            row.update(cpu_median_wall_s=float(np.median(elapsed)),cpu_events_per_s=n/float(np.median(elapsed)),preprocessing_and_transfers_included=False);rows.append(row)
        del model,cloud,points,counts;torch.cuda.empty_cache()
    # Explicitly verify that the null preserves the complete xy multiset in all 400 events.
    original=PointBatches(part['points'],part['counts'],part['metadata'],geo,'full',cfg['seeds'][0],device='cpu')
    shuffled=PointBatches(part['points'],part['counts'],part['metadata'],geo,'reassigned',cfg['seeds'][0],device='cpu')
    a=original.features.numpy();b=shuffled.features.numpy();np.testing.assert_array_equal(a[:,2:],b[:,2:])
    for lo,hi in zip(part['metadata']['offsets'][:-1],part['metadata']['offsets'][1:]):
        aa=a[lo:hi,:2];bb=b[lo:hi,:2]
        np.testing.assert_array_equal(aa[np.lexsort(aa.T)],bb[np.lexsort(bb.T)])
    prefix='smoke_' if args.smoke_artifacts else ''
    write_table(out/f'{prefix}checkpoint_checks.tsv',order_checks);write_table(out/f'{prefix}inference.tsv',rows)
    record=dict(models=4,events=n,null_xy_multisets_exact=True,null_geometry_and_counts_exact=True,
                object_order_invariance_passed=True,checkpoint_readbacks_passed=True,smoke=args.smoke_artifacts)
    (out/f'{prefix}numerical_checks.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))


if __name__=='__main__':main()
