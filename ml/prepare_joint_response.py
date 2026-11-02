#!/usr/bin/env python3
"""Train-only stage63 binning, immutable protocol and numerical/resource pilot."""
from datetime import datetime,timezone
import json
import platform
import time

import numpy as np
import scipy
from scipy.linalg import helmert
import xgboost as xgb

from audited_features import load,configuration
from joint_response import (REPO,OUT,ART,binning,assign,category_counts,histogram,
    TemplateLikelihood,information,begin,resources,save)


def main():
    start=begin();OUT.mkdir(exist_ok=True);ART.mkdir(exist_ok=True)
    assert not (OUT/'protocol.json').exists() and not (ART/'observables.npz').exists(),'Immutable stage63 preparation'
    p=dict(stage=63,starting_commit='d0c8d06',N_selected=1000,parameter='r=relative selected true50-200 vs >=200 strength; f(r)=r*f0/(1-f0+r*f0)',
        EM_initial_probability=1e-6,EM_probability_tolerance=1e-12,EM_active_probability=1e-9,EM_KKT_tolerance=1e-6,EM_maxiter=300,
        simplex_positive_floor=1e-14,simplex_ftol=1e-14,simplex_maxiter=300,
        fraction_bracket_points=17,fraction_xtol=1e-10,fraction_maxiter=200,
        likelihood='conditional data multinomial plus two conditional MC multinomials; fixed-f convex simplex profile via EM and analytic-gradient SLSQP polish for slow boundary convergence, no pseudocount',
        interval='profile delta NLL=.5 with physical f in [0,1]; asymptotic reference, not coverage claim',
        outer_search='fixed17 fraction grid, bounded refinement at every local/end grid minimum, brentq interval crossings; retain diagnostics',
        curvature='efficient joint multinomial Fisher; zero cells are tangent Gaussian approximation; exact profile interval also reported',
        bootstrap_replicates=500,bootstrap_seed=2026110263,
        bootstrap='component-stratified conservative train-source multinomial reweighting; fixed bins/F7/f0; paired curvature sigma ratios, no refits/toys',
        pressures=dict(low_internal=dict(target='true50-100 within true50-200',factors=[.75,1.25]),
                       high_y_mix=dict(target='true>=200, reco pz50-100 and y>=.8 within high component',factors=[.75,1.25])),
        pressure_normalization='renormalize weights separately in true low/high components, preserving original role f and total N; diagnostic, not1sigma',
        acceptance=dict(sigma_ratio_J_over_S_upper95_lt=1.,pooled_nominal_abs_bias_sigma_max=1.,
                        pooled_pressure_abs_bias_sigma_max=1.,J_minus_S_abs_bias_sigma_max=.25),
        acceptance_note='prespecified research tolerances; pooled cal/eval only, all source diagnostics retained; not measured detector tolerances',
        train_template_caveat='F7 was trained on the template train events; source-held-out closure is essential; no independent production certification',
        selected_models=['M_mu','S_scalar','J_joint'],energy_model_fits=0,
        invalid_statistics='separate missing category per representation; otherwise +-infinity implicit end bins, no event deletion',
        formal_job_limit=1,request_cpus=1,request_memory_MB=3000,cpu_budget_s=3600,wall_budget_s=3300,retained_budget_bytes=10000000,
        no_ROOT_RDO_locked_test_or_production=True,
        versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,xgboost=xgb.__version__))
    # Only synthetic arithmetic/counts; zero new physics fits in this pilot.
    mc=np.array([[320.,160.,80.,40.],[30.,100.,250.,820.]])
    f=.12;data=1000*(f*mc[0]/mc[0].sum()+(1-f)*mc[1]/mc[1].sum())
    pilot=[];tick=time.perf_counter();cpu=time.process_time()
    for finite in [False,True]:
        result=TemplateLikelihood(mc,data,p,finite).fit(f)
        assert abs(result['f_hat']-f)<1e-6
        assert result['f_low68']<f<result['f_high68']
        assert result['grid_global_check_pass']
        pilot.append(dict(finite_MC=finite,**result))
    fit_wall=time.perf_counter()-tick;fit_cpu=time.process_time()-cpu
    assert information(mc,f,1000,True)>information(mc,f,1000,False)
    assert information(np.tile([1.,2.,3.],(2,1)),f,1000,True) is None
    # Independent interior Fisher Schur complement, including both simplexes.
    a,b=mc/mc.sum(axis=1)[:,None];q=f*a+(1-f)*b;H=helmert(4,full=False).T
    ja=np.c_[f*H,(1-f)*H];v=a-b
    block=1000*ja.T@np.diag(1/q)@ja
    block[:3,:3]+=mc[0].sum()*H.T@np.diag(1/a)@H
    block[3:,3:]+=mc[1].sum()*H.T@np.diag(1/b)@H
    cross=1000*v@np.diag(1/q)@ja
    expected=1/np.sqrt(1000*np.sum(v*v/q)-cross@np.linalg.solve(block,cross))
    np.testing.assert_allclose(information(mc,f,1000,True),expected,rtol=1e-12)
    # Zero count cell and endpoint fit must remain in the likelihood.
    zero_mc=np.array([[0.,30.,70.],[80.,20.,0.]])
    zero_data=1000*(.1*zero_mc[0]/100+.9*zero_mc[1]/100)
    zr=TemplateLikelihood(zero_mc,zero_data,p,True).fit(.1)
    assert abs(zr['f_hat']-.1)<1e-6
    endpoint=TemplateLikelihood(mc,1000*mc[1]/mc[1].sum(),p,True).fit(f)
    assert endpoint['f_hat']<1e-7 and endpoint['interval_hits_boundary']
    # Only now read protected compact event caches; no new eval physics metrics.
    d,s,x=load();rows=s['row'];role=np.full(len(rows),'unused',dtype='<U6')
    role[d['train_eligible'][rows]]='train';role[d['cal_eligible'][rows]]='cal';role[d['partition'][rows]=='validation']='eval'
    use=role!='unused';rows=rows[use];role=role[use];x=x[use];cfg=configuration()
    with np.load(REPO/'ml/artifacts/stage56/predictions.npz') as z:old={k:z[k] for k in z.files}
    offset=json.loads(str(old['metadata_json']))['offset_log']
    predictions=[];model_checks=[];matrix=xgb.DMatrix(x,feature_names=cfg['features'],nthread=1)
    for j,seed in enumerate(cfg['seeds']):
        model=xgb.Booster(params={'nthread':1});model.load_model(REPO/'ml/artifacts/stage56'/str(seed)/'model.ubj')
        assert model.feature_names==cfg['features'] and json.loads(model.attr('feature_policy'))==cfg
        pred=model.predict(matrix).astype(float);predictions.append(pred)
        for r in ['cal','eval']:
            idx=role==r;np.testing.assert_array_equal(rows[idx],old[r+'_row'])
            np.testing.assert_array_equal(pred[idx],old[r+'_raw_log'][j])
        model_checks.append(dict(seed=seed,readback_predictions_exact=True,feature_names_policy_exact=True))
    M=np.log(d['reco_pz_GeV'][rows]);S=np.mean(predictions,axis=0)+offset;tr=role=='train'
    assert np.isfinite(S).all() and np.isfinite(M).all()
    assert [int((role==r).sum()) for r in ['train','cal','eval']]==[41447,8440,14057]
    truth=d['truth_E_GeV'][rows];low=truth<200
    p.update(f0=float(low[tr].mean()),global_offset_log=float(offset),binning=binning(M[tr],S[tr]))
    bins=assign(M,S,p);counts=category_counts(p)
    for name,index in bins.items():assert index.min()>=0 and index.max()<counts[name]
    p.update(category_counts=counts,frozen_utc=datetime.now(timezone.utc).isoformat(),
        resource_pilot_projection_s=fit_wall/2*300,
        frozen_resource_note='synthetic 4-category profiles only; projected300 curves, not measured physics cost; <=1CPU/3GB one Condor job')
    arrays={k:d[k][rows] for k in ['truth_E_GeV','y_lepton','confirmed','source','group','component']}
    arrays.update(row=rows,role=role,pz=d['reco_pz_GeV'][rows],M=M,S=S,missing=np.isnan(x).any(axis=1),low=low)
    arrays.update({name:index for name,index in bins.items()})
    np.savez_compressed(ART/'observables.npz',**arrays)
    save(OUT/'protocol.json',p)
    save(OUT/'pilot.json',dict(**resources(start),energy_fits=0,synthetic_profile_fits=4,synthetic_main_fits=pilot,
        synthetic_zero_cell_f_hat=zr['f_hat'],synthetic_endpoint_f_hat=endpoint['f_hat'],
        synthetic_two_fit_wall_s=fit_wall,synthetic_two_fit_CPU_s=fit_cpu,
        independent_Fisher_Schur_relative_error=float(abs(information(mc,f,1000,True)/expected-1)),
        F7_models=model_checks,protected_counts={r:int((role==r).sum()) for r in ['train','cal','eval']},
        eligible_missing={r:int(arrays['missing'][role==r].sum()) for r in ['train','cal','eval']},
        train_component_N=[int(low[tr].sum()),int((~low[tr]).sum())],
        train_negative_correction_N=int(((S-M<0)&tr).sum()),cache_bytes=(ART/'observables.npz').stat().st_size))
    print(json.dumps({k:v for k,v in p.items() if k!='binning'},indent=2))


if __name__=='__main__':main()
