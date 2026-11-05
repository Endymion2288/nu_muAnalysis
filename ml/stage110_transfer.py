"""Stage110: one analytic coefficient and paired saved-output risks, batch only."""
import csv
import json
import multiprocessing as mp
import resource
import time
from pathlib import Path

import numpy as np

from report_resplit_energy import incoming_draws, metrics
from stage99_report import masks
from stage110_solver import FEASIBILITY_TOL, analytic_qa, solve, value
from support_augmentation import arrays, save, table

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage110_energy_ml'
CACHE = ROOT/'ntuples/energy_ml_stage110'
LAYERS = ['E50_100', 'E100_200', 'all', 'E200_inf', 'pz50_100',
          'pz50_100_trueE200', 'high_y', 'unconfirmed']
PROTECT = dict(all=1.01, E200_inf=1.03, pz50_100=1.03,
               pz50_100_trueE200=1.03, high_y=1.03, unconfirmed=1.03)
G = None


def ci(x):
    x = np.asarray(x)
    return [float(v) for v in np.quantile(x[np.isfinite(x)], [.025, .975])]


def joined(source, rows):
    assert np.all(np.diff(source['row']) > 0)
    ix = np.searchsorted(source['row'], rows)
    np.testing.assert_array_equal(source['row'][ix], rows)
    return ix


def load():
    d = arrays(ROOT/'ntuples/energy_ml_stage94/evaluation_input.npz')
    with np.load(ROOT/'ml/artifacts/stage108/predictions.npz') as z:
        point = {k: z[k] for k in ['row', 'A_raw', 'B_raw', 'geometry_available']}
    with np.load(ROOT/'ml/artifacts/stage87/predictions.npz') as z:
        base = {k: z[k] for k in ['row', 'direct_cal', 'role', 'weight', 'truth_E_GeV', 'pz']}
    ip, ib = joined(point, d['row']), joined(base, d['row'])
    np.testing.assert_array_equal(point['row'], d['row'])
    split = arrays(ROOT/'ntuples/energy_ml_stage87/split.npz')
    assert len(split['role']) == 89033 and int((split['role'] == 0).sum()) == 17657
    np.testing.assert_array_equal(np.flatnonzero(split['role'] > 0), d['row'])
    for k in ['key_id', 'role', 'weight', 'origin', 'origin_row', 'component', 'group', 'block']:
        np.testing.assert_array_equal(d[k], split[k][d['row']])
    for k in ['role', 'weight', 'truth_E_GeV', 'pz']:
        np.testing.assert_array_equal(d[k], base[k][ib])
    d['geometry_available'] = point['geometry_available'][ip]
    d['base'] = base['direct_cal'][ib]
    # Shared compressed columns may be decoded, but no test differences before freeze.
    d['A_raw'], d['B_raw'] = point['A_raw'][ip], point['B_raw'][ip]
    assert len(d['row']) == 71376 and np.all(d['pz'] > 50)
    counts = []
    for code, nr, nk, missing, geom in [(1, 46575, 37556, 21, 345), (2, 11612, 10811, 6, 343), (3, 13189, 12125, 5, 356)]:
        z = d['role'] == code
        assert [int(z.sum()), len(np.unique(d['key_id'][z])), int(d['input_missing'][z].sum()),
                int((~d['geometry_available'][z]).sum())] == [nr, nk, missing, geom]
        _, gid = np.unique(d['key_id'][z], return_inverse=True)
        np.testing.assert_allclose(np.bincount(gid, weights=d['weight'][z]), 1., rtol=0, atol=1e-12)
        counts.append(dict(role=code, records=nr, incoming=nk, input_missing=missing, geometry_missing=geom))
    newk = (d['origin'] == 82) & (d['component'] == 'k')
    assert int(newk.sum()) == 1016
    cal = np.flatnonzero(d['role'] == 2)
    part = arrays(ROOT/'ntuples/energy_ml_stage94/cal_partition.npz')
    ix = joined(part, d['row'][cal])
    subrole, pw = part['subrole'][ix], part['weight'][ix]
    assert [int((subrole == s).sum()) for s in [0, 1, 2]] == [423, 5443, 5746]
    for s in [1, 2]:
        z = subrole == s
        _, gid = np.unique(d['key_id'][cal[z]], return_inverse=True)
        np.testing.assert_allclose(np.bincount(gid, weights=pw[z]), 1., rtol=0, atol=1e-12)
    save(OUT/'input_validation.json', dict(passed=True, roles=counts, compatible_records=89033,
        quarantined_records=17657, all_active_rows_joined=True, new_K_preserved=int(newk.sum()),
        cal_select=5443, cal_post=5746, cal_purged_from_select_only=423,
        point_columns=['row', 'A_raw', 'B_raw', 'geometry_available'], no_checkpoint_or_head_read=True,
        no_test_difference_or_risk_evaluated=True))
    return d, cal, subrole, pw


def direction(d):
    result = np.zeros(len(d['row']), dtype=float)
    good = d['geometry_available']
    result[good] = d['B_raw'][good].astype(float)-d['A_raw'][good].astype(float)
    assert np.isfinite(result).all()
    return result


def action(base, delta, alpha, available):
    result = base.copy()
    if alpha != 0:
        result[available] = base[available]+alpha*delta[available]
    return result


def coefficients(d, delta, weights, alpha=None, role=None):
    error = d['base']-np.log(d['truth_E_GeV'])
    result = []
    groups = masks(d)
    groups['geometry_missing'] = ~d['geometry_available']
    for layer, z in groups.items():
        if not z.any():
            continue
        avg = lambda x: float(np.average(x[z], weights=weights[z]))
        c, dd, a = avg(error**2), avg(error*delta), avg(delta**2)
        row = dict(stratum=layer, N=int(z.sum()), incoming=len(np.unique(d['key_id'][z])),
                   weight_sum=float(weights[z].sum()), C=c, D=dd, A=a)
        if alpha is not None:
            change = 2*alpha*dd+alpha**2*a
            actual = avg((error+alpha*delta)**2)-c
            assert abs(change-actual) <= FEASIBILITY_TOL
            row.update(role=role, alpha=alpha, predicted_risk_change=change,
                       actual_risk_change=actual, new_risk=c+change,
                       RMSE_ratio=float(np.sqrt((c+change)/c)))
        result.append(row)
    return result


def qa(d, subrole, weights):
    start = time.perf_counter(), time.process_time()
    # Deterministic identities, never selected on new errors or differences.
    rows = list(np.flatnonzero(d['input_missing']))
    rows += list(np.flatnonzero(~d['geometry_available'])[:5])
    rows += list(np.flatnonzero(subrole == 1)[:5])+list(np.flatnonzero(subrole == 2)[:5])
    ix = np.array(list(dict.fromkeys(rows+list(range(len(subrole)))))[:40])
    assert len(ix) == 40 and int(d['input_missing'][ix].sum()) == 6
    assert (~d['geometry_available'][ix]).any() and {1, 2}.issubset(set(subrole[ix]))
    small = {k: v[ix] for k, v in d.items()}
    delta = direction(small)
    zero = action(small['base'], delta, 0., small['geometry_available'])
    np.testing.assert_array_equal(zero, small['base'])
    assert zero.tobytes() == small['base'].tobytes()
    err = small['base']-np.log(small['truth_E_GeV'])
    c, dd, a = [float(np.average(v, weights=weights[ix])) for v in [err**2, err*delta, delta**2]]
    checks = []
    for alpha in [0., .25, 1.]:
        new = action(small['base'], delta, alpha, small['geometry_available'])
        assert new[~small['geometry_available']].tobytes() == small['base'][~small['geometry_available']].tobytes()
        direct = float(np.average((new-np.log(small['truth_E_GeV']))**2, weights=weights[ix]))
        checks.append(abs(direct-(c+2*alpha*dd+alpha**2*a)))
    assert max(checks) <= FEASIBILITY_TOL
    analytic = analytic_qa()
    save(OUT/'QA.json', dict(passed=True, identities=40, rows=small['row'].tolist(),
        keys=small['key_id'].tolist(), subroles=subrole[ix].tolist(), scalar_missing=6,
        geometry_missing=int((~small['geometry_available']).sum()), alpha0_bit_exact=True,
        geometry_fallback_bit_exact=True, direct_square_formula_max_abs_error=max(checks),
        analytic=analytic, natural_log_GeV_raw_difference=True, no_model_calls=True,
        CPU_s=time.process_time()-start[1], wall_s=time.perf_counter()-start[0]))


def fit(cal, subrole, pw):
    assert not (OUT/'selection.json').exists()
    use = subrole == 1
    d = {k: v[use] for k, v in cal.items()}
    delta = direction(d)
    rows = coefficients(d, delta, pw[use])
    coeff = {r['stratum']: r for r in rows}
    assert coeff['E50_100']['N'] == 85
    polys = [(coeff[k]['A']/coeff[k]['C'], 2*coeff[k]['D']/coeff[k]['C'], 1.) for k in LAYERS[:2]]
    constraints = {k: (coeff[k]['A'], 2*coeff[k]['D'], (1-limit**2)*coeff[k]['C'])
                   for k, limit in PROTECT.items()}
    result = solve(polys, constraints)
    alpha = result['alpha']
    result.update(fit_role='cal_select', analytic_global_minimum_of_fixed_problem=True,
        selection_frozen=True, test_differences_evaluated=False, coefficients=rows,
        constraints=[dict(stratum=k, RMSE_limit=PROTECT[k], residual=value(p, alpha),
                          active=abs(value(p, alpha)) <= FEASIBILITY_TOL) for k, p in constraints.items()],
        alpha0_feasible=True, risk_feasibility_absolute_tolerance=FEASIBILITY_TOL,
        objective_tie_tolerance=1e-12, solver_calls=1, numerical_optimizers=0,
        direction='geometry_available * (Stage108 B_raw - A_raw)', base='Stage87 direct_cal')
    table(OUT/'select_coefficients.tsv', rows)
    save(OUT/'selection.json', result)
    # Persist and read back the choice before any test difference or risk.
    frozen = json.loads((OUT/'selection.json').read_text())
    assert frozen['alpha'] == alpha and frozen['selection_frozen']
    return alpha


def task(spec):
    role, layer = spec
    d, policies, roles, delta, alpha = G
    v = roles[role]
    z = v['masks'][layer]
    ix, w, gid = v['use'][z], v['weights'][z], v['gid'][z]
    draw, nk = v['draw'], len(v['keys'])
    den = draw@np.bincount(gid, weights=w, minlength=nk)
    valid = den > 0
    support = dict(role=role, stratum=layer, N=len(ix), incoming=len(np.unique(gid)),
                   weight_sum=float(w.sum()), source_groups=len(np.unique(d['group'][ix])),
                   connected_blocks=len(np.unique(d['block'][ix])))
    names = list(policies)
    truth = np.log(d['truth_E_GeV'][ix])
    error = np.column_stack([policies[n][ix]-truth for n in names])
    agg = np.zeros((nk, len(names)))
    np.add.at(agg, gid, w[:, None]*error**2)
    boot = draw@agg
    points = []
    for j, name in enumerate(names):
        low, high = ci(np.sqrt(boot[valid, j]/den[valid]))
        points.append(dict(model=name, **support, **metrics(truth, policies[name][ix], w),
                           RMSE_low95=low, RMSE_high95=high))
    tails = {}
    rel = np.expm1(error)
    for sign, flags in [('total', abs(rel) > .5), ('positive', rel > .5), ('negative', rel < -.5)]:
        a = np.zeros_like(agg)
        np.add.at(a, gid, w[:, None]*flags)
        tails[sign] = (a.sum(0)/w.sum(), draw@a)
    paired, primary = [], {}
    j = names.index('transfer')
    for ref in ['traditional', 'direct_cal']:
        b = names.index(ref)
        good = valid & (boot[:, b] > 0)
        ratio = np.sqrt(boot[good, j]/boot[good, b])
        low, high = ci(ratio)
        row = dict(candidate='transfer', reference=ref, **support,
            RMSE_ratio=float(np.sqrt(agg[:, j].sum()/agg[:, b].sum())), low95=low, high95=high,
            valid_draws=int(good.sum()), interval_scope='component incoming conditional; no source/refit/alpha/offset/research-selection/system coverage')
        for sign, (central, bt) in tails.items():
            low, high = ci(100*(bt[good, j]-bt[good, b])/den[good])
            row.update({sign+'_tail_delta_pp': float(100*(central[j]-central[b])),
                        sign+'_tail_low95_pp': low, sign+'_tail_high95_pp': high})
        paired.append(row)
        if role == 'cal_post' and layer in LAYERS[:2] and ref == 'direct_cal':
            assert good.all()
            primary[layer] = ratio
    e0, dd = policies['direct_cal'][ix]-truth, delta[ix]
    c, cross, aa = [float(np.average(vv, weights=w)) for vv in [e0**2, e0*dd, dd**2]]
    change = 2*alpha*cross+alpha**2*aa
    actual = float(np.average(error[:, j]**2-e0**2, weights=w))
    assert abs(change-actual) <= FEASIBILITY_TOL
    coefficient = dict(**support, C=c, D=cross, A=aa, alpha=alpha,
        predicted_risk_change=change, actual_risk_change=actual, RMSE_ratio=float(np.sqrt((c+change)/c)))
    return points, paired, primary, coefficient


def validate(paired, primary):
    d, policies, roles, delta, alpha = G
    checks = []
    v = roles['test']
    for layer in LAYERS:
        z = v['masks'][layer]
        ix = v['use'][z]
        sw = v['draw'][:, v['gid'][z]]*v['weights'][z][None, :]
        den = sw.sum(1)
        y = np.log(d['truth_E_GeV'][ix])
        err = policies['transfer'][ix]-y
        for ref in ['traditional', 'direct_cal']:
            r = next(r for r in paired if r['role'] == 'test' and r['stratum'] == layer and r['reference'] == ref)
            re = policies[ref][ix]-y
            bounds = ci(np.sqrt((sw@err**2)/(sw@re**2)))
            checks.append(dict(stratum=layer, reference=ref, metric='RMSE',
                               max_abs_error=max(abs(bounds[0]-r['low95']), abs(bounds[1]-r['high95']))))
            if ref == 'direct_cal':
                rel, rr = np.expm1(err), np.expm1(re)
                for sign, a, b in [('total', abs(rel) > .5, abs(rr) > .5),
                        ('positive', rel > .5, rr > .5), ('negative', rel < -.5, rr < -.5)]:
                    bounds = ci(100*(sw@(a.astype(float)-b.astype(float)))/den)
                    checks.append(dict(stratum=layer, reference=ref, metric=sign+'_tail',
                        max_abs_error=max(abs(bounds[0]-r[sign+'_tail_low95_pp']), abs(bounds[1]-r[sign+'_tail_high95_pp']))))
    v = roles['cal_post']
    low = []
    for layer in LAYERS[:2]:
        z = v['masks'][layer]
        ix = v['use'][z]
        sw = v['draw'][:, v['gid'][z]]*v['weights'][z][None, :]
        truth = np.log(d['truth_E_GeV'][ix])
        low.append(np.sqrt((sw@(policies['transfer'][ix]-truth)**2)/(sw@(policies['direct_cal'][ix]-truth)**2)))
    bounds = ci(np.maximum(*low))
    pe = max(abs(bounds[0]-primary['low95']), abs(bounds[1]-primary['high95']))
    assert pe <= FEASIBILITY_TOL and max(r['max_abs_error'] for r in checks) <= FEASIBILITY_TOL
    table(OUT/'independent_checks.tsv', checks)
    return dict(primary_independent_max_abs_error=pe, interval_checks=len(checks),
                interval_max_abs_error=max(r['max_abs_error'] for r in checks))


def plot(rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    layers = LAYERS[:3]+['pz50_100_trueE200', 'high_y']
    fig, ax = plt.subplots(figsize=(9, 4), layout='constrained')
    for name in ['traditional', 'direct_cal', 'transfer']:
        vals = [next(r['log_RMSE'] for r in rows if r['role'] == 'test' and r['stratum'] == k and r['model'] == name) for k in layers]
        ax.plot(range(len(layers)), vals, 'o-', label=name)
    ax.set(xticks=range(len(layers)), xticklabels=['50–100 GeV', '100–200 GeV', 'all', 'low pz, high E', 'high-y'],
           ylabel='Incoming-weighted log-RMSE', title='Developed test: fixed A-to-B direction on strong BDT')
    ax.legend()
    fig.savefig(OUT/'anchored_transfer.svg')
    plt.close(fig)


def main():
    global G
    start = time.perf_counter(), time.process_time()
    protocol = json.loads((OUT/'protocol.json').read_text())
    assert protocol['stage'] == 110 and not (OUT/'selection.json').exists()
    d, calix, subrole, pw = load()
    cal = {k: v[calix] for k, v in d.items()}
    qa(cal, subrole, cal['weight'])
    alpha = fit(cal, subrole, pw)
    # First full-role difference and test diagnostics occur after persisted selection.
    delta = direction(d)
    new = action(d['base'], delta, alpha, d['geometry_available'])
    assert new[~d['geometry_available']].tobytes() == d['base'][~d['geometry_available']].tobytes()
    if alpha == 0:
        assert new.tobytes() == d['base'].tobytes()
    assert np.isfinite(new).all()
    CACHE.mkdir(parents=True, exist_ok=True)
    tmp = CACHE/'points.tmp.npz'
    np.savez_compressed(tmp, row=d['row'], transfer=new)
    readback = arrays(tmp)
    assert readback['transfer'].tobytes() == new.tobytes()
    np.testing.assert_array_equal(readback['row'], d['row'])
    tmp.replace(CACHE/'points.npz')
    policies = dict(traditional=np.log(d['pz']/.8), direct_cal=d['base'], transfer=new)
    test = np.flatnonzero(d['role'] == 3)
    roles = {}
    for role, use, w, seed in [('cal', calix, d['weight'][calix], 2026110389),
            ('cal_post', calix[subrole == 2], pw[subrole == 2], 2026110389),
            ('test', test, d['weight'][test], 2026110390)]:
        sub = {k: v[use] for k, v in d.items()}
        keys, gid, draw = incoming_draws(sub, seed)
        np.testing.assert_allclose(np.bincount(gid, weights=w), 1., rtol=0, atol=1e-12)
        layers = masks(sub)
        layers['geometry_missing'] = ~sub['geometry_available']
        roles[role] = dict(use=use, weights=w, keys=keys, gid=gid, draw=draw, masks=layers)
    G = d, policies, roles, delta, alpha
    jobs = [(role, layer) for role, v in roles.items() for layer, z in v['masks'].items() if z.any()]
    tick = time.perf_counter()
    with mp.get_context('fork').Pool(4) as pool:
        result = pool.map(task, jobs, chunksize=1)
    poolwall = time.perf_counter()-tick
    points = sum((r[0] for r in result), [])
    paired = sum((r[1] for r in result), [])
    boot = {k: v for r in result for k, v in r[2].items()}
    bounds = ci(np.maximum(*(boot[k] for k in LAYERS[:2])))
    central = [next(r['RMSE_ratio'] for r in paired if r['role'] == 'cal_post' and r['stratum'] == k and r['reference'] == 'direct_cal') for k in LAYERS[:2]]
    primary = dict(statistic='max of E50_100 and E100_200 transfer/direct_cal RMSE ratios',
        role='cal_post', point=max(central), low95=bounds[0], high95=bounds[1],
        supported=bounds[1] < 1, bootstrap_replicates=500, conditional_only=True)
    if alpha == 0:
        assert bounds == [1., 1.] and primary['point'] == 1.
    checks = validate(paired, primary)
    old = list(csv.DictReader((ROOT/'workbook/stage94_energy_ml/metrics.tsv').open(), delimiter='\t'))
    oldmap = {(r['role'], r['stratum'], r['policy']): r for r in old if r['weighting'] == 'incoming'}
    controls = []
    for r in points:
        prior = oldmap.get((r['role'], r['stratum'], r['model']))
        if prior:
            for k in ['log_RMSE', 'median_bias_pct', 'mean_bias_pct', 'R68_pct', 'tail50_pct', 'positive_tail50_pct', 'negative_tail50_pct']:
                error = abs(r[k]-float(prior[k]))
                assert error <= FEASIBILITY_TOL
                controls.append(dict(role=r['role'], stratum=r['stratum'], model=r['model'], metric=k, abs_error=error))
    assert controls
    gates = []
    for layer in LAYERS:
        ref = 'traditional' if layer in LAYERS[:2] else 'direct_cal'
        limit = 1.05 if layer in LAYERS[:2] else 1.01 if layer == 'all' else 1.03
        r = next(r for r in paired if r['role'] == 'test' and r['stratum'] == layer and r['reference'] == ref)
        t = next(r for r in paired if r['role'] == 'test' and r['stratum'] == layer and r['reference'] == 'direct_cal')
        gates.append(dict(stratum=layer, reference=ref, RMSE_upper95=r['high95'], limit=limit,
            RMSE_pass=r['high95'] <= limit,
            tail_pass=all(t[s+'_tail_high95_pp'] <= 2 for s in ['total', 'positive', 'negative']),
            **{s+'_tail_upper95_pp': t[s+'_tail_high95_pp'] for s in ['total', 'positive', 'negative']}))
    for name, rows in [('points.tsv', points), ('paired.tsv', paired), ('gates.tsv', gates),
            ('risk_coefficients.tsv', [r[3] for r in result]), ('old_controls.tsv', controls)]:
        table(OUT/name, rows)
    decision = dict(alpha=alpha, primary=primary,
        final_joint_pass=all(r['RMSE_pass'] and r['tail_pass'] for r in gates), promotion=False,
        fixed_direction_finished=True, new_network_fits=0, new_offsets=0, new_forwards=0,
        analytic_coefficients_fitted=1, no_automatic_followup=True,
        source_refit_research_selection_systematic_independent_confirmation=False)
    save(OUT/'decision.json', decision)
    save(OUT/'report_validation.json', dict(passed=True, **checks, old_scalar_checks=len(controls),
        old_scalar_max_abs_error=max(r['abs_error'] for r in controls),
        roles={k: dict(records=len(v['use']), incoming=len(v['keys']), weight_sum=float(v['weights'].sum())) for k, v in roles.items()},
        saved_point_readback_bit_exact=True, geometry_fallback_bit_exact=True,
        selected_before_test_difference=True, no_new_offset_or_model=True))
    plot(points)
    child = resource.getrusage(resource.RUSAGE_CHILDREN)
    selfcpu = time.process_time()-start[1]
    childcpu = child.ru_utime+child.ru_stime
    wall = time.perf_counter()-start[0]
    assert selfcpu+childcpu < 900 and wall < 900
    save(OUT/'complete.json', dict(passed=True, processes=4, inner_threads=1, tasks=len(jobs),
        pool_wall_s=poolwall, self_CPU_s=selfcpu, child_CPU_s=childcpu, wall_s=wall,
        peak_parent_RSS_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024))
    print(json.dumps(decision, indent=2), flush=True)


if __name__ == '__main__':
    main()
