#!/usr/bin/env python3
"""Audit actual weights and small checkpoint readbacks, without fitting."""
import argparse
import json
from pathlib import Path

import cupy as cp
import numpy as np
import torch
import xgboost as xgb
import yaml

from benchmark_tabular import transform
from check_set_preprocessing import compare_preprocessing
from robustness import bin_weights
from train_bdt import write_table
from train_tabular import make_model


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--smoke',action='store_true');args=p.parse_args()
    root=Path(__file__).resolve().parents[1];out=root/'workbook/stage21_energy_ml'
    cfg=yaml.safe_load((root/'ml/configs/prior.yaml').read_text());study=yaml.safe_load((root/cfg['reference_study']).read_text())
    base=yaml.safe_load((root/'ml/configs/baseline.yaml').read_text());torch.set_num_threads(1)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    with np.load(root/'ntuples/energy_ml_stage12/dataset/train.npz') as d:train_energy=d[base['target']]
    w,counts,mapping=bin_weights(train_energy,train_energy,cfg['energy_edges_GeV'])
    bins=np.searchsorted(cfg['energy_edges_GeV'],train_energy,side='right')-1
    np.testing.assert_allclose(np.bincount(bins,weights=w),np.full(6,len(w)/6),rtol=1e-12)
    np.testing.assert_allclose(w.mean(),1,rtol=1e-14)
    n=400 if args.smoke else 2048
    with np.load(root/'ntuples/energy_ml_stage12/dataset/validation.npz') as d:
        val={k:d[k][:n] for k in sum(base['feature_groups'].values(),[])+['run','eventID']}
    checks=[];common=None
    for arch in cfg['architectures']:
        for mode in cfg['modes']:
            name=f'{arch}_{mode}'
            folder=Path(f'/tmp/nu_mu_stage21_smoke_{name}') if args.smoke else root/f'ml/artifacts/stage21/{name}'
            meta=json.loads((folder/'preprocessing.json').read_text())
            if common is None:common=meta
            difference=compare_preprocessing(common,meta)
            x=transform(np.column_stack([val[k] for k in meta['features']]),meta['preprocessor'])
            if arch=='bdt':
                model=xgb.Booster();model.load_model(folder/'best.ubj');model.set_param({'device':'cuda','nthread':1})
                raw=cp.asnumpy(model.inplace_predict(cp.asarray(x),iteration_range=(0,model.best_iteration+1)))
            else:
                ckpt=torch.load(folder/'best.pt',map_location='cpu',weights_only=True)
                assert ckpt['prior_study']==cfg and ckpt['mode']==mode
                model=make_model('tabm',x.shape[1],cfg['fixed_trials']['tabm'],study).cuda().eval();model.load_state_dict(ckpt['state_dict'])
                with torch.no_grad():raw=model(torch.as_tensor(x,device='cuda')).mean(1).squeeze(-1).cpu().numpy()
            pred=np.exp(raw.astype(float)*meta['target_spread']+meta['target_center'])
            with np.load(folder/'predictions.npz') as d:
                for k in ['run','eventID']:np.testing.assert_array_equal(d[k][:n],val[k])
                reference=d['seed_0'][:n]
            np.testing.assert_allclose(pred,reference,rtol=2e-5,atol=.001)
            checks.append(dict(model=name,N=n,max_relative_checkpoint_difference=float(np.max(abs(pred/reference-1))),**difference))
            del model;torch.cuda.empty_cache()
    prefix='smoke_' if args.smoke else ''
    write_table(out/f'{prefix}checkpoint_checks.tsv',checks)
    record=dict(models=len(checks),checkpoint_events=n,all_checkpoint_readbacks_passed=True,train_counts=counts.tolist(),mapping=mapping.tolist(),
                train_sumw=float(w.sum()),train_sumw2=float((w*w).sum()),train_Neff=float(w.sum()**2/(w*w).sum()),
                equal_train_bin_weight_sums_passed=True,all_preprocessing_consistent=True,smoke=args.smoke)
    if args.smoke:
        summaries=[json.loads(Path(f'/tmp/nu_mu_stage21_smoke_{a}_{m}/summary.json').read_text()) for a in cfg['architectures'] for m in cfg['modes']]
        for s in summaries:s.pop('study')
        (out/'smoke_summary.json').write_text(json.dumps(summaries,indent=2)+'\n')
        record['common_trajectory_checks']=[]
        for arch in cfg['architectures']:
            for left,right in [('UU','UF'),('FU','FF')]:
                paths=[Path(f'/tmp/nu_mu_stage21_smoke_{arch}_{m}')/'predictions.npz' for m in [left,right]]
                with np.load(paths[0]) as a,np.load(paths[1]) as b:np.testing.assert_array_equal(a['seed_0'],b['seed_0'])
                record['common_trajectory_checks'].append(dict(architecture=arch,modes=[left,right],smoke_predictions_identical=True))
    (out/f'{prefix}numerical_checks.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))


if __name__=='__main__':main()
