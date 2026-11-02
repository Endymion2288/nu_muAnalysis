#!/usr/bin/env python3
"""Synthetic pilot and immutable stage64 protocol; no new physical contrasts."""
from datetime import datetime,timezone
import json
import platform
import time
import numpy as np
from scipy.linalg import helmert

from response_migration import OUT,REPO,decompose,linear_operator,project,begin,resources,save


def main():
    start=begin();OUT.mkdir(exist_ok=True);assert not (OUT/'protocol.json').exists()
    p=dict(stage=64,starting_commit='0c77e96',truth_E_edges_GeV=[50,100,200,400,800,1600,3200,6400],
        production_components=['pi','k','charm'],statistics=['M_mu','S_scalar'],truth_components=['low','high'],
        reference='train, shared k: mixture=(wR-wT)*RT; conditional=wR*(RR-RT); unmatched=original JR-JT outside shared support',
        strata='true E coarse bin x production component; explicit under/overflow; diagnostic truth, never deployment input',
        fixed_N_selected=1000,conservation_tolerance=1e-12,
        eigen_relative_cut=1e-12,eigen_absolute_cut=1e-18,
        operator='fixed nominal train a,b and role actual f_true; finite-MC covariance of stage63; L=v^T V+/(v^T V+v)',
        bootstrap_replicates=500,bootstrap_seeds=dict(train=2026110264,cal=2026110265,eval=2026110266),
        bootstrap='independent component-stratified source multinomial draws by role; same train draw reused for cal/eval, M/S paired; fixed f_true and nominal linear operator; recompute shared support each draw',
        bootstrap_scope='conditional on fitted F7, bins and central operator; no retraining, full-lineage guarantee, detector/interaction systematics or coverage claim',
        thin_support_flag='N<20 or conservative source count<3; descriptive only, no event/stratum exclusion',
        norms='half L1 of each signed vector; only total response difference is a TV distance; term norms need not add',
        ratio_policy='no attribution percentages: signed contributions and intervals retained with cancellations',
        profiles=0,energy_model_fits=0,F7_inferences=0,ROOT_RDO_production=0,coverage_toys=0,
        jobs=1,request_cpus=1,request_memory_MB=2000,cpu_budget_s=600,wall_budget_s=600,retained_budget_bytes=5000000,
        input_cache='ml/artifacts/stage63/observables.npz',versions=dict(python=platform.python_version(),numpy=np.__version__))
    # Known pure mixture, pure conditional and unmatched-support cases.
    train=np.array([[[30.,10.,0.],[0.,10.,10.],[0.,0.,0.]],[[10.,10.,0.],[0.,10.,30.],[0.,0.,0.]]])
    mixture=train*np.array([2.,.5,1.])[None,:,None]
    dm=decompose(train,mixture);assert np.max(abs(dm['vectors'][:,1:3]))==0
    conditional=train[:,:,::-1].copy();dc=decompose(train,conditional)
    assert np.max(abs(dc['vectors'][:,[0,2]]))==0
    unmatched=conditional.copy();unmatched[:,1]=0;unmatched[:,2]=[3,4,5]
    du=decompose(train,unmatched);assert np.all(du['unmatched_mass']>0)
    assert max(d['conservation_error'] for d in [dm,dc,du])<p['conservation_tolerance']
    rng=np.random.default_rng(64);t=rng.poisson(4,size=(2,27,17)).astype(float);r=rng.poisson(4,size=t.shape).astype(float)
    t[:,3]=0;r[:,4]=0;t[:,:,-1]=0;r[:,:,-1]=0
    op,diag=linear_operator(t.sum(axis=1),.1)
    # Independent reduced-space covariance solve with simplex tangent basis.
    mc=t.sum(axis=1);total=mc.sum(axis=1);a,b=mc/total[:,None];q=.1*a+.9*b;use=q>0;H=helmert(int(use.sum()),full=False).T
    cov=(np.diag(q[use])-np.outer(q[use],q[use]))/1000
    cov+=.01*(np.diag(a[use])-np.outer(a[use],a[use]))/total[0]+.81*(np.diag(b[use])-np.outer(b[use],b[use]))/total[1]
    solved=H@np.linalg.solve(H.T@cov@H,H.T@(a-b)[use]);solved/=solved@(a-b)[use]
    np.testing.assert_allclose(op[use],solved,rtol=1e-11,atol=1e-11)
    tick=time.perf_counter();cpu=time.process_time();worst=0.
    for _ in range(100):
        d=decompose(t,r);v=project(d['vectors'],op,.1)
        worst=max(worst,d['conservation_error'],float(np.max(abs(v[:,:3].sum(axis=1)-v[:,3]))))
    wall=time.perf_counter()-tick;cpu=time.process_time()-cpu
    assert worst<1e-12
    prior=json.loads((REPO/'workbook/stage63_energy_ml/protocol_v2.json').read_text())
    p.update(category_counts={k:prior['category_counts'][k] for k in p['statistics']},
        frozen_utc=datetime.now(timezone.utc).isoformat(),
        pilot_projected_2004_decompositions_wall_s=wall/100*2004)
    save(OUT/'pilot.json',dict(**resources(start),synthetic_decompositions=103,
        timing_100_decompositions_wall_s=wall,timing_100_decompositions_CPU_s=cpu,
        maximum_conservation_error=worst,independent_operator_max_abs_error=float(max(abs(op[use]-solved))),
        pure_mixture_conditional_unmatched_QA_pass=True,operator_unit_contrast_error=diag['unit_contrast_error']))
    save(OUT/'protocol.json',p);print(json.dumps(p,indent=2))


if __name__=='__main__':main()
