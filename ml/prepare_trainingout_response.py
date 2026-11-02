#!/usr/bin/env python3
"""Freeze stage66 after synthetic derivative, orthogonal and singular QA."""
from datetime import datetime,timezone
import json
import time
import numpy as np

from trainingout_response import OUT,REPO,directions,covariance,local_information,begin,resources,save


def main():
    start=begin();OUT.mkdir(exist_ok=True);assert not (OUT/'protocol.json').exists()
    p=dict(stage=66,starting_commit='f6e80d7',alpha=0.,energy_scale_GeV=400,N_selected=1000,
        covariance_relative_cut=1e-12,covariance_absolute_cut=1e-18,direction_information_min=1e-12,
        normalized_rank_cut=1e-10,fraction_boundary_tolerance=1e-8,numerical_tolerance=1e-8,
        derivative_difference_step=1e-5,bootstrap_replicates=500,
        bootstrap_seeds=dict(cal=2026110366,eval=2026110367),
        parameters=['selected low fraction f','selected high component power tilt alpha'],
        high_spectrum='b_alpha proportional to (E/400GeV)^alpha within selected high component; only alpha0 local derivatives',
        bootstrap='500 component-stratified independent cal/eval conservative source draws, M/S paired; fixed nominal eval f_true; re-estimate cal a/b/C/V/operators, eval response and support every draw; no new train draws',
        singular='rank<2, zero direction or f within1e-8 boundary: no free precision/regular projection; keep NaN in NPZ and null in JSON, report invalid counts and finite-only quantiles together; no ridge, prior or pseudocount',
        uncertainty='local tangent multinomial Fisher, including finite MC at alpha0; source intervals conditional on fitted F7/bins, no training/lineage/detector/calibration coverage guarantee',
        residual='full signed vector, half-L1 and sqrt(r^T V+ r); no goodness-of-fit p value, no nonlinear correction/fit or clipping unphysical linear extrapolation',
        formal_jobs=1,request_cpus=1,request_memory_MB=3000,cpu_budget_s=600,wall_budget_s=600,retained_budget_bytes=5000000,
        energy_fits=0,F7_inferences=0,ROOT_RDO_production=0,nonlinear_spectrum_profiles=0,coverage_toys=0,
        input_cache='ml/artifacts/stage63/observables.npz',template_role='cal',target_role='eval',
        f_eval=1114/14057,expected_template_low_high=[841,7599],expected_target_low_high=[1114,12943],
        reference='cal; shared k mixture=(w_eval-w_cal)*R_cal; conditional=w_eval*(R_eval-R_cal); unmatched=original J_eval-J_cal outside shared k',
        support='all27 coarseE x pi/k/charm strata and both components; no pruning or pseudocount; record cal/eval source counts and per-draw zero/shared frequencies and ESS',
        comparison='read stage65 train-to-eval Fisher/projection/intervals only, no new train resampling; no reversed or merged template',
        independent_QA_bootstrap_indices=[0,249,499],comparison_tolerance=1e-8)
    # Exact derivative of a normalized exponential tilt on synthetic events.
    E=np.array([200.,250.,400.,600.,1000.,2000.]);bins=np.array([0,0,1,1,2,3]);u=np.log(E/400)
    high=np.bincount(bins,minlength=4).astype(float);hlog=np.bincount(bins,weights=u,minlength=4)
    mc=np.array([[80.,15.,4.,1.],high]);D,C,_=directions(mc,hlog,.1);step=p['derivative_difference_step']
    def tilt(alpha):
        w=np.exp(alpha*u);return np.bincount(bins,weights=w,minlength=4)/w.sum()
    difference=(tilt(step)-tilt(-step))/(2*step);error=float(max(abs(C-difference)))
    assert error<1e-9 and abs(C.sum())<1e-12
    # Change of centering scale must not change C.
    _,other,_=directions(mc,np.bincount(bins,weights=np.log(E/1000),minlength=4),.1)
    np.testing.assert_allclose(C,other,rtol=0,atol=1e-12)
    # Orthogonal / exactly collinear / absent hardness directions.
    mc=np.array([[40.,20.,10.,30.],[10.,20.,30.,40.]]);f=.1
    W=np.linalg.pinv(covariance(mc,f,1000,True),hermitian=True,rcond=1e-12)
    v=mc[0]/100-mc[1]/100;c=np.array([1.,-1.,1.,-1.]);c-=v*(v@W@c)/(v@W@v)
    orth=local_information(mc,100*c,f,p)[0]
    assert orth['regular'] and abs(orth['sigma_f_cost_ratio']-1)<1e-10
    collinear=local_information(mc,100*v,f,p)[0];zero=local_information(mc,np.zeros(4),f,p)[0]
    assert not collinear['regular'] and collinear['sigma_f_free'] is None
    assert not zero['regular'] and zero['sigma_alpha'] is None
    boundary=local_information(mc,100*c,0.,p)[0];assert not boundary['regular']
    tick=time.perf_counter();cpu=time.process_time()
    for _ in range(100):local_information(mc,100*c,f,p)
    wall=time.perf_counter()-tick;cpu=time.process_time()-cpu
    old=json.loads((REPO/'workbook/stage64_energy_ml/protocol.json').read_text())
    p.update({k:old[k] for k in ['truth_E_edges_GeV','production_components','category_counts']})
    p.update(frozen_utc=datetime.now(timezone.utc).isoformat(),synthetic_projected_2004_Fisher_wall_s=wall/100*2004)
    save(OUT/'pilot.json',dict(**resources(start),derivative_max_abs_error=error,orthogonal=orth,
        collinear=collinear,zero_direction=zero,boundary=boundary,
        synthetic_100_Fisher_wall_s=wall,synthetic_100_Fisher_CPU_s=cpu,synthetic_checks_pass=True))
    save(OUT/'protocol.json',p);print(json.dumps(p,indent=2))


if __name__=='__main__':main()
