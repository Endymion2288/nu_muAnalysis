#!/usr/bin/env python3
"""Independent fixed-model inference, density arithmetic and cohort QA, no refits."""
import json
import numpy as np
import torch
from scipy.special import expit

from continuous_response import (OUT, ART, MODELS, inputs, transform_state, transform,
    training_weights, pair_indices, network, scan, density, begin, resources, save, subset)
from audited_features import load


def independent_logits(x, lp, p, state):
    grid=np.asarray(p['scan_log_grid'])
    u=((grid[None,:]-lp[:,None]-p['u_center'])/p['u_scale']).ravel()
    a=np.column_stack([np.repeat(x,len(grid),axis=0),u]).astype(float)
    for prefix in ['0','2','4']:
        a=a@state[prefix+'.weight'].numpy().T+state[prefix+'.bias'].numpy()
        if prefix!='4':a=a*expit(a)
    return a.reshape(len(x),len(grid))


def independent_density(logits,p,y):
    """Three-point Gaussian integration of scalar piecewise polynomials.

    Include truth among knots: each CRPS integrand is then a quartic with a
    constant target indicator. No stage62 density/CDF/moment code is reused.
    """
    grid=np.array(p['scan_log_grid']);edges=np.array(p['prior_log_edges'])
    knots=np.unique(np.r_[grid,edges,y]);knots=knots[(knots>=grid[0])&(knots<=grid[-1])]
    left,right=knots[:-1],knots[1:];width=right-left
    logits=np.asarray(logits,float)
    likelihood=np.exp(logits-np.max(logits));prior=np.array(p['prior_log_density'])
    gp,gw=np.polynomial.legendre.leggauss(3)
    at=(left+right)[:,None]/2+width[:,None]*gp/2
    pr=prior[np.clip(np.searchsorted(edges,(left+right)/2)-1,0,len(prior)-1)]
    rr=np.interp(at,grid,likelihood)*pr[:,None]
    mass=(rr*gw*width[:,None]/2).sum(axis=1);z=mass.sum()
    mean=(rr*at*gw*width[:,None]/2).sum()/z
    cumulative=np.r_[0,np.cumsum(mass)]/z
    # Integrate each linear density from the interval's left edge to each node.
    qleft=np.interp(left,grid,likelihood)*pr/z
    qright=np.interp(right,grid,likelihood)*pr/z
    slope=(qright-qleft)/width
    dx=at-left[:,None]
    f=cumulative[:-1,None]+qleft[:,None]*dx+.5*slope[:,None]*dx*dx
    crps=(((f-(at>=y))**2)*gw*width[:,None]/2).sum()+max(0,grid[0]-y,y-grid[-1])
    py=prior[np.clip(np.searchsorted(edges,y,side='right')-1,0,len(prior)-1)]
    log_density=float(np.log(np.interp(y,grid,likelihood)*py/z)) if grid[0]<=y<=grid[-1] else -np.inf
    return mean,crps,log_density


def main():
    start=begin();torch.set_num_threads(1)
    p=json.loads((OUT/'protocol.json').read_text());d=inputs();tr=subset(d,d['role']=='train')
    assert transform_state(tr['x'])==p['feature_state']
    for r1,r2 in [('train','cal'),('train','eval'),('cal','eval')]:
        assert not set(d['group'][d['role']==r1])&set(d['group'][d['role']==r2])
    with np.load(OUT.parents[1]/'ml/artifacts/stage60/predictions.npz') as z:reference={k:z[k] for k in z.files}
    records=[]
    for name in MODELS:
        result=json.loads((OUT/name/'fit.json').read_text())
        assert result['formal_fit_calls']==1 and result['epochs']==120 and result['status']=='completed'
        assert np.isfinite([r['weighted_binary_loss'] for r in result['history']]).all()
        saved=torch.load(ART/name/'model.pt',map_location='cpu',weights_only=True)
        model=network(saved['input_dim']);model.load_state_dict(saved['state_dict']);model.eval()
        with np.load(ART/name/'predictions.npz') as z:a={k:z[k] for k in z.files}
        weight,_=training_weights(np.log(tr['truth_E_GeV']),p,name=='B_full_flat')
        ix,it=pair_indices(len(weight),weight,p['negative_seed'])
        assert len(np.unique(ix))==result['negative_unique_X'] and len(np.unique(it))==result['negative_unique_t']
        inference_error=0.;quadrature_errors=[]
        for role in ['cal','eval']:
            dd=subset(d,d['role']==role)
            np.testing.assert_array_equal(dd['row'],a[role+'_row']);np.testing.assert_array_equal(dd['row'],reference[role+'_row'])
            assert np.isfinite(a[role+'_point_raw_log']).all()
            assert (a[role+'_crps_logE']>=-1e-12).all()
            assert (a[role+'_probabilities']>=-1e-12).all() and (a[role+'_probabilities']<=1+1e-12).all()
            assert (np.diff(a[role+'_probabilities'],axis=1)>=-1e-12).all()
            assert np.max(a[role+'_normalization_error'])<1e-12
            if role=='cal':
                off=float(np.mean(np.log(dd['truth_E_GeV'])-a['cal_point_raw_log']))
                assert off==result['global_cal_offset_log']
            np.testing.assert_array_equal(a[role+'_point_cal_log'],a[role+'_point_raw_log']+off)
            indices=np.unique(np.r_[np.arange(8),np.flatnonzero(dd['missing'])])
            rx,lp=transform(dd['x'][indices],p['feature_state'],name=='C_mu_unit')
            logits=scan(model,rx,lp,p)
            independent=independent_logits(rx,lp,p,saved['state_dict'])
            inference_error=max(inference_error,float(np.max(abs(logits-independent))))
            np.testing.assert_allclose(logits,independent,rtol=1e-4,atol=2e-5)
            summary=density(logits,p,np.log(dd['truth_E_GeV'][indices]))
            for key in ['point_raw_log','log_density','crps_logE','probabilities']:
                np.testing.assert_allclose(summary[key],a[role+'_'+key][indices],rtol=0,atol=3e-6)
            reverse=np.arange(len(indices))[::-1]
            np.testing.assert_allclose(scan(model,rx[reverse],lp[reverse],p),logits[reverse],rtol=0,atol=3e-6)
            for j in range(min(4,len(indices))):
                expected=independent_density(logits[j],p,np.log(dd['truth_E_GeV'][indices[j]]))
                got=[summary[k][j] for k in ['point_raw_log','crps_logE','log_density']]
                np.testing.assert_allclose(got,expected,rtol=0,atol=1e-10)
                quadrature_errors.append(float(np.max(abs(np.asarray(got)-expected))))
        records.append(dict(model=name,epochs=120,independent_logit_max_abs_error=inference_error,
            independent_Gaussian_quadrature_max_abs_error=max(quadrature_errors),identities_offsets_missing_preserved=True))
    _,_,full=load();assert int(np.isnan(full).any(axis=1).sum())==42
    save(OUT/'validation.json',dict(**resources(start),formal_fits_checked=3,additional_fits=0,
        train_transforms_exact=True,protected_source_partitions_preserved=True,full_missing_N=42,
        eligible_missing_by_role={r:int(d['missing'][d['role']==r].sum()) for r in ['train','cal','eval']},
        inference_and_density_QA_passed=True,models=records))
    print(json.dumps(json.loads((OUT/'validation.json').read_text()),indent=2))


if __name__=='__main__':main()
