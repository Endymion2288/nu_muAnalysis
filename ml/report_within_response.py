#!/usr/bin/env python3
"""Paired physics summary for stage24 fixed within-bin shape integration."""
import argparse
import json
import time
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from closure import fisher, read_table, write_table
from report_closure import interval, save_svg
from within_response import ALPHAS, METHODS, config


CASES = ['minus', 'nominal', 'plus']


def rms(x, axes):
    return np.sqrt(np.mean(x ** 2, axis=axes))


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--compact', action='store_true')
    args = parser.parse_args(); tick = time.perf_counter()
    root = Path(__file__).resolve().parents[1]; out = root / 'workbook/stage24_energy_ml'; cfg = config(root)
    models = list(cfg['models']); runs = {}; tables = {}; arrays = {}
    for filename in ['metrics', 'closure_bins', 'response', 'internal_counts', 'profile', 'selfchecks', 'toys', 'failures']:
        rows = []
        for model in models:
            p = out / model / f'{filename}.tsv'
            if p.exists(): rows.extend(read_table(p))
        if rows: write_table(out / f'{filename}.tsv', rows)
        elif (out / f'{filename}.tsv').exists(): rows = read_table(out / f'{filename}.tsv')
        tables[filename] = rows
    old_runs = json.loads((out / 'summary.json').read_text())['runs'] if (out / 'summary.json').exists() else {}
    for model in models:
        p = out / model / 'summary.json'
        runs[model] = json.loads(p.read_text()) if p.exists() else old_runs[model]
        run = runs[model]
        assert not run['smoke'] and run['events'] == 13375 and run['bootstrap'] == 500 and run['toys_per_cell'] == 200
        assert not run['calibration_test_challenge_evaluated']
        with np.load(root / f'ml/artifacts/stage24/{model}/bootstrap.npz') as saved: arrays[model] = {k: saved[k] for k in saved.files}
    reference = arrays[models[0]]['draws']
    for model in models: np.testing.assert_array_equal(arrays[model]['draws'], reference)
    summary_rows, bin_rows, pair_rows, profile_rows, profile_bins, reproduction = [], [], [], [], [], []
    for model in models:
        data = arrays[model]
        shift = data['central_bias'] - data['central_bias'][1:2]
        boot_shift = data['bias'] - data['bias'][:, 1:2]
        point_metrics = {'shift': shift, 'closure': data['central_bias'], 'sigma': data['central_sigma']}
        boot_metrics = {'shift': boot_shift, 'closure': data['bias'], 'sigma': data['sigma']}
        for ai, case in enumerate(CASES):
            for mi, method in enumerate(METHODS):
                for metric in point_metrics:
                    point = rms(point_metrics[metric][ai, mi], (0, 1, 2))
                    boot = rms(boot_metrics[metric][:, ai, mi], (1, 2, 3))
                    summary_rows.append(dict(model=model, case=case, method=method, metric=metric,
                                             value=float(point), **interval(boot)))
                    for b in range(6):
                        point_bin = rms(point_metrics[metric][ai, mi, :, :, b], (0, 1))
                        boot_bin = rms(boot_metrics[metric][:, ai, mi, :, :, b], (1, 2))
                        bin_rows.append(dict(model=model, case=case, method=method, metric=metric, bin=b,
                                             value=float(point_bin), **interval(boot_bin)))
        primary = rms(shift[[0, 2]], (0, 2, 3, 4))
        boot_primary = rms(boot_shift[:, [0, 2]], (1, 3, 4, 5))
        for mi, method in enumerate(METHODS):
            summary_rows.append(dict(model=model, case='pooled_pm', method=method, metric='shift',
                                     value=float(primary[mi]), **interval(boot_primary[:, mi])))
        for baseline, candidate in cfg['method_pairs']:
            left, right = METHODS.index(baseline), METHODS.index(candidate)
            pair_rows.append(dict(model=model, case='pooled_pm', baseline=baseline, candidate=candidate, metric='shift',
                                  delta=float(primary[right] - primary[left]), **interval(boot_primary[:, right] - boot_primary[:, left])))
            for ai, case in enumerate(CASES):
                for metric in point_metrics:
                    point = rms(point_metrics[metric][ai], (1, 2, 3))
                    boot = rms(boot_metrics[metric][:, ai], (2, 3, 4))
                    pair_rows.append(dict(model=model, case=case, baseline=baseline, candidate=candidate, metric=metric,
                                          delta=float(point[right] - point[left]), **interval(boot[:, right] - boot[:, left])))
        fixed = rms(data['central_sigma'][1, 0], (0, 1, 2)); free = rms(data['profile_sigma'], (0, 1, 2))
        fixed_b = rms(data['sigma'][:, 1, 0], (1, 2, 3)); free_b = rms(data['boot_profile_sigma'], (1, 2, 3))
        profile_rows.append(dict(model=model, known_alpha_sigma_rms=float(fixed), profile_sigma_rms=float(free),
                                 sigma_inflation=float(free / fixed), delta=float(free - fixed), **interval(free_b - fixed_b),
                                 alpha_sigma_rms=float(rms(data['profile_alpha'], (0, 1)))))
        for b in range(6):
            for name, point_data, boot_data in [('known', data['central_sigma'][1, 0], data['sigma'][:, 1, 0]),
                                               ('profile', data['profile_sigma'], data['boot_profile_sigma'])]:
                profile_bins.append(dict(model=model, mode=name, bin=b, value=float(rms(point_data[:, :, b], (0, 1))),
                                         **interval(rms(boot_data[:, :, :, b], (1, 2)))))
        with np.load(root / f'ml/artifacts/stage23/{model}/bootstrap.npz') as old:
            np.testing.assert_array_equal(data['draws'], old['draws'])
            for ai, ci in [(0, 3), (1, 0), (2, 4)]:
                for metric, new_key, old_key in [('bias', 'bias', 'bias_sq'), ('sigma', 'sigma', 'sigma_sq')]:
                    new = (data[new_key][:, ai, 0] ** 2).mean(axis=(1, 2))
                    prior = old[old_key][:, 0, ci]
                    difference = float(np.nanmax(abs(new - prior)))
                    if ai == 1: np.testing.assert_allclose(new, prior, rtol=0, atol=1e-12)
                    reproduction.append(dict(model=model, alpha=ALPHAS[ai], metric=metric, max_bootstrap_square_difference=difference))
    for name, rows in [('model_summary', summary_rows), ('bin_summary', bin_rows), ('method_comparisons', pair_rows),
                       ('profile_summary', profile_rows), ('profile_bins', profile_bins), ('stage23_reproduction', reproduction)]: write_table(out / f'{name}.tsv', rows)
    toy_summary = []
    for model in models:
        for alpha in ALPHAS:
            for method in METHODS:
                for law in cfg['toy_laws']:
                    for b in range(6):
                        rows = [r for r in tables['toys'] if r['model'] == model and float(r['alpha']) == alpha and r['method'] == method and r['law'] == law and int(r['bin']) == b]
                        if not rows: continue
                        weights = np.array([int(r['valid']) for r in rows])
                        average = lambda k: float(np.average([float(r[k]) for r in rows], weights=weights))
                        toy_summary.append(dict(model=model, alpha=alpha, method=method, law=law, bin=b, valid=int(weights.sum()),
                                                failures=sum(int(r['failures']) for r in rows), boundary_frequency=average('boundary_frequency'),
                                                relative_rms=float(np.sqrt(np.average([float(r['relative_rms']) ** 2 for r in rows], weights=weights))),
                                                rms_relative_bias=float(np.sqrt(np.average([float(r['relative_bias']) ** 2 for r in rows], weights=weights))),
                                                pull_std=average('pull_std'), coverage_68=average('coverage_68')))
    write_table(out / 'toy_summary.tsv', toy_summary)
    # Central correlations are derived from retained matrices; no event reread
    # or additional spectrum fit is needed. Nominal duplicates share coarse6.
    matrix_groups = {}
    for row in tables['response']:
        key = (row['model'], row['seed'], row['direction'], row['alpha'], row['method'])
        matrix_groups.setdefault(key, []).append(float(row['probability']))
    correlations = []
    for key, values in matrix_groups.items():
        model, seed, direction, alpha, method = key
        rows = [r for r in tables['closure_bins'] if (r['model'], r['seed'], r['direction'], r['alpha'], r['method']) == key]
        fractions = np.array([float(r['true_fraction']) for r in rows])
        covariance, _ = fisher(np.array(values).reshape(10, 6), fractions, cfg)
        correlation = covariance / np.sqrt(np.outer(np.diag(covariance), np.diag(covariance)))
        for b in range(6):
            for other in range(6):
                correlations.append(dict(model=model, seed=seed, direction=direction, alpha=alpha, method=method,
                                         bin=b, other_bin=other, correlation=float(correlation[b, other])))
    write_table(out / 'correlations.tsv', correlations)
    checks = dict(table_rows={k: len(v) for k, v in tables.items()}, paired_draws_identical=True,
                  all_selfchecks_passed=all(r['passed'] == 'True' for r in tables['selfchecks']),
                  maximum_selfclosure_fraction_error=max(float(r['fraction_error']) for r in tables['selfchecks']),
                  maximum_selfclosure_reco_error=max(float(r['reco_error']) for r in tables['selfchecks']),
                  central_fit_failures=sum(r['status'] != 'ok' for r in tables['metrics']),
                  maximum_kkt=max(float(r['kkt']) for r in tables['metrics']))
    assert checks['all_selfchecks_passed'] and checks['central_fit_failures'] == 0
    for model in models:
        for name in ['central_bias', 'central_sigma', 'bias', 'sigma']:
            axis = 0 if name.startswith('central') else 1
            nominal = np.take(arrays[model][name], 1, axis=axis)
            base = nominal[:, 0] if axis == 1 else nominal[0]
            for mi in [1, 2]:
                other = nominal[:, mi] if axis == 1 else nominal[mi]
                joint = np.isfinite(base) & np.isfinite(other)
                np.testing.assert_array_equal(base[joint], other[joint])
    checks['nominal_methods_identical'] = True
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.5), sharey=True, constrained_layout=True)
    for ax, model in zip(axes, models):
        for method in METHODS:
            rows = [r for r in summary_rows if r['model'] == model and r['method'] == method and r['metric'] == 'shift' and r['case'] != 'pooled_pm']
            ax.plot(ALPHAS, [r['value'] * 100 for r in rows], 'o-', label=method)
        ax.set(title=model, xlabel='Within-bin injection alpha', ylabel='Induced spectrum shift RMS (%)'); ax.set_xticks(ALPHAS); ax.grid(alpha=.25)
    axes[-1].legend(fontsize=8); save_svg(fig, out / 'within_shifts.svg'); plt.close(fig)
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.7), sharey=True, constrained_layout=True)
    for ax, model in zip(axes, models):
        for mode in ['known', 'profile']:
            rows = [r for r in profile_bins if r['model'] == model and r['mode'] == mode]
            ax.plot(range(6), [r['value'] * 100 for r in rows], 'o-', label=f'alpha {mode}')
        ax.set(title=model, xlabel='True energy bin (GeV)', ylabel='Relative statistical sigma (%)', yscale='log')
        ax.set_xticks(range(6), ['100–200', '200–400', '400–800', '800–1600', '1600–3200', '3200–6400'], rotation=40); ax.grid(alpha=.25)
    axes[-1].legend(fontsize=8); save_svg(fig, out / 'shape_information.svg'); plt.close(fig)
    summary = dict(runs=runs, checks=checks, totals=dict(worker_wall_s=sum(r['wall_s'] for r in runs.values()),
                   worker_cpu_s=sum(r['cpu_s'] for r in runs.values()), peak_rss_KiB=max(r['max_rss_KiB'] for r in runs.values()),
                   fits={k: sum(r['total_fits'][k] for r in runs.values()) for k in ['central', 'bootstrap', 'selfcheck', 'toy']}),
                   report_wall_s=time.perf_counter() - tick)
    (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    if args.compact:
        removed = []
        for model in models:
            folder = out / model
            if not folder.exists(): continue
            for p in folder.iterdir():
                if p.suffix == '.tsv': assert read_table(p) == [r for r in tables[p.stem] if r['model'] == model]
                elif p.name == 'summary.json': assert json.loads(p.read_text()) == runs[model]
                else: raise ValueError(p)
                removed.append(dict(path=str(p.relative_to(root)), bytes=p.stat().st_size)); p.unlink()
            folder.rmdir()
        if removed: (out / 'compaction.json').write_text(json.dumps(dict(removed=removed, bytes=sum(r['bytes'] for r in removed)), indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__': main()
