#!/usr/bin/env python3
"""Replay stage27 independent samples, probabilities, counts and global profiles."""
import json
import time
from pathlib import Path

import numpy as np

from check_profile_response import convex, scan_profile
from closure import load_data, read_table
from independent_response import (LAYERS, aggregate, basis, config, count_uniforms,
                                  local_covariance, sample_weights)
from profile_response import Response, nll
from source_response import counts_from_uniform


def main():
    tick=time.perf_counter();root=Path(__file__).resolve().parents[1];cfg=config(root);out=root/'workbook/stage27_energy_ml'
    intervals=read_table(out/'intervals.tsv');counts_replayed=0;samples_checked=0;fits_checked=0;global_scans=0;lr_scans=0;endpoint_scans=0
    max_loss=0.;max_global=0.;max_lr=0.;max_endpoint=0.;cov_error=0.;largest_simplex=0.;max_pool=0.;max_cov_replay=0.
    for model,spec in cfg['models'].items():
        for seed in spec['seeds']:
            local_cfg={**cfg,'models':{model:{**spec,'seeds':[seed]}}}
            y,bins,gi,groups,fold,predictions=load_data(root,local_cfg,model,False)
            powers,index,logs,reco=basis(y,bins,predictions[0],cfg)
            pool=aggregate(powers,index,np.ones(len(y)));population=Response(pool)
            truth=np.bincount(bins,minlength=6)/len(y);sizes=np.bincount(bins,minlength=6)//2
            data=[]
            for ai,alpha in enumerate(cfg['alphas']):
                with np.load(root/f'ml/artifacts/stage27/{model}/seed_{seed}/alpha_{ai}/independent_inference.npz') as z:
                    d={k:z[k] for k in z.files}
                np.testing.assert_array_equal(d['pool'][0],pool[0]);np.testing.assert_array_equal(d['truth'],truth)
                max_pool=max(max_pool,float(abs(d['pool']-pool).max()))
                np.testing.assert_allclose(d['pool'],pool,atol=1e-12,rtol=1e-13)
                np.testing.assert_array_equal(d['sizes'],sizes)
                cov,info=local_covariance(population,truth,alpha,bins,reco,logs,sizes,cfg)
                max_cov_replay=max(max_cov_replay,float(abs(cov-d['local_covariance']).max()))
                np.testing.assert_allclose(cov,d['local_covariance'],atol=1e-12,rtol=1e-11)
                # A different expanded weighted-second-moment expression checks
                # the response-probability covariance for all injected alpha.
                R=population.at(alpha)[0];C=np.zeros((10,10))
                for b in range(6):
                    sel=bins==b;w=np.exp(alpha*logs[sel]);v=np.bincount(reco[sel],weights=w*w,minlength=10)/len(w)
                    C+=truth[b]**2/sizes[b]*(np.diag(v)-np.outer(v,R[:,b])-np.outer(R[:,b],v)+v.sum()*np.outer(R[:,b],R[:,b]))/w.mean()**2
                error=float(abs(C-np.array(info['probability_mc_covariance'])).max());cov_error=max(cov_error,error);assert error<1e-15
                assert np.isfinite(d['fits']).all() and np.isfinite(d['lrs']).all()
                assert d['statuses'].all() and (d['lrs']>=0).all()
                largest_simplex=max(largest_simplex,float(abs(d['fits'][...,:6].sum(axis=-1)-1).max()))
                assert d['fits'][...,:6].min()>=-1e-9 and abs(d['fits'][...,6]).max()<=3+1e-9
                data.append(d)
            for ti in range(cfg['replicates']):
                weights=[sample_weights(bins,sizes,side,ti,cfg) for side in range(2)]
                for w in weights:
                    np.testing.assert_array_equal(np.bincount(bins,weights=w,minlength=6),sizes);samples_checked+=1
                responses=[population]+[Response(aggregate(powers,index,w)) for w in weights]
                for ai,alpha in enumerate(cfg['alphas']):
                    d=data[ai];u=count_uniforms(seed,ai,ti,cfg)
                    for li in range(4):
                        response=responses[1] if li in [1,3] else population
                        mean=responses[2] if li in [2,3] else population
                        q=mean.at(alpha)[0]@truth
                        np.testing.assert_allclose(q,d['qs'][ti,li],atol=1e-15,rtol=0)
                        counts=counts_from_uniform(q,u);np.testing.assert_array_equal(counts,d['counts'][ti,li]);counts_replayed+=1
                        for ci,observed in enumerate([q,counts/1000]):
                            for mi in range(2):
                                point=d['fits'][ti,li,ci,mi]
                                loss=nll(response.at(point[6])[0],point[:6],observed)
                                difference=abs(loss-d['losses'][ti,li,ci,mi]);max_loss=max(max_loss,difference);assert difference<1e-11;fits_checked+=1
                            expected=max(0.,2000*(d['losses'][ti,li,ci,0]-d['losses'][ti,li,ci,1]))
                            assert abs(expected-d['lrs'][ti,li,ci,6])<1e-9
                            selected=seed==0 and ti==0 and (ai==1 or (li in [1,3] and ci==1))
                            if selected:
                                independent=scan_profile(observed,response,cfg);global_scans+=1
                                error=abs(independent-d['losses'][ti,li,ci,1]);max_global=max(max_global,error);assert error<2e-8,(model,ai,li,ci,error)
                                partial=scan_profile(observed,response,cfg,5,float(truth[5]));lr_scans+=1
                                expected=max(0.,2000*(partial-independent));error=abs(expected-d['lrs'][ti,li,ci,5]);max_lr=max(max_lr,error);assert error<5e-5
                            # Fixed endpoint positions, with an independent
                            # alpha grid for the high fraction and convex
                            # fit for alpha. No endpoint selection by result.
                            if seed==0 and ti==0 and ai==1 and ci==1:
                                rows=[r for r in intervals if r['model']==model and int(r['seed'])==seed and int(r['trial'])==ti and r['layer']==LAYERS[li]]
                                assert len(rows)==2
                                for row in rows:
                                    p=int(row['parameter'])
                                    for side in ['low','high']:
                                        if row[side+'_limited']=='True':continue
                                        value=float(row[side])
                                        loss=convex(observed,response.at(value)[0],cfg) if p==6 else scan_profile(observed,response,cfg,p,value)
                                        lr=2000*(loss-d['losses'][ti,li,ci,1]);error=abs(lr-1);max_endpoint=max(max_endpoint,error);assert error<2e-4;endpoint_scans+=1
            print(f'checked {model} seed={seed}',flush=True)
    result=dict(mc_sample_instances_replayed=samples_checked,unique_mc_rng_samples=2*cfg['replicates'],
                counting_instances_replayed=counts_replayed,fit_nlls_recomputed=fits_checked,global_profiles_scanned=global_scans,
                highest_fraction_truth_lrs_scanned=lr_scans,interval_endpoints_scanned=endpoint_scans,
                maximum_nll_replay_difference=max_loss,maximum_global_nll_difference=max_global,
                maximum_fraction_lr_difference=max_lr,maximum_endpoint_lr_difference=max_endpoint,
                maximum_covariance_expansion_difference=cov_error,maximum_simplex_error=largest_simplex,
                maximum_pool_moment_replay_difference=max_pool,maximum_local_covariance_replay_difference=max_cov_replay,
                all_alpha_lrs_recomputed=True,calibration_test_challenge_evaluated=False,wall_s=time.perf_counter()-tick)
    (out/'independent_checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
