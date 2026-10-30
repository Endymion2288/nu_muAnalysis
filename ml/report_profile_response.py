#!/usr/bin/env python3
"""Physics summary of actual known/unknown within-bin shape profile inference."""
import argparse
import json
import time
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from closure import read_table, write_table
from profile_response import METHODS, config
from report_closure import interval, save_svg
from within_response import ALPHAS


def rmse(x, axes):
    return np.sqrt(np.mean(x ** 2, axis=axes))


def coverage_statistics(indicator, valid):
    """Stratified independent toy Monte Carlo error; fixed seed/direction laws."""
    counts = valid.sum(axis=-1); success = np.sum(indicator & valid, axis=-1)
    total = int(counts.sum()); p = float(success.sum() / total) if total else np.nan
    proportions = np.divide(success, counts, out=np.zeros_like(success, dtype=float), where=counts > 0)
    se = float(np.sqrt(np.sum(counts * proportions * (1 - proportions))) / total) if total else np.nan
    return dict(valid=total, coverage=p, mc_se=se, mc_low95=max(0., p - 1.96 * se), mc_high95=min(1., p + 1.96 * se))


def main():
    parser = argparse.ArgumentParser(__doc__); parser.add_argument('--compact', action='store_true')
    args = parser.parse_args(); tick = time.perf_counter()
    root = Path(__file__).resolve().parents[1]; out = root / 'workbook/stage25_energy_ml'; cfg = config(root)
    identities = [(m, s) for m, spec in cfg['models'].items() for s in spec['seeds']]
    tables = {}; runs = {}; arrays = {}
    for filename in ['metrics', 'estimates', 'intervals', 'toys', 'toy_global', 'failures', 'compression']:
        rows = []
        for model, seed in identities:
            p = out / model / f'seed_{seed}/{filename}.tsv'
            if p.exists(): rows.extend(read_table(p))
        if rows: write_table(out / f'{filename}.tsv', rows)
        elif (out / f'{filename}.tsv').exists(): rows = read_table(out / f'{filename}.tsv')
        tables[filename] = rows
    old_runs = json.loads((out / 'summary.json').read_text())['runs'] if (out / 'summary.json').exists() else {}
    common = None
    for model, seed in identities:
        key = f'{model}/seed_{seed}'; p = out / key / 'summary.json'
        run = json.loads(p.read_text()) if p.exists() else old_runs[key]; runs[key] = run
        assert run['events'] == 13375 and run['bootstrap'] == 500 and run['toys_per_cell'] == 200 and not run['smoke']
        assert not run['calibration_test_challenge_evaluated']
        with np.load(root / f'ml/artifacts/stage25/{key}/inference.npz') as data: arrays[model, seed] = {k: data[k] for k in data.files}
        draws = arrays[model, seed]['draws']
        if common is None: common = draws
        else: np.testing.assert_array_equal(common, draws)
    center_rows, gain_rows, coverage_rows, global_rows, coverage_gains, reproduction = [], [], [], [], [], []
    for model, spec in cfg['models'].items():
        data = {k: np.stack([arrays[model, s][k] for s in spec['seeds']]) for k in arrays[model, spec['seeds'][0]]}
        fractions = data['truth']
        point_bias = data['central'][..., :6] / fractions[:, :, None, None, :] - 1
        boot = np.moveaxis(data['bootstrap'], 1, 0)
        boot_truth = np.moveaxis(data['boot_truth'], 1, 0)
        boot_bias = boot[..., :6] / boot_truth[:, :, :, None, None, :] - 1
        shift = point_bias - point_bias[:, :, 1:2]
        boot_shift = boot_bias - boot_bias[:, :, :, 1:2]
        with np.load(root / f'ml/artifacts/stage24/{model}/bootstrap.npz') as prior:
            old_point = prior['central_bias']; old_boot = prior['bias']
            np.testing.assert_array_equal(common, prior['draws'])
        for ai, alpha in enumerate(ALPHAS):
            for mi, method in enumerate(METHODS):
                for metric, point_array, boot_array in [('closure', point_bias, boot_bias), ('shift', shift, boot_shift)]:
                    point = rmse(point_array[:, :, ai, mi], (0, 1, 2))
                    samples = rmse(boot_array[:, :, :, ai, mi], (1, 2, 3))
                    center_rows.append(dict(model=model, alpha_injected=alpha, method=method, metric=metric,
                                            value=float(point), **interval(samples)))
            profile_center = rmse(point_bias[:, :, ai, 1], (0, 1, 2))
            profile_boot = rmse(boot_bias[:, :, :, ai, 1], (1, 2, 3))
            for baseline in ['known_alpha', 'coarse6']:
                if baseline == 'known_alpha':
                    baseline_center = rmse(point_bias[:, :, ai, 0], (0, 1, 2))
                    baseline_boot = rmse(boot_bias[:, :, :, ai, 0], (1, 2, 3))
                else:
                    baseline_center = rmse(old_point[ai, 0], (0, 1, 2))
                    baseline_boot = rmse(old_boot[:, ai, 0], (1, 2, 3))
                gain_rows.append(dict(model=model, alpha_injected=alpha, baseline=baseline, candidate='profile_alpha',
                                      delta=float(profile_center - baseline_center), **interval(profile_boot - baseline_boot)))
            difference = float(np.max(abs(boot_bias[:, :, :, ai, 0] - old_boot[:, ai, 2])))
            reproduction.append(dict(model=model, alpha_injected=alpha, stage24_continuous_bootstrap_bias_max_difference=difference))
            for li, law in enumerate(cfg['toy_laws']):
                for mi, method in enumerate(METHODS):
                    local = data['toy_fits'][:, :, ai, li, :, mi]  # seed, direction, toy, parameter
                    lr = data['toy_lr'][:, :, ai, li, :, mi]
                    normalized = local[..., :6] / fractions[:, :, None, :] - 1
                    mean = local[..., :6].mean(axis=2, keepdims=True)
                    sd = (local[..., :6] - mean) / fractions[:, :, None, :]
                    valid_all = np.isfinite(lr[..., :6]).all(axis=-1)
                    mean_coverage = (lr[..., :6] <= 1).mean(axis=-1)
                    macro = float(mean_coverage[valid_all].mean())
                    within_variance = 0.
                    for s in range(len(spec['seeds'])):
                        for d in range(2):
                            v = mean_coverage[s, d, valid_all[s, d]]
                            within_variance += len(v) * np.var(v, ddof=1)
                    macro_se = float(np.sqrt(within_variance) / valid_all.sum())
                    coverages = []
                    for parameter in range(6 + mi):
                        valid = np.isfinite(lr[..., parameter])
                        stats = coverage_statistics(lr[..., parameter] <= 1, valid)
                        actual = fractions[:, :, parameter, None] if parameter < 6 else alpha
                        residual = local[..., parameter] - actual
                        if parameter < 6: residual /= actual
                        bias = float(np.nanmean(residual))
                        coverage_rows.append(dict(model=model, alpha_injected=alpha, law=law, method=method, parameter=parameter,
                                                  requested=int(valid.size), **stats, bias=bias, rmse=float(np.sqrt(np.nanmean(residual ** 2)))))
                        if parameter < 6: coverages.append(stats['coverage'])
                    global_rows.append(dict(model=model, alpha_injected=alpha, law=law, method=method,
                                            macro_coverage=macro, macro_mc_se=macro_se, worst_bin_coverage=float(min(coverages)),
                                            high_bin_coverage=float(coverages[-1]), relative_rmse=float(np.sqrt(np.nanmean(normalized ** 2))),
                                            relative_sd=float(np.sqrt(np.nanmean(sd ** 2))),
                                            alpha_bias=float(np.nanmean(local[..., 6] - alpha)),
                                            alpha_rmse=float(np.sqrt(np.nanmean((local[..., 6] - alpha) ** 2))),
                                            alpha_domain_frequency=float(np.mean(abs(local[..., 6]) > 3 - 1e-6)),
                                            fraction_boundary_frequency=float(np.mean(np.any(local[..., :6] < 1e-7, axis=-1)))))
                # Same toy counts make coverage changes paired, within each law.
                lrs = data['toy_lr'][:, :, ai, li]
                for parameter in range(6):
                    joint = np.isfinite(lrs[..., 0, parameter]) & np.isfinite(lrs[..., 1, parameter])
                    delta = (lrs[..., 1, parameter] <= 1).astype(float) - (lrs[..., 0, parameter] <= 1)
                    n = int(joint.sum()); point = float(delta[joint].mean()); variance = 0.
                    for s in range(len(spec['seeds'])):
                        for d in range(2):
                            v = delta[s, d, joint[s, d]]
                            variance += len(v) * np.var(v, ddof=1)
                    se = float(np.sqrt(variance) / n)
                    coverage_gains.append(dict(model=model, alpha_injected=alpha, law=law, parameter=parameter, valid=n,
                                               delta=point, mc_se=se, mc_low95=point - 1.96 * se, mc_high95=point + 1.96 * se))
    for name, rows in [('model_summary', center_rows), ('closure_comparisons', gain_rows), ('coverage_summary', coverage_rows),
                       ('toy_summary', global_rows), ('coverage_gains', coverage_gains), ('stage24_reproduction', reproduction)]: write_table(out / f'{name}.tsv', rows)
    checks = dict(table_rows={k: len(v) for k, v in tables.items()}, paired_draws_identical=True,
                  failed_intervals=sum(r['interval_status'] != 'ok' for r in tables['intervals']),
                  intervals_with_scan_reentry=sum(r['scan_reentry'] == 'True' for r in tables['intervals']),
                  domain_limited_intervals=sum(r['low_limited'] == 'True' or r['high_limited'] == 'True' for r in tables['intervals']),
                  maximum_kkt=max(float(r['kkt']) for r in tables['metrics']),
                  maximum_moment_response_error=max(float(r['response_max_difference']) for r in tables['compression']),
                  maximum_moment_derivative_error=max(float(r['derivative_max_difference']) for r in tables['compression']))
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.5), sharey=True, constrained_layout=True)
    for ax, model in zip(axes, cfg['models']):
        for mi, method in enumerate(METHODS):
            for li, law in enumerate(cfg['toy_laws']):
                rows = [r for r in global_rows if r['model'] == model and r['method'] == method and r['law'] == law]
                errors = [r for r in coverage_rows if r['model'] == model and r['method'] == method
                          and r['law'] == law and r['parameter'] == 5]
                ax.errorbar(ALPHAS, [100 * r['high_bin_coverage'] for r in rows],
                            yerr=[100 * r['mc_se'] for r in errors], fmt='o-' if li == 0 else 's--',
                            color=f'C{mi}', capsize=2, label=f'{method}, {law}')
        ax.axhline(68.2689, color='gray', lw=1); ax.set(title=model, xlabel='Injected within-bin alpha', ylabel='Highest-bin LR coverage (%)'); ax.grid(alpha=.25)
    axes[-1].legend(fontsize=6); save_svg(fig, out / 'profile_coverage.svg'); plt.close(fig)
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.5), sharey=True, constrained_layout=True)
    for ax, model in zip(axes, cfg['models']):
        rows = [r for r in global_rows if r['model'] == model and r['method'] == 'profile_alpha']
        for law in cfg['toy_laws']:
            local = [r for r in rows if r['law'] == law]
            ax.plot(ALPHAS, [100 * r['alpha_domain_frequency'] for r in local], 'o-', label=law)
        ax.set(title=model, xlabel='Injected within-bin alpha', ylabel='Alpha MLE at numerical bound (%)'); ax.grid(alpha=.25)
    axes[-1].legend(fontsize=8); save_svg(fig, out / 'alpha_boundaries.svg'); plt.close(fig)
    summary = dict(runs=runs, checks=checks, totals=dict(worker_wall_s=sum(r['wall_s'] for r in runs.values()),
                   worker_cpu_s=sum(r['cpu_s'] for r in runs.values()), peak_rss_KiB=max(r['max_rss_KiB'] for r in runs.values()),
                   independent_toys=sum(r['total_toys'] for r in runs.values()),
                   solver_calls=sum(r['numerical_stats']['solver_calls'] for r in runs.values()),
                   solver_failures=sum(r['numerical_stats']['solver_failures'] for r in runs.values()),
                   failure_cells=sum(r['failure_cells'] for r in runs.values())), report_wall_s=time.perf_counter() - tick)
    (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    if args.compact:
        removed = []
        for model, seed in identities:
            folder = out / model / f'seed_{seed}'
            if not folder.exists(): continue
            for p in folder.iterdir():
                if p.suffix == '.tsv': assert read_table(p) == [r for r in tables[p.stem] if r['model'] == model and int(r['seed']) == seed]
                elif p.name == 'summary.json': assert json.loads(p.read_text()) == runs[f'{model}/seed_{seed}']
                else: raise ValueError(p)
                removed.append(dict(path=str(p.relative_to(root)), bytes=p.stat().st_size)); p.unlink()
            folder.rmdir()
            if not any(folder.parent.iterdir()): folder.parent.rmdir()
        if removed: (out / 'compaction.json').write_text(json.dumps(dict(removed=removed, bytes=sum(r['bytes'] for r in removed)), indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__': main()
