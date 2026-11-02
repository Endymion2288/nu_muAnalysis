"""Frozen, readout-only routing and convex log-expert combination for stage58."""
import json
import resource
import time
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

from audited_features import REPO, configuration, load

OUT = REPO / 'workbook/stage58_energy_ml'
ART = REPO / 'ml/artifacts/stage58'
CELLS = ['pz50_100_low', 'pz50_100_high', 'pz100_250_low', 'pz100_250_high']
LOW = ['E50_100', 'E100_200']
COST = {'all': 1.01, 'E200_inf': 1.03, 'pz50_100': 1.03,
        'high_y': 1.03, 'unconfirmed': 1.03}


def io_counters():
    return {k: int(v) for k, v in (line.split(':') for line in Path('/proc/self/io').read_text().splitlines())}


def begin():
    return time.perf_counter(), time.process_time(), io_counters()


def resources(start):
    wall, cpu, io = start
    now = io_counters()
    return dict(wall_s=time.perf_counter()-wall, cpu_s=time.process_time()-cpu,
                peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                proc_io_delta={k: now[k]-io[k] for k in now},
                io_scope='process counters; rchar includes imports/cache, read_bytes is kernel accounting, not EOS physical/network I/O')


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def inputs():
    d, s, x = load()  # Enforces the complete F7 status/domain/dependency policy.
    rows = s['row']; cfg = configuration()
    role = np.full(len(rows), 'unused', dtype='<U6')
    role[d['train_eligible'][rows]] = 'train'
    role[d['cal_eligible'][rows]] = 'cal'
    role[d['partition'][rows] == 'validation'] = 'eval'
    use = role != 'unused'
    selected = rows[use]; xx = x[use].astype(float)
    # No indexing of historical locked-test labels/predictions.
    data = {k: d[k][selected] for k in ['truth_E_GeV', 'y_lepton', 'confirmed', 'source', 'group', 'component']}
    data.update(row=selected, role=role[use], pz=xx[:, cfg['features'].index('ML_mu_pz0_GeV')],
                timing=np.sum(xx[:, [cfg['features'].index(f'Timing{i}_raw_charge') for i in range(4)]], axis=1),
                clusters=np.sum(xx[:, [cfg['features'].index(f'nClusters{i}') for i in range(4)]], axis=1),
                calo=xx[:, cfg['features'].index('ML_calo_total_E_EM_GeV')],
                missing=np.isnan(xx).any(axis=1))
    # Baselines keep the original pz precision used in stage56's reference.
    data['pz'] = d['reco_pz_GeV'][selected]
    raw = np.full(len(selected), np.nan)
    with np.load(REPO/'ml/artifacts/stage56/predictions.npz') as z:
        for name in ['cal', 'eval']:
            take = np.flatnonzero(data['role'] == name)
            np.testing.assert_array_equal(data['row'][take], z[name+'_row'])
            raw[take] = z[name+'_raw_log'].mean(axis=0)
    data['raw_F7'] = raw
    assert [int((data['role'] == r).sum()) for r in ['train', 'cal', 'eval']] == [41447, 8440, 14057]
    return data


def route(pz, timing, boundaries):
    """Only measured pz and signed, strict-sum raw Timing enter the lookup."""
    cell = np.full(len(pz), -1, dtype=int)
    for j, (lo, hi) in enumerate([(50, 100), (100, 250)]):
        good = np.isfinite(pz) & np.isfinite(timing) & (pz >= lo) & (pz < hi)
        cell[good] = 2*j + (timing[good] >= boundaries[j]).astype(int)
    return cell


def masks(d):
    e, p = d['truth_E_GeV'], d['pz']
    result = dict(all=np.ones(len(e), bool), E50_100=(e >= 50) & (e < 100),
                  E100_200=(e >= 100) & (e < 200), E200_inf=e >= 200,
                  pz50_100=(p >= 50) & (p < 100), pz100_250=(p >= 100) & (p < 250),
                  high_y=d['y_lepton'] >= .8, unconfirmed=~d['confirmed'], input_missing=d['missing'])
    for lo, hi in zip([50, 75, 100, 150, 200, 400, 800, 1600, 3200], [75, 100, 150, 200, 400, 800, 1600, 3200, 6400]):
        result[f'E{lo}_{hi}'] = (e >= lo) & (e < hi)
    result['E6400_inf'] = e >= 6400
    return result


def subset(d, take):
    return {k: v[take] for k, v in d.items()}


def experts(pz, raw, offset):
    t0 = np.log(pz)
    return np.column_stack([t0, t0-np.log(.8), raw+offset])


def predict(pz, timing, raw, model, boundaries):
    cell = route(pz, timing, boundaries)
    t = experts(pz, raw, model['offset_log'])
    out = t[:, 2].copy(); active = cell >= 0
    out[active] = np.sum(t[active] * np.asarray(model['weights'])[cell[active]], axis=1)
    return out


def quadratic(a, error, mask, denominator):
    aa, ee = a[mask], error[mask]
    assert len(ee) and denominator > 0
    return aa.T@aa/len(ee)/denominator, aa.T@ee/len(ee)/denominator, float(ee@ee/len(ee)/denominator)


def value(q, v):
    Q, b, c = q
    return float(v@Q@v + 2*b@v + c)


def gradient(q, v):
    return 2*(q[0]@v+q[1])


def optimize(d, cell, family, epsilon):
    """One convex epigraph solve per family/fold; 8 solves total, no scan.

    Numerical lexicographic objective: max low-E relative MSE, then all-event
    relative MSE with fixed epsilon. Feasibility bounds the possible sacrifice
    in primary risk by epsilon*1.01**2, recorded rather than called exact.
    """
    start = time.perf_counter()
    offset = float(np.mean(np.log(d['truth_E_GeV'])-d['raw_F7']))
    t = experts(d['pz'], d['raw_F7'], offset); y = np.log(d['truth_E_GeV'])
    use_experts = [1] if family == 'two' else [0, 1]
    width = len(use_experts); n = 4*width
    a = np.zeros((len(y), n))
    for k in range(4):
        m = cell == k
        a[m, k*width:(k+1)*width] = t[m][:, use_experts]-t[m, 2, None]
    error = t[:, 2]-y; mm = masks(d)
    q = {key: quadratic(a, error, mm[key], np.mean((t[mm[key], 1]-y[mm[key]])**2)) for key in LOW}
    q.update({key: quadratic(a, error, mm[key], np.mean(error[mm[key]]**2)) for key in COST})
    # Nonnegative weights, F7 weight = 1 - sum(other weights) in each cell.
    jac_simplex = np.zeros((4, n+1))
    for k in range(4): jac_simplex[k, k*width:(k+1)*width] = -1
    def constraints(v):
        z, w = v[-1], v[:-1]
        return np.r_[1-w.reshape(4, width).sum(axis=1),
                     [z-value(q[key], w) for key in LOW],
                     [COST[key]**2-value(q[key], w) for key in COST]]
    def jacobian(v):
        w = v[:-1]
        return np.vstack([jac_simplex,
                          *[np.r_[-gradient(q[key], w), 1] for key in LOW],
                          *[np.r_[-gradient(q[key], w), 0] for key in COST]])
    def objective(v): return v[-1]+epsilon*value(q['all'], v[:-1])
    def jac(v): return np.r_[epsilon*gradient(q['all'], v[:-1]), 1.]
    initial = np.r_[np.zeros(n), max(q[key][2] for key in LOW)]
    result = minimize(objective, initial, jac=jac, method='SLSQP', bounds=[(0, 1)]*n+[(0, None)],
                      constraints={'type': 'ineq', 'fun': constraints, 'jac': jacobian},
                      options={'ftol': 1e-13, 'maxiter': 3000})
    assert result.success, result.message
    violation = float(max(0, -np.min(constraints(result.x))))
    assert violation < 1e-8
    multipliers = result.multipliers
    lagrangian_grad = jac(result.x)-multipliers@jacobian(result.x)
    projected = lagrangian_grad.copy()
    projected[:-1][result.x[:-1] < 1e-8] = np.minimum(projected[:-1][result.x[:-1] < 1e-8], 0)
    projected[:-1][result.x[:-1] > 1-1e-8] = np.maximum(projected[:-1][result.x[:-1] > 1-1e-8], 0)
    other = result.x[:-1].reshape(4, width)
    weights = np.zeros((4, 3)); weights[:, use_experts] = other
    weights[:, 2] = 1-other.sum(axis=1)
    assert np.min(weights) >= -1e-8
    # Tiny solver roundoff only; no energy clipping or event removal.
    weights[np.abs(weights) < 1e-12] = 0
    weights /= weights.sum(axis=1, keepdims=True)
    return dict(family=family, offset_log=offset, weights=weights.tolist(), N=len(y),
                objective_max_low_MSE_ratio=max(value(q[key], result.x[:-1]) for key in LOW),
                risk_ratios={key: value(qq, result.x[:-1]) for key, qq in q.items()},
                success=bool(result.success), message=str(result.message), iterations=int(result.nit),
                maximum_constraint_violation=violation, numerical_secondary_epsilon=epsilon,
                projected_KKT_max_abs=float(np.max(np.abs(projected))),
                complementarity_max_abs=float(np.max(np.abs(multipliers*constraints(result.x)))),
                primary_sacrifice_bound=epsilon*1.01**2, solver_wall_s=time.perf_counter()-start)
