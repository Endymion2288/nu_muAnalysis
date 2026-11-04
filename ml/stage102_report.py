"""Eight-process paired evaluation, fixed checkpoints and old fixed b, zero fits."""
import json
import multiprocessing as mp
import os
import resource
import time

import numpy as np
from scipy.special import logsumexp, ndtr

from report_energy_architectures import group_masks, mixture, probability_summary
from report_resplit_energy import incoming_draws, metrics
from stage102_common import (REPO, OUT, ART, SEED, OLD_B, GATES,
    arrays, begin, resources, save, table)

G = None
NEW = ['P_raw', 'N_raw', 'P_oldb', 'N_oldb']


def ci(values):
    return [float(v) for v in np.quantile(values[np.isfinite(values)], [.025, .975])]


def prepare():
    start = begin()
    assert json.loads((OUT/'worker_complete.json').read_text())['new_training_trajectories'] == 1
    all_d = arrays(REPO/'ntuples/energy_ml_stage94/evaluation_input.npz')
    selected = np.isin(all_d['role'], [2, 3])
    d = {k: v[selected] for k, v in all_d.items()}
    h = arrays(ART/'heads.npz')
    np.testing.assert_array_equal(d['row'], h['row'])
    assert [int((d['role'] == role).sum()) for role in [2, 3]] == [11612, 13189]
    assert [int(d['input_missing'][d['role'] == role].sum()) for role in [2, 3]] == [6, 5]
    base = arrays(REPO/'ml/artifacts/stage87/predictions.npz')
    ix = np.searchsorted(base['row'], d['row'])
    np.testing.assert_array_equal(base['row'][ix], d['row'])
    policies = dict(traditional=np.log(d['pz']/.8), direct_cal=base['direct_cal'][ix],
                    bounded_cal=base['bounded_cal'][ix])
    old = arrays(REPO/'ml/artifacts/stage94/point_predictions.npz')
    ix = np.searchsorted(old['row'], d['row'])
    np.testing.assert_array_equal(old['row'][ix], d['row'])
    policies['oldP_raw'] = old['E_2026110494'][ix].astype(float)
    policies['oldP_oldb'] = policies['oldP_raw']+OLD_B
    distributions, checks = {}, []
    truth = np.log(d['truth_E_GeV'])
    anchor = np.log(d['pz']/.8)
    for name in ['P', 'N']:
        w, mu, sig = mixture(h[name+'_head'], anchor)
        point = (w*mu).sum(1)
        error = float(np.max(abs(point-h[name+'_point'])))
        assert error < 3e-6
        checks.append(dict(check='decoded_mean_vs_float32_saved_point', model=name, max_abs_error=error))
        # Retain the actual original float32 network point; do not silently replace it.
        for suffix, shift in [('raw', 0.), ('oldb', OLD_B)]:
            key = name+'_'+suffix
            policies[key] = h[name+'_point'].astype(float)+shift
            distributions[key] = probability_summary(w, mu+shift, sig, truth)
            assert distributions[key]['max_root_residual'] < 1e-10
            # Independent scipy.stats PDF/CDF check on every event; no second model forward.
            from scipy.stats import norm
            density = logsumexp(np.log(w)+norm.logpdf(truth[:, None], mu+shift, sig), axis=1)
            pit = np.sum(w*norm.cdf(truth[:, None], mu+shift, sig), axis=1)
            diff = max(float(np.max(abs(density-distributions[key]['logscore']))),
                       float(np.max(abs(pit-distributions[key]['PIT']))))
            assert diff < 1e-10
            checks.append(dict(check='independent_scipy_density_CDF_all_events', model=key, max_abs_error=diff))
    part = arrays(REPO/'ntuples/energy_ml_stage94/cal_partition.npz')
    cal = np.flatnonzero(d['role'] == 2)
    ip = np.searchsorted(part['row'], d['row'][cal])
    np.testing.assert_array_equal(part['row'][ip], d['row'][cal])
    post = cal[part['subrole'][ip] == 2]
    postweight = part['weight'][ip][part['subrole'][ip] == 2]
    assert len(post) == 5746
    roles = {}
    for role, use, weights, seed in [('cal', cal, d['weight'][cal], 2026110389),
            ('cal_post', post, postweight, 2026110389),
            ('test', np.flatnonzero(d['role'] == 3), d['weight'][d['role'] == 3], 2026110390)]:
        sub = {k: v[use] for k, v in d.items()}
        keys, gid, draw = incoming_draws(sub, seed)
        sums = np.bincount(gid, weights=weights)
        np.testing.assert_allclose(sums, 1., atol=1e-12)
        roles[role] = dict(use=use, weights=weights, keys=keys, gid=gid, draws=draw,
                           masks=group_masks(sub))
    save(OUT/'report_input_validation.json', dict(passed=True, eval_rows=len(truth),
        new_fits=0, new_calibration_optimizations=0, saved_points_preserved=True,
        original_row_role_weights_exact=True, post_subrole_weights_retained=True,
        roles={k: dict(N=len(v['use']), incoming=len(v['keys']), weight_sum=float(v['weights'].sum())) for k, v in roles.items()},
        all_CDF_density_checks=checks, **resources(start)))
    return d, policies, distributions, roles


def task(spec):
    role, layer = spec
    d, policies, probability, roles = G
    data = roles[role]
    mask = data['masks'][layer]
    ix = data['use'][mask]
    ww = data['weights'][mask]
    gid = data['gid'][mask]
    draws = data['draws']
    nk = len(data['keys'])
    count = np.bincount(gid, weights=ww, minlength=nk)
    den = draws@count
    good = den > 0
    support = dict(role=role, stratum=layer, N=len(ix), incoming=len(np.unique(gid)),
                   weight_sum=float(ww.sum()))
    if not len(ix):
        return [], [], [], [], [], []
    y = np.log(d['truth_E_GeV'][ix])
    names = list(policies)
    errors = np.column_stack([policies[k][ix]-y for k in names])
    loss = np.zeros((nk, len(names)))
    np.add.at(loss, gid, ww[:, None]*errors**2)
    bootloss = draws@loss
    tails = {}
    rel = np.expm1(errors)
    for label, flags in [('total', abs(rel) > .5), ('positive', rel > .5), ('negative', rel < -.5)]:
        agg = np.zeros_like(loss)
        np.add.at(agg, gid, ww[:, None]*flags)
        tails[label] = (agg.sum(0)/ww.sum(), draws@agg)
    points = []
    for j, name in enumerate(names):
        value = metrics(y, policies[name][ix], ww)
        bounds = ci(np.sqrt(bootloss[good, j]/den[good]))
        points.append(dict(model=name, **support, **value,
                           log_RMSE_low95=bounds[0], log_RMSE_high95=bounds[1]))
    comparisons = [(n, ref) for n in NEW for ref in ['traditional', 'direct_cal']]
    comparisons += [('N_raw', 'P_raw'), ('N_oldb', 'P_oldb'), ('P_raw', 'oldP_raw'), ('P_oldb', 'oldP_oldb')]
    paired = []
    for a, b in comparisons:
        ja, jb = names.index(a), names.index(b)
        valid = good & (bootloss[:, jb] > 0)
        bounds = ci(np.sqrt(bootloss[valid, ja]/bootloss[valid, jb]))
        r = dict(candidate=a, reference=b, **support,
            RMSE_ratio=float(np.sqrt(loss[:, ja].sum()/loss[:, jb].sum())),
            low95=bounds[0], high95=bounds[1], valid_draws=int(valid.sum()))
        for label, (point, boots) in tails.items():
            bounds = ci(100*(boots[valid, ja]-boots[valid, jb])/den[valid])
            r.update({label+'_tail_delta_pp': float(100*(point[ja]-point[jb])),
                      label+'_tail_low95_pp': bounds[0], label+'_tail_high95_pp': bounds[1]})
        paired.append(r)
    probabilities, reliability, paired_probability = [], [], []
    samples = {}
    for name in NEW:
        value = probability[name]
        ld, pit, q = value['logscore'][ix], value['PIT'][ix], value['quantiles'][ix]
        def resample(v):
            return (draws@np.bincount(gid, weights=ww*v, minlength=nk))[good]/den[good]
        samples[name] = resample(-ld)
        nci, pci = ci(samples[name]), ci(resample(pit))
        r = dict(model=name, **support, NLL=float(np.average(-ld, weights=ww)),
                 NLL_low95=nci[0], NLL_high95=nci[1], mean_PIT=float(np.average(pit, weights=ww)),
                 PIT_low95=pci[0], PIT_high95=pci[1], uniformity_required=layer == 'all' or layer.startswith('X_'),
                 sparse=len(ix) < 20)
        for level, lo, hi in [(68, 1, 3), (90, 0, 4)]:
            flag = (y >= q[:, lo]) & (y <= q[:, hi])
            bounds = ci(100*resample(flag))
            r.update({f'coverage{level}_pct': float(100*np.average(flag, weights=ww)),
                      f'coverage{level}_low95_pct': bounds[0], f'coverage{level}_high95_pct': bounds[1],
                      f'width{level}_logE': float(np.average(q[:, hi]-q[:, lo], weights=ww))})
        probabilities.append(r)
        bins = np.minimum((pit*10).astype(int), 9)
        for j in range(10):
            reliability.append(dict(model=name, **support, PIT_bin=j,
                fraction=float(ww[bins == j].sum()/ww.sum())))
    for suffix in ['raw', 'oldb']:
        a, b = 'N_'+suffix, 'P_'+suffix
        delta = (-probability[a]['logscore'][ix])-(-probability[b]['logscore'][ix])
        bounds = ci(samples[a]-samples[b])
        paired_probability.append(dict(candidate=a, reference=b, **support,
            NLL_delta=float(np.average(delta, weights=ww)), low95=bounds[0], high95=bounds[1],
            primary=role == 'cal_post' and layer == 'all' and suffix == 'raw'))
    # Original numeric controls: re-evaluate old points on identical weights/roles.
    checks = []
    if role != 'cal_post':
        old = G_OLD_METRICS
        for model, oldname in [('traditional', 'traditional'), ('direct_cal', 'direct_cal'),
                ('oldP_raw', 'E_2026110494_raw'), ('oldP_oldb', 'E_2026110494_cal')]:
            oldrow = old.get((role, layer, oldname))
            if oldrow:
                newrow = next(r for r in points if r['model'] == model)
                for key in ['log_RMSE', 'tail50_pct', 'positive_tail50_pct', 'negative_tail50_pct']:
                    err = abs(newrow[key]-float(oldrow[key]))
                    assert err < 1e-10, (role, layer, model, key, err)
                    checks.append(dict(role=role, stratum=layer, model=model, metric=key, abs_error=err))
    return points, paired, probabilities, reliability, paired_probability, checks


def independent_primary():
    """Explicit sampled-incoming expansion, separate from matrix reduction."""
    d, _, probability, roles = G
    role = roles['cal_post']
    ix, gid, ww = role['use'], role['gid'], role['weights']
    keys = role['keys']
    first = np.unique(gid, return_index=True)[1]
    comp = d['component'][ix][first]
    rng = np.random.default_rng(2026110389)
    counts = np.zeros((500, len(keys)), int)
    for c in sorted(set(comp)):
        ids = np.flatnonzero(comp == c)
        counts[:, ids] = rng.multinomial(len(ids), np.full(len(ids), 1/len(ids)), size=500)
    errors = -probability['N_raw']['logscore'][ix]+probability['P_raw']['logscore'][ix]
    # Compute each incoming's weighted loss with explicit row selection, then expand IDs.
    grouped = np.array([np.dot(ww[gid == k], errors[gid == k]) for k in range(len(keys))])
    values = []
    for draw in counts:
        sample = np.repeat(np.arange(len(keys)), draw)
        values.append(float(grouped[sample].mean()))
    return float(np.average(errors, weights=ww)), ci(np.array(values))


def independent_gates(paired):
    """Re-evaluate all gate intervals directly in record space, without key sums."""
    d, policies, _, roles = G
    data = roles['test']
    checks = []
    for layer in GATES:
        mask = data['masks'][layer]
        ix = data['use'][mask]
        weight = data['weights'][mask]
        sampled = data['draws'][:, data['gid'][mask]]*weight[None, :]
        den = sampled.sum(1)
        truth = np.log(d['truth_E_GeV'][ix])
        reference = 'traditional' if layer in GATES[:2] else 'direct_cal'
        for name in NEW:
            candidate_error = policies[name][ix]-truth
            reference_error = policies[reference][ix]-truth
            valid = (den > 0) & ((sampled@(reference_error**2)) > 0)
            values = np.sqrt((sampled@(candidate_error**2))[valid]/(sampled@(reference_error**2))[valid])
            actual = ci(values)
            r = next(r for r in paired if r['role'] == 'test' and r['stratum'] == layer
                     and r['candidate'] == name and r['reference'] == reference)
            error = max(abs(actual[0]-r['low95']), abs(actual[1]-r['high95']))
            assert error < 1e-10
            checks.append(dict(model=name, stratum=layer, metric='RMSE_interval', max_abs_error=error))
            rr = np.expm1(candidate_error)
            dr = np.expm1(policies['direct_cal'][ix]-truth)
            control = next(r for r in paired if r['role'] == 'test' and r['stratum'] == layer
                           and r['candidate'] == name and r['reference'] == 'direct_cal')
            for sign, candidate, direct in [('total', abs(rr) > .5, abs(dr) > .5),
                    ('positive', rr > .5, dr > .5), ('negative', rr < -.5, dr < -.5)]:
                delta = candidate.astype(float)-direct.astype(float)
                actual = ci((100*(sampled@delta)/den)[den > 0])
                error = max(abs(actual[0]-control[sign+'_tail_low95_pp']),
                            abs(actual[1]-control[sign+'_tail_high95_pp']))
                assert error < 1e-10
                checks.append(dict(model=name, stratum=layer, metric=sign+'_tail_interval', max_abs_error=error))
    table(OUT/'independent_gate_checks.tsv', checks)
    return checks


def main():
    global G, G_OLD_METRICS
    start = begin()
    G = prepare()
    import csv
    with (REPO/'workbook/stage94_energy_ml/metrics.tsv').open() as f:
        old = list(csv.DictReader(f, delimiter='\t'))
    G_OLD_METRICS = {(r['role'], r['stratum'], r['policy']): r for r in old if r['weighting'] == 'incoming'}
    jobs = [(role, layer) for role, value in G[3].items() for layer in value['masks'] if value['masks'][layer].any()]
    tick = time.perf_counter()
    with mp.get_context('fork').Pool(8) as pool:
        results = pool.map(task, jobs, chunksize=1)
    combined = [sum((r[j] for r in results), []) for j in range(6)]
    for name, rows in zip(['points', 'paired_points', 'probability', 'PIT', 'paired_probability', 'old_controls'], combined):
        table(OUT/(name+'.tsv'), rows)
    primary = next(r for r in combined[4] if r['primary'])
    point, bounds = independent_primary()
    err = max(abs(point-primary['NLL_delta']), abs(bounds[0]-primary['low95']), abs(bounds[1]-primary['high95']))
    assert err < 1e-12
    gates = []
    for r in combined[1]:
        if r['role'] != 'test' or r['candidate'] not in NEW or r['stratum'] not in GATES:
            continue
        layer = r['stratum']
        reference = 'traditional' if layer in GATES[:2] else 'direct_cal'
        if r['reference'] != reference:
            continue
        limit = 1.05 if layer in GATES[:2] else 1.01 if layer == 'all' else 1.03
        tail = next(q for q in combined[1] if q['role'] == 'test' and q['stratum'] == layer
                    and q['candidate'] == r['candidate'] and q['reference'] == 'direct_cal')
        gates.append(dict(model=r['candidate'], stratum=layer, RMSE_reference=reference,
            RMSE_ratio_upper95=r['high95'], RMSE_limit=limit, RMSE_pass=r['high95'] <= limit,
            **{k+'_tail_upper95_pp': tail[k+'_tail_high95_pp'] for k in ['total', 'positive', 'negative']},
            tail_pass=all(tail[k+'_tail_high95_pp'] <= 2 for k in ['total', 'positive', 'negative'])))
    assert len(gates) == 32
    table(OUT/'gates.tsv', gates)
    independent = independent_gates(combined[1])
    save(OUT/'decision.json', dict(primary=primary, primary_supported=primary['high95'] < 0,
        conditional_only=True, point_joint_pass={n: all(r['RMSE_pass'] and r['tail_pass'] for r in gates if r['model'] == n) for n in NEW},
        promotion=False, new_fits=0, new_b_T_optimizations=0,
        action='complete this checkpoint comparison; no automatic seed/loss/local-calibration/collection extension'))
    save(OUT/'validation.json', dict(passed=True, old_scalar_checks=len(combined[5]),
        old_scalar_max=max(r['abs_error'] for r in combined[5]), independent_primary_expansion_max=err,
        independent_primary_point=point, independent_primary_CI=bounds, bootstrap_replicates=500,
        independent_gate_interval_checks=len(independent),
        independent_gate_max=max(r['max_abs_error'] for r in independent),
        original_role_subrole_incoming_support=True, no_test_checkpoint_selection=True))
    plot(combined[0], combined[2])
    u = resource.getrusage(resource.RUSAGE_CHILDREN)
    save(OUT/'report_complete.json', dict(passed=True, new_fits=0, new_b_T_optimizations=0,
        processes=8, tasks=len(jobs), parallel_wall_s=time.perf_counter()-tick,
        child_CPU_s=u.ru_utime+u.ru_stime, roles=list(G[3]), **resources(start)))
    print((OUT/'decision.json').read_text(), flush=True)
    print((OUT/'report_complete.json').read_text(), flush=True)


def plot(points, probabilities):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.7), layout='constrained')
    labels = ['E50_100', 'E100_200', 'all', 'pz50_100_trueE200', 'high_y']
    for name, color in [('P_raw', 'C0'), ('N_raw', 'C1')]:
        rows = [next(r for r in points if r['role'] == 'test' and r['stratum'] == l and r['model'] == name) for l in labels]
        axes[0].plot(np.arange(len(labels)), [r['log_RMSE'] for r in rows], 'o-', color=color, label=name)
        rows = [next(r for r in probabilities if r['role'] == 'test' and r['stratum'] == 'all' and r['model'] == name)]
        r = rows[0]
        axes[1].plot([68, 90], [r['coverage68_pct'], r['coverage90_pct']], 'o-', color=color, label=name)
    axes[0].set(xticks=np.arange(len(labels)), xticklabels=['50–100', '100–200', 'all', 'low-pz high-E', 'high-y'], ylabel='Test log-RMSE', title='Same trajectory, raw points')
    axes[0].tick_params(axis='x', labelrotation=18)
    axes[1].plot([68, 90], [68, 90], '--', color='grey', label='nominal')
    axes[1].set(xlabel='Nominal coverage [%]', ylabel='Test coverage [%]', title='Developed test; no calibration fit')
    for ax in axes:
        ax.legend()
    fig.savefig(OUT/'checkpoint_comparison.svg')
    fig.savefig(OUT/'checkpoint_comparison.pdf')
    plt.close(fig)


if __name__ == '__main__':
    main()
