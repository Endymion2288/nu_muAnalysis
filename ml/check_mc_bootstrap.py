#!/usr/bin/env python3
"""Replay source/response bootstraps and independently scan selected LR fits."""
import json
import time
from pathlib import Path

import numpy as np

from check_profile_response import convex,scan_profile
from closure import load_data,read_table
from mc_bootstrap import (aggregate,basis,bootstrap_indices,config,counts_from_uniform,
                          observed_uniform,pseudo_uniform,source_sample_indices)
from profile_response import Response,nll


def main():
    tick=time.perf_counter();root=Path(__file__).resolve().parents[1];cfg=config(root);out=root/'workbook/stage28_energy_ml'
    allwidths=read_table(out/'widths.tsv');counts=0;samples=0;losses=0;scans=0;lrscans=0;endpoints=0
    maxloss=0.;maxglobal=0.;maxlr=0.;maxendpoint=0.;maxpool=0.;maxrawnegative=0.;near=0
    for model,spec in cfg['models'].items():
        for seed in spec['seeds']:
            local={**cfg,'models':{model:{**spec,'seeds':[seed]}}}
            y,bins,gi,groups,fold,pred=load_data(root,local,model,False);powers,index,logs,reco=basis(y,bins,pred[0],cfg)
            pool=aggregate(powers,index,np.ones(len(y)));population=Response(pool)
            with np.load(root/f'ml/artifacts/stage28/{model}/seed_{seed}/mc_bootstrap.npz') as z:d={k:z[k] for k in z.files}
            maxpool=max(maxpool,float(abs(pool-d['pool']).max()));np.testing.assert_allclose(pool,d['pool'],atol=1e-12,rtol=1e-13)
            for k in ['actual_lrs','bootstrap_lrs','fits','bootstrap_fits','actual_loss','bootstrap_loss']:assert np.isfinite(d[k]).all(),(model,seed,k)
            assert (d['actual_lrs']>=0).all() and (d['bootstrap_lrs']>=0).all()
            np.testing.assert_array_equal(d['counts'].sum(axis=-1),1000);np.testing.assert_array_equal(d['bootstrap_counts'].sum(axis=-1),1000)
            for k in ['fits','bootstrap_fits']:
                assert abs(d[k][...,:6].sum(axis=-1)-1).max()<1e-9 and d[k][...,:6].min()>=-1e-9 and abs(d[k][...,6]).max()<=3+1e-9
            threshold=[np.quantile(d['bootstrap_lrs'][:100,:,:6],cfg['threshold_quantile']),np.quantile(d['bootstrap_lrs'][:100,:,6],cfg['threshold_quantile'])]
            np.testing.assert_array_equal(threshold,d['thresholds'])
            for ti in range(200):
                source=source_sample_indices(bins,d['sizes'],ti,cfg,seed)
                assert [len(s) for s in source]==d['sizes'].tolist()
                for b,s in enumerate(source):assert (bins[s]==b).all()
                weights=np.bincount(np.concatenate(source),minlength=len(y));response=Response(aggregate(powers,index,weights));samples+=1
                q=population.at(0.)[0]@d['truth'];observed=counts_from_uniform(q,observed_uniform(seed,ti,cfg));np.testing.assert_array_equal(observed,d['counts'][ti]);counts+=1
                point=d['fits'][ti];loss=nll(response.at(point[6])[0],point[:6],observed/1000)
                maxloss=max(maxloss,abs(loss-d['actual_loss'][ti]));assert abs(loss-d['actual_loss'][ti])<1e-11;losses+=1
                selected=ti in [0,100] and seed==0
                if selected:
                    independent=scan_profile(observed/1000,response,cfg);scans+=1
                    error=abs(independent-d['actual_loss'][ti]);maxglobal=max(maxglobal,error);assert error<2e-8
                    for par in [5,6]:
                        partial=convex(observed/1000,response.at(0.)[0],cfg) if par==6 else scan_profile(observed/1000,response,cfg,par,float(d['truth'][par]))
                        lr=max(0.,2000*(partial-independent));error=abs(lr-d['actual_lrs'][ti,par]);maxlr=max(maxlr,error);assert error<5e-5;lrscans+=1
                if ti==100 and seed==0:
                    rows=[r for r in allwidths if r['model']==model and int(r['seed'])==seed and int(r['trial'])==ti]
                    for row in rows:
                        par=int(row['parameter'])
                        for method in ['fixed','calibrated']:
                            threshold=1. if method=='fixed' else d['thresholds'][0 if par==5 else 1]
                            for side in ['low','high']:
                                if row[f'{method}_{side}_limited']=='True':continue
                                value=float(row[f'{method}_{side}'])
                                partial=convex(observed/1000,response.at(value)[0],cfg) if par==6 else scan_profile(observed/1000,response,cfg,par,value)
                                lr=2000*(partial-d['actual_loss'][ti]);error=abs(lr-threshold);maxendpoint=max(maxendpoint,error);assert error<2e-4;endpoints+=1
                for ri in range(16):
                    boot=bootstrap_indices(source,ti,ri,cfg,seed)
                    for b,s in enumerate(boot):assert len(s)==d['sizes'][b] and np.isin(s,source[b]).all()
                    weights=np.bincount(np.concatenate(boot),minlength=len(y));rb=Response(aggregate(powers,index,weights));samples+=1
                    prob=response.at(point[6])[0]@point[:6]
                    pseudo=counts_from_uniform(prob,pseudo_uniform(seed,ti,ri,cfg));np.testing.assert_array_equal(pseudo,d['bootstrap_counts'][ti,ri]);counts+=1
                    bp=d['bootstrap_fits'][ti,ri];loss=nll(rb.at(bp[6])[0],bp[:6],pseudo/1000)
                    error=abs(loss-d['bootstrap_loss'][ti,ri]);maxloss=max(maxloss,error);assert error<1e-11;losses+=1
                    # Independent alpha-truth convex subproblem audits every
                    # bootstrap LR without reusing the worker conditional path.
                    if ri==0 or (ti in [0,100] and seed==0):
                        partial=convex(pseudo/1000,rb.at(point[6])[0],cfg)
                        raw=2000*(partial-loss);maxrawnegative=min(maxrawnegative,raw)
                        error=abs(max(0.,raw)-d['bootstrap_lrs'][ti,ri,6]);maxlr=max(maxlr,error);assert error<5e-5;lrscans+=1
                    if selected and ri==0:
                        independent=scan_profile(pseudo/1000,rb,cfg);scans+=1
                        error=abs(independent-loss);maxglobal=max(maxglobal,error);assert error<2e-8
                        partial=scan_profile(pseudo/1000,rb,cfg,5,float(point[5]));lr=max(0.,2000*(partial-independent))
                        error=abs(lr-d['bootstrap_lrs'][ti,ri,5]);maxlr=max(maxlr,error);assert error<5e-5;lrscans+=1
            print(f'checked {model} seed={seed}',flush=True)
    result=dict(sample_instances_replayed=samples,count_instances_replayed=counts,nlls_recomputed=losses,global_scans=scans,conditional_lr_scans=lrscans,endpoint_scans=endpoints,
                maximum_nll_difference=maxloss,maximum_global_nll_difference=maxglobal,maximum_lr_difference=maxlr,maximum_endpoint_error=maxendpoint,maximum_pool_difference=maxpool,
                minimum_independent_raw_lr=maxrawnegative,calibration_thresholds_replayed=True,calibration_test_challenge_evaluated=False,wall_s=time.perf_counter()-tick)
    (out/'independent_checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
