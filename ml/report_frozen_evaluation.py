#!/usr/bin/env python3
"""Source-paired evaluation of frozen ensembles; no fits or parameter selection."""
import argparse
import json
import resource
import time
from pathlib import Path

import numpy as np

from frozen_evaluation import configuration, logs, read_cache, reportdir, save_json, stamp
from train_bdt import metric_values, write_table

METRICS = ['log_RMSE', 'mean_bias', 'median_bias', 'R68', 'relative_RMS', 'tail_0p5', 'tail_1']


def draws(groups, rng, repeats):
    names, inverse = np.unique(groups, return_inverse=True)
    weights = rng.multinomial(len(names), np.ones(len(names)) / len(names), size=repeats)
    return names, inverse, weights


def calibration_bootstrap(data, rng, repeats):
    _, gid, weights = draws(data['group'], rng, repeats)
    n = np.bincount(gid)
    total = weights @ n
    pred = logs(data)
    result = {}
    for v in ['F5', 'F6']:
        s = np.bincount(gid, weights=np.log(data['truth_E_GeV']) - pred[v])
        result[v] = (weights @ s) / total
    return result


def intervals(x):
    finite = np.isfinite(x)
    q = np.quantile(x[finite], [.025, .975]) if finite.any() else [np.nan, np.nan]
    return float(q[0]), float(q[1]), int((~finite).sum())


def sufficient_bootstrap(residual, gid, weights, offset):
    """Exact resampling of whole source groups, using sums and repeated-order ranks."""
    ng = weights.shape[1]
    n = weights @ np.bincount(gid, minlength=ng)
    safe = np.where(n > 0, n, 1)
    mean_log = (weights @ np.bincount(gid, weights=residual, minlength=ng)) / safe
    mean_log2 = (weights @ np.bincount(gid, weights=residual ** 2, minlength=ng)) / safe
    ratio = np.exp(residual)
    mean_ratio = (weights @ np.bincount(gid, weights=ratio, minlength=ng)) / safe
    mean_ratio2 = (weights @ np.bincount(gid, weights=ratio ** 2, minlength=ng)) / safe
    scale = np.exp(offset)
    order = np.argsort(ratio)
    sorted_ratio = ratio[order]
    cumulative = np.cumsum(weights[:, gid[order]], axis=1)
    ranks = (safe[:, None] - 1) * np.array([.16, .5, .84])
    lower = np.floor(ranks).astype(int)
    upper = np.ceil(ranks).astype(int)
    # These are ordinary np.quantile ranks on the integer-replicated event sample.
    quantiles = np.empty_like(ranks)
    for i in range(len(weights)):
        if not n[i]:
            quantiles[i] = np.nan
            continue
        lo = np.searchsorted(cumulative[i], lower[i] + 1)
        hi = np.searchsorted(cumulative[i], upper[i] + 1)
        quantiles[i] = sorted_ratio[lo] + (ranks[i] - lower[i]) * (sorted_ratio[hi] - sorted_ratio[lo])
    quantiles = scale[:, None] * quantiles - 1

    def count_below(threshold, side):
        pos = np.searchsorted(sorted_ratio, threshold / scale, side=side)
        return np.where(pos > 0, cumulative[np.arange(len(weights)), np.maximum(pos - 1, 0)], 0)

    result = dict(log_RMSE=np.sqrt(np.maximum(0, mean_log2 + 2 * offset * mean_log + offset ** 2)),
                  mean_bias=scale * mean_ratio - 1, median_bias=quantiles[:, 1],
                  R68=(quantiles[:, 2] - quantiles[:, 0]) / 2,
                  relative_RMS=np.sqrt(np.maximum(0, scale ** 2 * mean_ratio2 - 2 * scale * mean_ratio + 1)),
                  tail_0p5=(count_below(.5, 'left') + n - count_below(1.5, 'right')) / safe,
                  tail_1=(n - count_below(2, 'right')) / safe)
    for v in result.values():
        v[n == 0] = np.nan
    return result


def strata(data, cfg):
    p = data['primary_p_GeV']
    r = data['reco_p_GeV']
    c = data['confirmed']
    y = data['y_lepton']
    subsets = dict(all=np.ones(len(p), bool), confirmed=c, unconfirmed=~c,
                   primary_invalid=~data['primary_valid'])
    for name, value in [('reco_p', r), ('truth_p', p), ('confirmed_truth_p', p)]:
        support = c if name.startswith('confirmed') else np.ones(len(p), bool)
        for lo, hi, suffix in [(100, 1000, '100_1000'), (100, 250, '100_250'),
                               (250, 1000, '250_1000'), (1000, np.inf, 'ge1000')]:
            subsets[name + '_' + suffix] = support & (value >= lo) & (value < hi)
    for lo, hi in zip(cfg['energy_edges_GeV'][:-1], cfg['energy_edges_GeV'][1:]):
        subsets[f'energy_{lo}_{hi}'] = (data['truth_E_GeV'] >= lo) & (data['truth_E_GeV'] < hi)
    for lo, hi in zip(cfg['y_edges'][:-1], cfg['y_edges'][1:]):
        m = (y >= lo) & ((y <= hi) if hi == 1 else (y < hi))
        subsets[f'y_{lo}_{hi}'] = m
        subsets[f'confirmed_y_{lo}_{hi}'] = m & c
    subsets['confirmed_truth_p_100_1000_y_ge0p8'] = c & (p >= 100) & (p < 1000) & (y >= .8) & (y <= 1)
    subsets['y_missing_or_outside'] = ~np.isfinite(y) | (y < 0) | (y > 1)
    for component in np.unique(data['component']):
        subsets['component_' + component] = data['component'] == component
        if component in ['pi', 'sibyll_pi']:
            for lo, hi in zip(cfg['energy_edges_GeV'][:-1], cfg['energy_edges_GeV'][1:]):
                subsets[f'component_{component}_energy_{lo}_{hi}'] = ((data['component'] == component) &
                    (data['truth_E_GeV'] >= lo) & (data['truth_E_GeV'] < hi))
    return subsets


def macro_result(residual, y, mask, gid, weights, offset, boots, edges, active=None):
    masks = [mask & (y >= lo) & (y < hi) for lo, hi in zip(edges[:-1], edges[1:])]
    if active is None:
        active = [i for i, m in enumerate(masks) if m.sum() >= 100]
    central = []
    sampled = []
    for i in active:
        m = masks[i]
        central.append(float(np.mean((residual[m] + offset) ** 2)))
        n = weights @ np.bincount(gid[m], minlength=weights.shape[1])
        sums = weights @ np.bincount(gid[m], weights=residual[m], minlength=weights.shape[1])
        sums2 = weights @ np.bincount(gid[m], weights=residual[m] ** 2, minlength=weights.shape[1])
        with np.errstate(divide='ignore', invalid='ignore'):
            sampled.append(sums2 / n + 2 * boots * sums / n + boots ** 2)
    if not active:
        return np.nan, np.full(len(weights), np.nan), []
    return np.sqrt(np.mean(central)), np.sqrt(np.maximum(0, np.mean(sampled, axis=0))), active


def evaluate(repo, part):
    out = reportdir(repo)
    assert not (out / f'{part}_summary.json').exists(), 'Evaluation already published; do not silently overwrite'
    if part == 'challenge':
        assert (out / 'test_summary.json').exists()
    tick = time.perf_counter()
    cpu = time.process_time()
    cfg = configuration(repo)
    state = json.loads((out / 'calibration_state.json').read_text())
    calibration = read_cache(repo, 'calibration')
    data = read_cache(repo, part)
    assert not set(calibration['group']) & set(data['group'])
    rng = np.random.default_rng(cfg['bootstrap_seed'] + (0 if part == 'test' else 1))
    cboots = calibration_bootstrap(calibration, rng, cfg['bootstrap_replicates'])
    group_names, gid, weights = draws(data['group'], rng, cfg['bootstrap_replicates'])
    raw = logs(data)
    truth = np.log(data['truth_E_GeV'])
    methods = {'mu_raw': (np.log(data['reco_p_GeV']), 0., np.zeros(len(weights))),
               'mu_div0p8': (np.log(data['reco_p_GeV'] / .8), 0., np.zeros(len(weights)))}
    for v in ['F5', 'F6']:
        methods[v + '_raw'] = (raw[v], 0., np.zeros(len(weights)))
        methods[v + '_cal'] = (raw[v], state['offset_log'][v], cboots[v])
    subsets = strata(data, cfg)
    table = []
    store = {}
    for name, mask in subsets.items():
        for model, (logpred, correction, bs) in methods.items():
            row = dict(partition=part, subset=name, model=model, N=int(mask.sum()),
                       source_groups=len(np.unique(data['group'][mask])))
            if not mask.any():
                for k in METRICS:
                    row.update({k: np.nan, k + '_lo': np.nan, k + '_hi': np.nan, k + '_invalid_boot': len(weights)})
                table.append(row)
                continue
            values = metric_values(data['truth_E_GeV'], np.exp(logpred + correction), mask)
            samples = sufficient_bootstrap((logpred - truth)[mask], gid[mask], weights, bs)
            for k in METRICS:
                lo, hi, invalid = intervals(samples[k])
                row.update({k: values[k], k + '_lo': lo, k + '_hi': hi, k + '_invalid_boot': invalid})
            store[name, model] = values, samples
            table.append(row)
    write_table(out / f'{part}_metrics.tsv', table)
    comparisons = []
    for name in subsets:
        for old, new in [('F5_cal', 'F6_cal'), ('F5_raw', 'F6_raw'), ('mu_div0p8', 'F5_cal')]:
            if (name, old) not in store:
                continue
            a, ab = store[name, old]
            b, bb = store[name, new]
            row = dict(partition=part, subset=name, reference=old, candidate=new, N=a['N'])
            differences = {k + '_delta': (b[k] - a[k], bb[k] - ab[k]) for k in METRICS}
            differences['relative_log_RMSE_gain'] = (1 - b['log_RMSE'] / a['log_RMSE'], 1 - bb['log_RMSE'] / ab['log_RMSE'])
            for k, (point, samples) in differences.items():
                lo, hi, invalid = intervals(samples)
                row.update({k: point, k + '_lo': lo, k + '_hi': hi, k + '_invalid_boot': invalid})
            comparisons.append(row)
    write_table(out / f'{part}_paired.tsv', comparisons)
    macro = []
    macro_store = {}
    for subset in ['all'] + [k for k in subsets if k.startswith('component_') and '_energy_' not in k]:
        for model, (logpred, correction, bs) in methods.items():
            point, boot, active = macro_result(logpred - truth, data['truth_E_GeV'], subsets[subset], gid, weights,
                                               correction, bs, cfg['energy_edges_GeV'])
            lo, hi, invalid = intervals(boot)
            macro.append(dict(partition=part, subset=subset, model=model, macro_log_RMSE=point, lo=lo, hi=hi,
                              invalid_boot=invalid, active_bins=','.join(map(str, active))))
            macro_store[subset, model] = point, boot
    write_table(out / f'{part}_macro.tsv', macro)
    # Descriptive MC response, never used to select or correct a deployment model.
    muon = []
    for subset in ['all', 'confirmed', 'unconfirmed', 'confirmed_truth_p_100_1000',
                   'confirmed_truth_p_100_250', 'confirmed_truth_p_250_1000', 'confirmed_truth_p_ge1000',
                   'confirmed_truth_p_100_1000_y_ge0p8']:
        mask = subsets[subset] & data['primary_valid'] & (data['primary_p_GeV'] > 0)
        if not mask.any():
            continue
        values = metric_values(data['primary_p_GeV'], data['reco_p_GeV'], mask)
        sampled = sufficient_bootstrap(np.log(data['reco_p_GeV'][mask] / data['primary_p_GeV'][mask]),
                                      gid[mask], weights, np.zeros(len(weights)))
        row = dict(partition=part, subset=subset, N=int(mask.sum()), source_groups=len(np.unique(data['group'][mask])))
        for k in METRICS:
            lo, hi, invalid = intervals(sampled[k])
            row.update({k: values[k], k + '_lo': lo, k + '_hi': hi, k + '_invalid_boot': invalid})
        muon.append(row)
    write_table(out / f'{part}_muon_production_response.tsv', muon)
    a, ab = macro_store['all', 'F5_cal']
    b, bb = macro_store['all', 'F6_cal']
    gain = 1 - b / a
    lo, hi, invalid = intervals(1 - bb / ab)
    focus = next(r for r in comparisons if r['subset'] == 'reco_p_100_1000' and r['reference'] == 'F5_cal')
    summary = dict(partition=part, created_utc=stamp(), events=len(truth), groups=len(group_names),
                   confirmed=int(data['confirmed'].sum()), primary_invalid=int((~data['primary_valid']).sum()),
                   macro_F5_cal=a, macro_F6_cal=b, macro_relative_gain=gain, macro_gain_lo=lo, macro_gain_hi=hi,
                   macro_invalid_boot=invalid, focus_relative_gain=focus['relative_log_RMSE_gain'],
                   focus_gain_lo=focus['relative_log_RMSE_gain_lo'], focus_gain_hi=focus['relative_log_RMSE_gain_hi'],
                   extension_criterion_passed=bool(gain >= cfg['minimum_relative_gain'] and lo > 0 and
                                                  focus['relative_log_RMSE_gain_lo'] > -cfg['focus_noninferiority_margin']),
                   calibration_offset_95={v: list(intervals(cboots[v])[:2]) for v in ['F5', 'F6']},
                   wall_s=time.perf_counter() - tick, cpu_s=time.process_time() - cpu,
                   peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
                   zero_new_model_fits=True, bootstrap_replicates=len(weights),
                   bootstrap_scope='paired evaluation source groups plus independent calibration groups')
    save_json(out / f'{part}_summary.json', summary)
    print(json.dumps(summary), flush=True)


def challenge_comparison(repo):
    """Common truth-energy support, keeping nominal pi distinct from all-component mix."""
    cfg = configuration(repo)
    out = reportdir(repo)
    state = json.loads((out / 'calibration_state.json').read_text())
    sets = {p: read_cache(repo, p) for p in ['test', 'challenge']}
    edges = cfg['energy_edges_GeV']
    masks = {p: (d['component'] == ('pi' if p == 'test' else 'sibyll_pi')) for p, d in sets.items()}
    active = [i for i, (lo, hi) in enumerate(zip(edges[:-1], edges[1:]))
              if all(np.sum(masks[p] & (d['truth_E_GeV'] >= lo) & (d['truth_E_GeV'] < hi)) >= 100 for p, d in sets.items())]
    rng = np.random.default_rng(cfg['bootstrap_seed'] + 2)
    cb = calibration_bootstrap(read_cache(repo, 'calibration'), rng, cfg['bootstrap_replicates'])
    rows = []
    values = {}
    for part, data in sets.items():
        _, gid, weights = draws(data['group'], rng, cfg['bootstrap_replicates'])
        for version, logpred in logs(data).items():
            point, boot, used = macro_result(logpred - np.log(data['truth_E_GeV']), data['truth_E_GeV'], masks[part],
                                            gid, weights, state['offset_log'][version], cb[version], edges, active=active)
            lo, hi, invalid = intervals(boot)
            rows.append(dict(partition=part, component='pi' if part == 'test' else 'sibyll_pi', model=version + '_cal',
                             N=int(masks[part].sum()), source_groups=len(np.unique(data['group'][masks[part]])),
                             common_bins=','.join(map(str, used)), macro_log_RMSE=point, lo=lo, hi=hi, invalid_boot=invalid))
            values[part, version] = point, boot
    write_table(out / 'challenge_pi_common_energy.tsv', rows)
    contrasts = []
    for version in ['F5', 'F6']:
        nominal, nominal_boot = values['test', version]
        challenge, challenge_boot = values['challenge', version]
        lo, hi, invalid = intervals(challenge_boot - nominal_boot)
        contrasts.append(dict(comparison='SIBYLL_pi_minus_nominal_pi', model=version + '_cal',
                              macro_delta=challenge - nominal, lo=lo, hi=hi, invalid_boot=invalid))
    for part in ['test', 'challenge']:
        a, ab = values[part, 'F5']
        b, bb = values[part, 'F6']
        lo, hi, invalid = intervals(bb - ab)
        contrasts.append(dict(comparison=part + '_F6_minus_F5', model='paired', macro_delta=b - a,
                              lo=lo, hi=hi, invalid_boot=invalid))
    write_table(out / 'challenge_pi_contrasts.tsv', contrasts)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--partition', required=True, choices=['test', 'challenge'])
    a = p.parse_args()
    evaluate(a.repo, a.partition)
    if a.partition == 'challenge':
        challenge_comparison(a.repo)


if __name__ == '__main__':
    main()
