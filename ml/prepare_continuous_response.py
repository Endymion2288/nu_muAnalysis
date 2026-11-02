#!/usr/bin/env python3
"""Freeze stage62 train-only design after arithmetic and resource QA; no fits."""
from datetime import datetime, timezone
import json
import platform
import time

import numpy as np
import torch

from continuous_response import (OUT, ART, MODELS, inputs, transform_state, transform,
    pair_indices, pair_matrix, network, training_weights, scan, density, begin, resources, save, subset)


def main():
    start = begin()
    OUT.mkdir(exist_ok=True)
    assert not (OUT/'protocol.json').exists(), 'Do not overwrite the frozen stage62 design'
    torch.set_num_threads(1)
    d = inputs(); tr = subset(d, d['role'] == 'train')
    t = np.log(tr['truth_E_GeV']); state = transform_state(tr['x'])
    x, lp = transform(tr['x'], state)
    u = t-lp
    lo, hi = 50., 6400.
    while np.exp(t.min()) < lo: lo /= 2
    while np.exp(t.max()) > hi: hi *= 2
    octaves = int(round(np.log2(hi/lo)))
    flat_edges = np.linspace(np.log(lo), np.log(hi), octaves+1)
    prior_edges = np.linspace(np.log(lo), np.log(hi), 2*octaves+1)
    prior_counts = np.histogram(t, prior_edges)[0]
    prior_density = (prior_counts+.5)/(len(t)+.5*len(prior_counts))/np.diff(prior_edges)
    p = dict(stage=62, starting_commit='84de80d', seed=2026110262,
        models=MODELS, primary_model=MODELS[0], formal_fit_limit=3,
        architecture='two 64-unit SiLU hidden layers, scalar binary logit; no dropout',
        optimizer='AdamW', learning_rate=.001, weight_decay=.0001, epochs=120, batch_size=1024,
        cpu_threads=1, device='cpu', early_stopping=False, checkpoint='terminal epoch120 only',
        negative_seed=2026110262, negative_multiplier=2, negative_weight=.5,
        pair_rule='independent weighted train X and t marginals with replacement, then u=t-logpz; A/C same indices',
        loss='1.5*mean(weight*BCEWithLogits); positive weights sum N, negative weights sum N',
        feature_policy='F7_pz0_raw_v1', feature_state=state,
        invalid_pz='impute train median logpz, preserve missing mask, use same reference in u; never delete',
        scale_fallback='signed scale=median(abs), positive finite else1; transformed IQR<=1e-8/nonfinite ->1; all missing median ->0',
        u_center=float(np.median(u)), u_scale=float(np.quantile(u,.75)-np.quantile(u,.25)),
        flat_log_edges=flat_edges.tolist(), prior_log_edges=prior_edges.tolist(),
        prior_counts=prior_counts.tolist(), prior_pseudocount_per_bin=.5, prior_log_density=prior_density.tolist(),
        scan_log_grid=np.linspace(np.log(lo), np.log(hi), 129).tolist(), inference_event_batch=128,
        density_rule='linear exp(logit-max) interpolation between129 scan nodes, multiplied by piecewise constant prior; exact piecewise linear-density integrals split at prior edges',
        logscore_rule='log density wrt dlogE under the normalized finite-grid distribution; outside support -infinity',
        crps_rule='exact integral (CDF-1[t>=truth])^2 dt including outside-support distance',
        point_rule='exp(normalized posterior mean logE); raw and one global cal offset per A/B/C; flat-prior raw only',
        quantiles=[.05,.16,.5,.84,.95], mode_logit_tolerance=1e-4,
        reliability_edges=np.linspace(0,1,11).tolist(), low_probability_thresholds_GeV=[100,200],
        numerical_refinement='257-point network scan, same prior, first16 cal rows only; diagnostic, never replaces129 outputs',
        bootstrap_replicates=500, bootstrap_seed=2026110262,
        recovery_upper95_limit=1.05, RMSE_cost_limits=dict(all=1.01,E200_inf=1.03,pz50_100=1.03,high_y=1.03,unconfirmed=1.03),
        tail50_upper95_delta_limit_pp=2, per_job_cpu_budget_s=3000, per_job_wall_budget_s=3300,
        total_cpu_budget_s=10800, request_cpus=1, request_memory_MB=3000,
        retained_budget_bytes=20000000, no_ROOT_RDO_or_locked_test_evaluation=True,
        versions=dict(python=platform.python_version(), numpy=np.__version__, torch=torch.__version__))
    assert p['u_scale'] > 0
    support = []
    for role in ['train','cal','eval']:
        dd = subset(d, d['role'] == role)
        support.append(dict(role=role,N=len(dd['row']),groups=len(np.unique(dd['group'])),missing=int(dd['missing'].sum()),
            invalid_pz=int((~np.isfinite(dd['x'][:,0]) | (dd['x'][:,0]<=0)).sum())))
    # Select curves by fixed row order within train/cal energy bins, not residuals.
    curves = []
    for role in ['train','cal']:
        dd = subset(d, d['role'] == role)
        for low, high in [(50,100),(100,200),(200,800),(800,3200),(3200,np.inf)]:
            idx = np.flatnonzero((dd['truth_E_GeV']>=low)&(dd['truth_E_GeV']<high))
            if len(idx): curves.append(dict(role=role,row=int(dd['row'][idx[0]])))
        idx=np.flatnonzero(dd['missing'])
        if len(idx): curves.append(dict(role=role,row=int(dd['row'][idx[0]])))
    p['curve_rows'] = curves
    weight_rows = []
    pair_rows = []
    for flat in [False,True]:
        w, index = training_weights(t,p,flat)
        ix,it=pair_indices(len(t),w,p['negative_seed'])
        pair_rows.append(dict(training_prior='flat' if flat else 'unit',negative_pairs=len(ix),
            unique_X=int(len(np.unique(ix))),unique_t=int(len(np.unique(it))),accidental_same_row=int((ix==it).sum()),
            positive_weight_sum=float(w.sum()),negative_weight_sum=len(ix)*.5,
            weight_min=float(w.min()),weight_max=float(w.max()),Neff=float(w.sum()**2/(w@w))))
        for k in range(len(flat_edges)-1):
            use=index==k
            weight_rows.append(dict(prior='flat' if flat else 'unit',low_GeV=float(np.exp(flat_edges[k])),high_GeV=float(np.exp(flat_edges[k+1])),
                N=int(use.sum()),groups=len(np.unique(tr['group'][use])),weight_sum=float(w[use].sum())))
    # Pure arithmetic QA: uniform density, nonuniform prior, and discrete ratio algebra.
    q=density(np.zeros((3,129)),p,np.array([np.log(lo),(np.log(lo)+np.log(hi))/2,np.log(hi)]),True)
    width=np.log(hi/lo)
    np.testing.assert_allclose(q['point_raw_log'],(np.log(lo)+np.log(hi))/2,atol=1e-12)
    np.testing.assert_allclose(q['crps_logE'],[width/3,width/12,width/3],atol=1e-12)
    np.testing.assert_allclose(q['pit'],[0,.5,1],atol=1e-12)
    np.testing.assert_allclose(q['log_density'],-np.log(width),atol=1e-12)
    prior_q=density(np.zeros((1,129)),p)
    np.testing.assert_allclose(np.diff(prior_q['probabilities'])[0],(prior_counts+.5)/(len(t)+.5*len(prior_counts)),atol=1e-12)
    joint=np.array([[.1,.2],[.3,.4]])
    prod=joint.sum(axis=1)[:,None]*joint.sum(axis=0)
    np.testing.assert_allclose(np.exp(np.log(joint/prod))*prod,joint,atol=1e-15)
    injected=tr['x'][:3].copy();injected[0,0]=np.nan;injected[1,29]=-1
    injected[2,37]=np.nan
    tx,tlp=transform(injected,state)
    assert np.isfinite(tx).all() and np.isfinite(tlp).all() and tx[0,62]==1
    assert tx[1,62+29]==0 and tx[2,62+37]==1
    np.testing.assert_array_equal(pair_matrix(x,lp,t,np.array([0,1]),np.array([2,3]),p)[:,-1],
        ((t[[2,3]]-lp[[0,1]]-p['u_center'])/p['u_scale']).astype('float32'))
    # Throughput only: backward passes without optimizer/parameter updates.
    torch.manual_seed(p['seed']);model=network(125)
    xx=torch.from_numpy(pair_matrix(x,lp,t,np.arange(1024),np.arange(1024),p))
    before=[v.detach().clone() for v in model.parameters()]
    tick=time.perf_counter();cpu=time.process_time()
    for _ in range(12):
        model.zero_grad(set_to_none=True);model(xx).square().mean().backward()
    backward_wall=(time.perf_counter()-tick)/12;backward_cpu=(time.process_time()-cpu)/12
    assert all(torch.equal(a,b) for a,b in zip(before,model.parameters()))
    pilot_scan=scan(model,x[:129],lp[:129],p)
    split_scan=scan(model,x[:129],lp[:129],p,event_batch=37)
    np.testing.assert_allclose(pilot_scan,split_scan,rtol=1e-5,atol=1e-6)
    tick=time.perf_counter();scan(model,x[:1024],lp[:1024],p)
    scan_wall=time.perf_counter()-tick
    p['frozen_utc']=datetime.now(timezone.utc).isoformat()
    save(OUT/'protocol.json',p)
    save(OUT/'pilot.json',dict(**resources(start),formal_fit_calls=0,optimizer_updates=0,
        train_E_min_GeV=float(np.exp(t.min())),train_E_max_GeV=float(np.exp(t.max())),
        support=support,weight_bins=weight_rows,pair_support=pair_rows,arithmetic_QA_passed=True,
        transformed_dimensions=dict(full=125,mu_only=3),batch_backward_wall_s=backward_wall,
        batch_backward_cpu_s=backward_cpu,scan1024x129_wall_s=scan_wall,
        projected120epoch_backward_s=120*int(np.ceil(3*len(t)/1024))*backward_wall,
        resource_note='pilot has backward but zero optimizer updates; extrapolation excludes AdamW/initialization and is not measured fit cost'))
    print(json.dumps(json.loads((OUT/'pilot.json').read_text()),indent=2))


if __name__=='__main__':main()
