#!/usr/bin/env python3
"""Freeze stage58 routing/folds/protocol before inspecting combination outcomes."""
from datetime import datetime, timezone
import numpy as np

from expert_combination import (OUT, REPO, CELLS, COST, LOW, begin, resources, inputs,
                                subset, route, masks, save, experts, predict)
from train_bdt import write_table

start = begin(); OUT.mkdir(exist_ok=True)
assert not (OUT/'protocol.json').exists(), 'Never change the protocol after outcomes'
d = inputs(); train = d['role'] == 'train'; cal = d['role'] == 'cal'
boundaries = []
for lo, hi in [(50,100), (100,250)]:
    m = train & (d['pz'] >= lo) & (d['pz'] < hi) & np.isfinite(d['timing'])
    boundaries.append(float(np.median(d['timing'][m])))
# Greedy source split uses only component and group event counts, never labels.
folds = {}; component_load = np.zeros((3,3), int); total = np.zeros(3,int)
for c, comp in enumerate(['pi','k','charm']):
    groups = [(str(g), int(np.sum(cal & (d['group'] == g)))) for g in np.unique(d['group'][cal & (d['component'] == comp)])]
    for group, count in sorted(groups, key=lambda p: (-p[1], p[0])):
        fold = min(range(3), key=lambda f: (component_load[c,f], total[f], f))
        folds[group] = fold; component_load[c,fold] += count; total[fold] += count
protocol = dict(stage=58, frozen_utc=datetime.now(timezone.utc).isoformat(), starting_commit='4a55cf5',
                feature_version='F7_pz0_raw_v1', cell_names=CELLS, timing_medians_pC=boundaries,
                timing_sum='float64 sum of cleaned float32 Timing0..3 raw; any missing propagates; signed values retained',
                routing='50<=pz<100 and 100<=pz<250; timing < median is low, >= median high; all others F7',
                fold_by_group=folds, folds_method='component-wise greedy source event-count balance, pi/k/charm; no truth or residual',
                families=['two','three'], combination_optimization_calls=8, new_energy_model_fits=0,
                objective='min max low-E log-MSE / pz0-over0.8 MSE; numerical lexicographic all-event risk tie break',
                low_groups=LOW, RMSE_cost_limits=COST, numerical_secondary_epsilon=1e-6,
                primary_sacrifice_upper_bound=1e-6*1.01**2,
                numerical_note='one SLSQP call per family/fold; fixed epsilon is numerical tie tolerance, not a scanned tradeoff; primary is approximate within the explicit bound',
                optimizer='SLSQP analytic quadratic gradients, ftol=1e-13, maxiter=3000, feasibility tolerance=1e-8',
                bootstrap_replicates=500, bootstrap_seed=2026110258,
                recovery_ratio_upper95_max=1.05, breakthrough_gain_low95_min_pct=0,
                maximum_key_tail50_increase_pp=2, locked_test_evaluation=False,
                forbidden='no new ROOT/RDO, flux toy, energy fits, threshold/gate/family/lambda scans, or eval tuning')
# Small implementation QA: boundaries, signed sums, defaults, and expert vertices.
p = np.array([50.,99.,100.,249.,250.,60.]); q = np.array([boundaries[0]-1,boundaries[0],boundaries[1]-1,boundaries[1],0,np.nan])
np.testing.assert_array_equal(route(p,q,boundaries), [0,1,2,3,-1,-1])
assert np.isnan(np.sum([1.,np.nan])) and np.sum([-3.,1.]) == -2
for j in range(3):
    weights = np.zeros((4,3)); weights[:,j]=1
    model=dict(offset_log=.1,weights=weights.tolist())
    actual=predict(p,q,np.log(p)+.3,model,boundaries)
    expected=experts(p,np.log(p)+.3,.1)[:,j];expected[4:]=np.log(p[4:])+.4
    np.testing.assert_allclose(actual,expected,rtol=0,atol=1e-14)
save(OUT/'protocol.json',protocol)
records=[];cell=route(d['pz'],d['timing'],boundaries);mm=masks(d)
for role in ['train','cal','eval']:
    for fold in ([-1,0,1,2] if role=='cal' else [-1]):
        base=d['role']==role
        if fold>=0: base &= np.array([folds.get(str(g),-1)==fold for g in d['group']])
        for name,m in {**{k:mm[k] for k in ['all']+LOW+list(COST)[1:]},**{n:cell==i for i,n in enumerate(CELLS)},'default_F7':cell<0}.items():
            use=base&m
            records.append(dict(role=role,fold=fold,stratum=name,N=int(use.sum()),groups=len(np.unique(d['group'][use])),
                                sources=len(np.unique(d['source'][use])),pi_N=int((use&(d['component']=='pi')).sum()),
                                k_N=int((use&(d['component']=='k')).sum()),charm_N=int((use&(d['component']=='charm')).sum())))
write_table(OUT/'support_before_optimization.tsv',records)
save(OUT/'prepare_resources.json',dict(**resources(start),small_sample_checks='routing boundaries/defaults, signed/NaN strict sum, three expert vertices',
                                     input_file_bytes={str(p.relative_to(REPO)):p.stat().st_size for p in [REPO/'ntuples/energy_ml_stage55/dataset.npz',REPO/'ntuples/energy_ml_stage56/readout.npz',REPO/'ml/artifacts/stage56/predictions.npz']}))
print(protocol)
