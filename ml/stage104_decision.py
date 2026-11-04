"""One fixed-density, two-cost decision experiment; numerical work only in batch."""
import csv
import json
import multiprocessing as mp
import resource
import time
from pathlib import Path

import numpy as np
from scipy.optimize import minimize
from scipy.special import logsumexp, ndtr
from scipy.stats import norm

from report_resplit_energy import incoming_draws, metrics
from stage99_report import masks
from support_augmentation import arrays, begin, resources, save, table

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage104_energy_ml'
CACHE = ROOT/'ntuples/energy_ml_stage104'
LAYERS = ['E50_100', 'E100_200', 'all', 'E200_inf', 'pz50_100',
          'pz50_100_trueE200', 'high_y', 'unconfirmed']
PROTECT = dict(all=1.01, E200_inf=1.03, pz50_100=1.03,
               pz50_100_trueE200=1.03, high_y=1.03, unconfirmed=1.03)
G = None


def interval(v):
    v = np.asarray(v)
    return [float(x) for x in np.quantile(v[np.isfinite(v)], [.025, .975])]


def load(codes):
    full = arrays(ROOT/'ntuples/energy_ml_stage94/evaluation_input.npz')
    d = {k: v[np.isin(full['role'], codes)] for k, v in full.items()}
    raw = arrays(ROOT/'ml/artifacts/stage94/point_predictions.npz')
    head = arrays(ROOT/'ml/artifacts/stage94/MDN_heads.npz')
    ir = np.searchsorted(raw['row'], d['row'])
    ih = np.searchsorted(head['row'], d['row'])
    np.testing.assert_array_equal(raw['row'][ir], d['row'])
    np.testing.assert_array_equal(head['row'][ih], d['row'])
    cfg = json.loads((ROOT/'workbook/stage99_energy_ml/calibration.json').read_text())
    anchor = np.log(d['pz']/.8)
    ww, mm, ss = [], [], []
    for key in sorted(set(head)-{'row'}):
        h = head[key][ih].astype(float)
        ww.append(np.exp(h[:, :3]-logsumexp(h[:, :3], axis=1)[:, None])/3)
        mm.append(h[:, 3:6]+anchor[:, None])
        ss.append(.05+np.logaddexp(0, h[:, 6:9]))
    w, mu, sig = np.column_stack(ww), np.column_stack(mm), np.column_stack(ss)
    assert w.shape[1] == 9
    mean = (w*mu).sum(1)
    old = raw['E_ensemble'][ir].astype(float)+cfg['b_fixed']
    discrepancy = float(np.max(abs(mean+cfg['b_fixed']-old)))
    assert discrepancy < 3e-6
    mu = mean[:, None]+cfg['b_fixed']+cfg['T']*(mu-mean[:, None])
    sig *= cfg['T']
    np.testing.assert_allclose(w.sum(1), 1, atol=1e-14)
    np.testing.assert_allclose((w*mu).sum(1), mean+cfg['b_fixed'], atol=1e-14, rtol=0)
    return d, old, (w, mu, sig), cfg, discrepancy


def normal_moments(mu, sig, lo, hi):
    a, b = (lo-mu)/sig, (hi-mu)/sig
    # Use the survival representation in the positive tail to avoid CDF subtraction.
    p = np.where(a >= 0, ndtr(-a)-ndtr(-b), ndtr(b)-ndtr(a))
    phi = lambda z: np.exp(-.5*z*z)/np.sqrt(2*np.pi)
    return p, mu*p+sig*(phi(a)-phi(b))


def moments(distribution):
    w, mu, sig = distribution
    mean = (w*mu).sum(1)
    pp, mm = [], []
    for low, high in [(50, 100), (100, 200)]:
        p, m = normal_moments(mu, sig, np.log(low), np.log(high))
        pp.append((w*p).sum(1))
        mm.append((w*m).sum(1))
    return mean, np.column_stack(pp), np.column_stack(mm)


def action(lam, old, mean, prob, moment):
    centered = moment-mean[:, None]*prob
    den = 1+prob@lam
    num = centered@lam
    value = old+num/den
    derivative = centered/den[:, None]-num[:, None]*prob/den[:, None]**2
    return value, derivative


def partition(d):
    part = arrays(ROOT/'ntuples/energy_ml_stage94/cal_partition.npz')
    ix = np.searchsorted(part['row'], d['row'])
    np.testing.assert_array_equal(part['row'][ix], d['row'])
    return part['subrole'][ix], part['weight'][ix]


def qa(d, old, distribution, cfg, discrepancy):
    start = begin()
    subrole, _ = partition(d)
    first = list(np.flatnonzero(d['input_missing']))
    first += list(np.flatnonzero(subrole == 1)[:5])+list(np.flatnonzero(subrole == 2)[:5])
    ix = np.array(list(dict.fromkeys(first+list(range(len(old)))))[:40])
    assert len(ix) == 40 and int(d['input_missing'][ix].sum()) == 6
    assert {1, 2}.issubset(set(subrole[ix])) and np.all(d['role'][ix] == 2)
    dist = tuple(v[ix] for v in distribution)
    mean, pp, mm = moments(dist)
    assert np.all((pp >= 0) & (pp <= 1))
    w, mu, sig = dist
    whole_p, whole_m = normal_moments(mu, sig, np.log(50), np.log(200))
    mass_error = float(np.max(abs(pp.sum(1)-(w*whole_p).sum(1))))
    moment_error = float(np.max(abs(mm.sum(1)-(w*whole_m).sum(1))))
    assert mass_error < 1e-12 and moment_error < 1e-12
    independent = []
    for j, (low, high) in enumerate([(50, 100), (100, 200)]):
        a, b = (np.log(low)-mu)/sig, (np.log(high)-mu)/sig
        p = np.where(a >= 0, norm.sf(a)-norm.sf(b), norm.cdf(b)-norm.cdf(a))
        m = mu*p+sig*(norm.pdf(a)-norm.pdf(b))
        independent += [float(np.max(abs((w*p).sum(1)-pp[:, j]))),
                        float(np.max(abs((w*m).sum(1)-mm[:, j])))]
    p, m = normal_moments(np.array([0., 0., 2.]), np.array([1., 1., 3.]),
                           np.array([-1., 0., -np.inf]), np.array([1., np.inf, np.inf]))
    np.testing.assert_allclose(p, [norm.cdf(1)-norm.cdf(-1), .5, 1.], atol=1e-14)
    np.testing.assert_allclose(m, [0., 1/np.sqrt(2*np.pi), 2.], atol=1e-14)
    zero, _ = action(np.zeros(2), old[ix], mean, pp, mm)
    np.testing.assert_array_equal(zero, old[ix])
    point, grad = action(np.array([2., 3.]), old[ix], mean, pp, mm)
    formula = (mean+mm@np.array([2., 3.]))/(1+pp@np.array([2., 3.]))
    formula_error = float(np.max(abs(point-old[ix]-(formula-mean))))
    errors = []
    for j in range(2):
        step = np.eye(2)[j]*1e-5
        plus = action(np.array([2., 3.])+step, old[ix], mean, pp, mm)[0]
        minus = action(np.array([2., 3.])-step, old[ix], mean, pp, mm)[0]
        errors.append(float(np.max(abs((plus-minus)/2e-5-grad[:, j]))))
    assert max(errors) < 1e-7 and max(independent) < 1e-12 and formula_error < 1e-12
    elapsed = resources(start)
    # Work is analytic; project event arithmetic with a conservative 50x allowance.
    projected = elapsed['wall_s']*24801/40*50+120
    assert projected < 900
    save(OUT/'QA.json', dict(passed=True, identities=40, rows=d['row'][ix].tolist(),
        subroles=subrole[ix].tolist(), missing=6, new_optimizations=0,
        zero_point_bit_exact=True, decoded_saved_logE_max=discrepancy,
        mass_additivity_max=mass_error, moment_additivity_max=moment_error,
        independent_moments_max=max(independent), derivative_max=max(errors),
        direct_action_formula_max=formula_error, full_work_projection_wall_s=projected,
        fixed_b_T=cfg, **elapsed))


def fit(d, old, moment_values):
    start = begin()
    assert not (OUT/'optimization_started.json').exists()
    subrole, partweight = partition(d)
    use = np.flatnonzero(subrole == 1)
    assert [len(use), int((subrole == 2).sum()), int((subrole == 0).sum())] == [5443, 5746, 423]
    data = {k: v[use] for k, v in d.items()}
    group = masks(data)
    assert int(group['E50_100'].sum()) == 85
    y, ww, base = np.log(data['truth_E_GeV']), partweight[use], old[use]
    traditional = np.log(data['pz']/.8)
    mean, pp, mm = (v[use] for v in moment_values)
    groups = LAYERS[:2]+list(PROTECT)
    references = [traditional, traditional]+[base]*len(PROTECT)
    normloss = np.array([np.average((ref-y)[group[k]]**2, weights=ww[group[k]])
                         for k, ref in zip(groups, references)])
    limits = np.array([0., 0.]+[v*v for v in PROTECT.values()])

    def constraints(x):
        point, dp = action(x[:2], base, mean, pp, mm)
        err = point-y
        risk, jac = [], []
        for k, scale in zip(groups, normloss):
            z = group[k]
            risk.append(np.average(err[z]**2, weights=ww[z])/scale)
            jac.append(np.average(2*err[z, None]*dp[z], weights=ww[z], axis=0)/scale)
        value = limits-np.array(risk)
        value[:2] += x[2]
        deriv = np.column_stack([-np.array(jac), np.r_[np.ones(2), np.zeros(len(PROTECT))]])
        return value, deriv

    initial_risk = [np.average((base-y)[group[k]]**2, weights=ww[group[k]])/scale
                    for k, scale in zip(groups[:2], normloss[:2])]
    x0 = np.array([0., 0., max(initial_risk)])
    errors = []
    for j in range(3):
        step = np.eye(3)[j]*1e-5
        numeric = (constraints(x0+step)[0]-constraints(x0-step)[0])/2e-5
        errors.append(float(np.max(abs(numeric-constraints(x0)[1][:, j]))))
    assert max(errors) < 1e-7 and np.min(constraints(x0)[0]) >= -1e-12
    save(OUT/'optimization_started.json', dict(optimizer_calls_allowed=1, x0=x0.tolist(),
        method='SLSQP', bounds=[[0, 100], [0, 100], [None, None]],
        ftol=1e-9, maxiter=200, fit_role='cal_select',
        constraint_jacobian_finite_difference_max=max(errors), test_risks_evaluated=False))
    opt = minimize(lambda x: x[2], x0, jac=lambda x: np.array([0., 0., 1.]),
        method='SLSQP', bounds=[(0, 100), (0, 100), (None, None)],
        constraints=[dict(type='ineq', fun=lambda x: constraints(x)[0],
                          jac=lambda x: constraints(x)[1])], options=dict(ftol=1e-9, maxiter=200))
    residual, jac = constraints(opt.x)
    result = dict(success=bool(opt.success), status=int(opt.status), message=str(opt.message),
        x=opt.x.tolist(), lambda_weights=opt.x[:2].tolist(), tau=float(opt.fun),
        iterations=int(opt.nit), evaluations=int(opt.nfev), jacobian_evaluations=int(opt.njev),
        constraints=[dict(stratum=k, residual=float(v)) for k, v in zip(groups, residual)],
        min_feasible_residual=float(residual.min()),
        boundary_hit=[bool(abs(v) < 1e-7 or abs(v-100) < 1e-7) for v in opt.x[:2]],
        optimizer_calls=1, no_test_selection=True, selection_frozen=True,
        initial_tau=float(x0[2]), **resources(start))
    save(OUT/'optimization.json', result)
    assert opt.success and residual.min() >= -1e-8, 'Numerically unresolved; no intermediate test policy'
    return opt.x[:2]


def evaluate_task(spec):
    role, layer = spec
    d, policies, roles = G
    v = roles[role]
    mask = v['masks'][layer]
    ix, ww, gid = v['use'][mask], v['weights'][mask], v['gid'][mask]
    draws, nk = v['draw'], len(v['keys'])
    den = draws@np.bincount(gid, weights=ww, minlength=nk)
    valid = den > 0
    support = dict(role=role, stratum=layer, N=len(ix), incoming=len(np.unique(gid)), weight_sum=float(ww.sum()))
    names = list(policies)
    y = np.log(d['truth_E_GeV'][ix])
    err = np.column_stack([policies[k][ix]-y for k in names])
    loss = np.zeros((nk, len(names)))
    np.add.at(loss, gid, ww[:, None]*err**2)
    boots = draws@loss
    point_rows = []
    for j, name in enumerate(names):
        bounds = interval(np.sqrt(boots[valid, j]/den[valid]))
        point_rows.append(dict(model=name, **support, **metrics(y, policies[name][ix], ww),
                               RMSE_low95=bounds[0], RMSE_high95=bounds[1]))
    tail = {}
    rel = np.expm1(err)
    for sign, flag in [('total', abs(rel) > .5), ('positive', rel > .5), ('negative', rel < -.5)]:
        agg = np.zeros_like(loss)
        np.add.at(agg, gid, ww[:, None]*flag)
        tail[sign] = (agg.sum(0)/ww.sum(), draws@agg)
    comparisons = []
    j = names.index('decision')
    primary_boot = None
    for ref in ['traditional', 'direct_cal', 'E94_fixed']:
        b = names.index(ref)
        good = valid & (boots[:, b] > 0)
        ratio = np.sqrt(boots[good, j]/boots[good, b])
        bounds = interval(ratio)
        row = dict(candidate='decision', reference=ref, **support,
            RMSE_ratio=float(np.sqrt(loss[:, j].sum()/loss[:, b].sum())),
            low95=bounds[0], high95=bounds[1], valid_draws=int(good.sum()))
        for sign, (point, boot) in tail.items():
            bounds = interval(100*(boot[good, j]-boot[good, b])/den[good])
            row.update({sign+'_tail_delta_pp': float(100*(point[j]-point[b])),
                        sign+'_tail_low95_pp': bounds[0], sign+'_tail_high95_pp': bounds[1]})
        comparisons.append(row)
        if role == 'cal_post' and layer in LAYERS[:2] and ref == 'E94_fixed':
            assert good.all()
            primary_boot = (layer, ratio)
    return point_rows, comparisons, primary_boot


def validate_primary(primary, low_ratios):
    d, policies, roles = G
    v = roles['cal_post']
    values = []
    for layer in LAYERS[:2]:
        z = v['masks'][layer]
        ix = v['use'][z]
        sw = v['draw'][:, v['gid'][z]]*v['weights'][z][None, :]
        y = np.log(d['truth_E_GeV'][ix])
        values.append(np.sqrt((sw@(policies['decision'][ix]-y)**2)/(sw@(policies['E94_fixed'][ix]-y)**2)))
    check = interval(np.maximum(*values))
    error = max(abs(check[0]-primary['low95']), abs(check[1]-primary['high95']),
                *(float(np.max(abs(a-low_ratios[k]))) for a, k in zip(values, LAYERS[:2])))
    assert error < 1e-12
    return error


def validate_gates(paired):
    d, policies, roles = G
    v = roles['test']
    checks = []
    for layer in LAYERS:
        z = v['masks'][layer]
        ix = v['use'][z]
        sw = v['draw'][:, v['gid'][z]]*v['weights'][z][None, :]
        den = sw.sum(1)
        y = np.log(d['truth_E_GeV'][ix])
        error = policies['decision'][ix]-y
        ref = 'traditional' if layer in LAYERS[:2] else 'direct_cal'
        row = next(r for r in paired if r['role'] == 'test' and r['stratum'] == layer and r['reference'] == ref)
        bounds = interval(np.sqrt((sw@error**2)/(sw@(policies[ref][ix]-y)**2)))
        checks.append(dict(stratum=layer, metric='RMSE_interval', max_abs_error=max(abs(bounds[0]-row['low95']), abs(bounds[1]-row['high95']))))
        row = next(r for r in paired if r['role'] == 'test' and r['stratum'] == layer and r['reference'] == 'direct_cal')
        r, dr = np.expm1(error), np.expm1(policies['direct_cal'][ix]-y)
        for sign, a, b in [('total', abs(r) > .5, abs(dr) > .5), ('positive', r > .5, dr > .5), ('negative', r < -.5, dr < -.5)]:
            bounds = interval(100*(sw@(a.astype(float)-b.astype(float)))/den)
            checks.append(dict(stratum=layer, metric=sign+'_tail_interval', max_abs_error=max(abs(bounds[0]-row[sign+'_tail_low95_pp']), abs(bounds[1]-row[sign+'_tail_high95_pp']))))
    assert max(r['max_abs_error'] for r in checks) < 1e-10
    table(OUT/'independent_gate_checks.tsv', checks)
    return checks


def main():
    global G
    start = begin()
    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    dcal, oldcal, qcal, cfg, discrepancy = load([2])
    assert len(oldcal) == 11612 and int(dcal['input_missing'].sum()) == 6
    qa(dcal, oldcal, qcal, cfg, discrepancy)
    cal_moments = moments(qcal)
    w, mu, sig = qcal
    subrole, pw = partition(dcal)
    y = np.log(dcal['truth_E_GeV'])
    ld = logsumexp(np.log(w)-np.log(sig)-.5*((y[:, None]-mu)/sig)**2-.5*np.log(2*np.pi), axis=1)
    nll_post = float(-np.average(ld[subrole == 2], weights=pw[subrole == 2]))
    assert abs(nll_post-cfg['NLL_after']) < 1e-12
    lam = fit(dcal, oldcal, cal_moments)
    # Both weights and optimizer outcome persisted before any test risk evaluation.
    d, old, q, same, discrepancy = load([2, 3])
    assert same == cfg
    assert [int((d['role'] == r).sum()) for r in [2, 3]] == [11612, 13189]
    mean, pp, mm = moments(q)
    point, _ = action(lam, old, mean, pp, mm)
    assert np.isfinite(point).all()
    zero, _ = action(np.zeros(2), old, mean, pp, mm)
    np.testing.assert_array_equal(zero, old)
    temporary = CACHE/'points.tmp.npz'
    np.savez_compressed(temporary, row=d['row'], old=old, decision=point)
    readback = arrays(temporary)
    np.testing.assert_array_equal(readback['decision'], point)
    temporary.replace(CACHE/'points.npz')
    base = arrays(ROOT/'ml/artifacts/stage87/predictions.npz')
    ib = np.searchsorted(base['row'], d['row'])
    np.testing.assert_array_equal(base['row'][ib], d['row'])
    policies = dict(traditional=np.log(d['pz']/.8), direct_cal=base['direct_cal'][ib],
                    bounded_cal=base['bounded_cal'][ib], E94_fixed=old, decision=point)
    cal = np.flatnonzero(d['role'] == 2)
    post = cal[subrole == 2]
    roles = {}
    for role, use, weight, seed in [('cal', cal, d['weight'][cal], 2026110389),
            ('cal_post', post, pw[subrole == 2], 2026110389),
            ('test', np.flatnonzero(d['role'] == 3), d['weight'][d['role'] == 3], 2026110390)]:
        sub = {k: v[use] for k, v in d.items()}
        keys, gid, draw = incoming_draws(sub, seed)
        np.testing.assert_allclose(np.bincount(gid, weights=weight), 1, atol=1e-12)
        roles[role] = dict(use=use, weights=weight, keys=keys, gid=gid, draw=draw, masks=masks(sub))
    G = (d, policies, roles)
    jobs = [(role, key) for role, v in roles.items() for key, z in v['masks'].items() if z.any()]
    tick = time.perf_counter()
    with mp.get_context('fork').Pool(4) as pool:
        result = pool.map(evaluate_task, jobs, chunksize=1)
    pool_wall = time.perf_counter()-tick
    rows = sum((r[0] for r in result), [])
    paired = sum((r[1] for r in result), [])
    low_ratios = dict(r[2] for r in result if r[2] is not None)
    table(OUT/'points.tsv', rows)
    table(OUT/'paired.tsv', paired)
    low = [next(r for r in paired if r['role'] == 'cal_post' and r['stratum'] == k and r['reference'] == 'E94_fixed')['RMSE_ratio'] for k in LAYERS[:2]]
    bounds = interval(np.maximum(*(low_ratios[k] for k in LAYERS[:2])))
    primary = dict(statistic='max of the two low-energy RMSE ratios, decision / E94_fixed',
        role='cal_post', point=max(low), low95=bounds[0], high95=bounds[1], supported=bounds[1] < 1,
        bootstrap_replicates=500, conditional_only=True)
    primary_error = validate_primary(primary, low_ratios)
    checks = validate_gates(paired)
    oldrows = list(csv.DictReader((ROOT/'workbook/stage94_energy_ml/metrics.tsv').open(), delimiter='\t'))
    oldmap = {(r['role'], r['stratum'], r['policy']): r for r in oldrows if r['weighting'] == 'incoming'}
    control = []
    for r in rows:
        name = {'traditional': 'traditional', 'direct_cal': 'direct_cal', 'E94_fixed': 'E_ensemble_cal'}.get(r['model'])
        prev = oldmap.get((r['role'], r['stratum'], name))
        if prev:
            for key in ['log_RMSE', 'median_bias_pct', 'mean_bias_pct', 'R68_pct', 'tail50_pct', 'positive_tail50_pct', 'negative_tail50_pct']:
                error = abs(r[key]-float(prev[key]))
                assert error < 1e-10
                control.append(dict(role=r['role'], stratum=r['stratum'], model=r['model'], metric=key, abs_error=error))
    table(OUT/'old_controls.tsv', control)
    gates = []
    for k in LAYERS:
        ref = 'traditional' if k in LAYERS[:2] else 'direct_cal'
        r = next(r for r in paired if r['role'] == 'test' and r['stratum'] == k and r['reference'] == ref)
        tail = next(r for r in paired if r['role'] == 'test' and r['stratum'] == k and r['reference'] == 'direct_cal')
        limit = 1.05 if k in LAYERS[:2] else 1.01 if k == 'all' else 1.03
        gates.append(dict(stratum=k, reference=ref, upper95=r['high95'], limit=limit,
            RMSE_pass=r['high95'] <= limit, tail_pass=all(tail[s+'_tail_high95_pp'] <= 2 for s in ['total', 'positive', 'negative']),
            **{s+'_tail_upper95_pp': tail[s+'_tail_high95_pp'] for s in ['total', 'positive', 'negative']}))
    table(OUT/'gates.tsv', gates)
    save(OUT/'decision.json', dict(primary=primary, final_joint_pass=all(r['RMSE_pass'] and r['tail_pass'] for r in gates),
        promotion=False, q_unchanged=True, new_energy_fits=0, new_b_T_optimizations=0,
        decision_optimizations=1, no_automatic_followup=True))
    save(OUT/'validation.json', dict(passed=True, old_scalar_checks=len(control), old_scalar_max=max(r['abs_error'] for r in control),
        primary_independent_max=primary_error, independent_gate_checks=len(checks), independent_gate_max=max(r['max_abs_error'] for r in checks),
        full_cal_post_q_NLL=nll_post, old_q_NLL_difference=abs(nll_post-cfg['NLL_after']), decoded_saved_logE_max=discrepancy,
        zero_point_bit_exact=True, persisted_points_exact=True, test_after_weight_freeze=True,
        roles={k: dict(N=len(v['use']), incoming=len(v['keys']), weight_sum=float(v['weights'].sum())) for k, v in roles.items()}))
    plot(rows)
    child = resource.getrusage(resource.RUSAGE_CHILDREN)
    save(OUT/'complete.json', dict(passed=True, processes=4, tasks=len(jobs), pool_wall_s=pool_wall,
        child_CPU_s=child.ru_utime+child.ru_stime, new_energy_fits=0, decision_optimizations=1, **resources(start)))
    print((OUT/'decision.json').read_text(), flush=True)
    print((OUT/'complete.json').read_text(), flush=True)


def plot(rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 3.8), layout='constrained')
    keys = ['E50_100', 'E100_200', 'all', 'pz50_100_trueE200', 'high_y']
    for name in ['traditional', 'direct_cal', 'E94_fixed', 'decision']:
        rr = [next(r for r in rows if r['role'] == 'test' and r['stratum'] == k and r['model'] == name) for k in keys]
        ax.plot(range(len(keys)), [r['log_RMSE'] for r in rr], 'o-', label=name)
    ax.set(xticks=range(len(keys)), xticklabels=['50–100 GeV', '100–200 GeV', 'all', 'low-pz high-E', 'high-y'],
           ylabel='log-RMSE', title='Developed test: fixed density, changed point action')
    ax.legend()
    fig.savefig(OUT/'point_action.svg')
    fig.savefig(OUT/'point_action.pdf')
    plt.close(fig)


if __name__ == '__main__':
    main()
