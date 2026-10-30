#!/usr/bin/env python3
"""Summarize matched-source closure and conditional finite-pool randomization."""
import argparse
import json
import time
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from closure import read_table, write_table
from profile_response import METHODS
from report_closure import save_svg
from source_response import ALPHAS, CASES, NULLS, config


def rms(x, axes):
    return np.sqrt(np.mean(x ** 2, axis=axes))


def independent_mc(values):
    """Equal-sized independent seed/direction strata; final axis is trial."""
    v = values.reshape(-1, values.shape[-1])
    valid = np.isfinite(v)
    count = valid.sum(axis=-1); total = int(count.sum())
    mean = float(np.nanmean(v))
    variance = sum(n * np.var(a[ok], ddof=1) for a, ok, n in zip(v, valid, count) if n > 1)
    se = float(np.sqrt(variance) / total)
    return dict(value=mean, mc_se=se, valid=total, mc_low95=mean - 1.96 * se, mc_high95=mean + 1.96 * se)


def block_mc(values):
    """One independent block per shared source-label permutation."""
    v = values.reshape(len(values), -1)
    block = np.nanmean(v, axis=1); valid = np.isfinite(block); block = block[valid]
    mean = float(block.mean()); se = float(block.std(ddof=1) / np.sqrt(len(block)))
    return dict(value=mean, mc_se=se, valid=int(len(block)), mc_low95=mean - 1.96 * se, mc_high95=mean + 1.96 * se)


def coverage_difference(first, second):
    valid = np.isfinite(first) & np.isfinite(second)
    return np.where(valid, (first <= 1).astype(float) - (second <= 1).astype(float), np.nan)


def main():
    parser = argparse.ArgumentParser(__doc__); parser.add_argument('--compact', action='store_true'); args = parser.parse_args()
    tick = time.perf_counter(); root = Path(__file__).resolve().parents[1]; out = root / 'workbook/stage26_energy_ml'; cfg = config(root)
    identities = [(m, s) for m, spec in cfg['models'].items() for s in spec['seeds']]
    tables, runs, arrays = {}, {}, {}
    previous = json.loads((out / 'summary.json').read_text()) if (out / 'summary.json').exists() else {}
    for filename in ['metrics', 'composition', 'compression', 'failures']:
        rows = []
        for model, seed in identities:
            p = out / model / f'seed_{seed}/{filename}.tsv'
            if p.exists(): rows.extend(read_table(p))
        if rows: write_table(out / f'{filename}.tsv', rows)
        elif (out / f'{filename}.tsv').exists(): rows = read_table(out / f'{filename}.tsv')
        tables[filename] = rows
    common = None
    for model, seed in identities:
        key = f'{model}/seed_{seed}'; p = out / key / 'summary.json'
        run = json.loads(p.read_text()) if p.exists() else previous['runs'][key]; runs[key] = run
        assert run['events'] == 13375 and run['permutations_per_null'] == 1000 and run['observed_toys_per_cell'] == 200
        assert not run['smoke'] and not run['calibration_test_challenge_evaluated']
        with np.load(root / f'ml/artifacts/stage26/{key}/source_inference.npz') as data:
            arrays[model, seed] = {k: data[k] for k in data.files}
        d = arrays[model, seed]
        local = {k: d[k] for k in ['target', 'truth', 'null_truth', 'null_counts', 'null_support']}
        if common is None: common = local
        else:
            for k in local: np.testing.assert_array_equal(local[k], common[k])
    model_rows, tests, match_rows, cover_rows, global_rows, comparisons, reproduction, bins_rows = [], [], [], [], [], [], [], []
    references = {}
    for model, spec in cfg['models'].items():
        d = {k: np.stack([arrays[model, seed][k] for seed in spec['seeds']]) for k in arrays[model, spec['seeds'][0]]}
        s = len(spec['seeds']); truth = d['truth']
        bias = d['central'][..., :6] / truth[:, :, None, None, None, :] - 1
        alpha_error = d['central'][..., 6] - np.array(ALPHAS)[None, None, :, None, None]
        for seed in spec['seeds']:
            with np.load(root / f'ml/artifacts/stage25/{model}/seed_{seed}/inference.npz') as prior:
                difference = float(abs(arrays[model, seed]['central'][:, :, 0] - prior['central']).max())
                reproduction.append(dict(model=model, seed=seed, maximum_stage25_raw_parameter_difference=difference))
                assert difference < 3e-5
        for ai, alpha in enumerate(ALPHAS):
            for mi, method in enumerate(METHODS):
                for metric, a in [('closure_rms', bias), ('alpha_error_rms', alpha_error)]:
                    for ci, case in enumerate(CASES):
                        observed = float(rms(a[:, :, ai, ci, mi], tuple(range(a[:, :, ai, ci, mi].ndim))))
                        model_rows.append(dict(model=model, alpha_injected=alpha, case=case, method=method, metric=metric, value=observed))
                        for ni, null in enumerate(NULLS):
                            f = d['null_point'][:, ni, :, :, ai, ci, mi]
                            if metric == 'closure_rms':
                                residual = f[..., :6] / d['null_truth'][:, ni] - 1
                                samples = rms(residual, (0, 2, 3))
                            else:
                                samples = rms(f[..., 6] - alpha, (0, 2))
                            valid = np.isfinite(samples)
                            clean = samples[valid]; k = int(np.sum(clean >= observed)); n = len(clean)
                            row = dict(model=model, alpha_injected=alpha, case=case, method=method, metric=metric, null=null,
                                       observed=observed, requested=len(samples), valid=n, exceedances=k,
                                       p_plus_one=(k + 1) / (n + 1), null_mean=float(clean.mean()), null_median=float(np.median(clean)),
                                       null_low95=float(np.quantile(clean, .025)), null_high95=float(np.quantile(clean, .975)),
                                       primary=bool(alpha == 0 and method == 'profile_alpha'), holm_p=np.nan)
                            tests.append(row); references[model, ai, ci, mi, metric, ni] = samples
                raw = float(rms(bias[:, :, ai, 0, mi], (0, 1, 2))); matched = float(rms(bias[:, :, ai, 1, mi], (0, 1, 2)))
                for ni, null in enumerate(NULLS):
                    x = references[model, ai, 1, mi, 'closure_rms', ni] - references[model, ai, 0, mi, 'closure_rms', ni]
                    good = x[np.isfinite(x)]
                    match_rows.append(dict(model=model, alpha_injected=alpha, method=method, null=null,
                                           raw=raw, matched=matched, delta=matched - raw, valid=len(good),
                                           null_delta_median=float(np.median(good)), null_delta_low95=float(np.quantile(good, .025)),
                                           null_delta_high95=float(np.quantile(good, .975))))
                for ci, case in enumerate(CASES):
                    for bi in range(6):
                        bins_rows.append(dict(model=model, alpha_injected=alpha, case=case, method=method, truth_bin=bi,
                                              bias_signed_mean=float(bias[:, :, ai, ci, mi, bi].mean()),
                                              bias_rms=float(rms(bias[:, :, ai, ci, mi, bi], (0, 1)))))
            # Original-fold conditional coverage, paired across case and law.
            for ci, case in enumerate(CASES):
                for li, law in enumerate(cfg['toy_laws']):
                    lr = d['toy_lr'][:, :, ai, ci, li]  # seed,direction,toy,parameter
                    fits = d['toy_fits'][:, :, ai, ci, li, :, 1]
                    indicator = np.where(np.isfinite(lr), (lr <= 1).astype(float), np.nan)
                    perbin = []
                    for parameter in range(7):
                        stat = independent_mc(indicator[..., parameter]); perbin.append(stat['value'])
                        cover_rows.append(dict(model=model, ensemble='original_conditional', alpha_injected=alpha,
                                               case=case, law=law, parameter=parameter, **stat))
                    macro = independent_mc(np.mean(indicator[..., :6], axis=-1))
                    relative = fits[..., :6] / truth[:, :, None, :] - 1
                    fluctuation = (fits[..., :6] - fits[..., :6].mean(axis=2, keepdims=True)) / truth[:, :, None, :]
                    global_rows.append(dict(model=model, ensemble='original_conditional', alpha_injected=alpha, case=case, law=law,
                                            macro_coverage=macro['value'], macro_mc_se=macro['mc_se'], independent_blocks=macro['valid'],
                                            worst_bin_coverage=min(perbin[:6]), high_bin_coverage=perbin[5], alpha_coverage=perbin[6],
                                            relative_rmse=float(rms(relative, (0, 1, 2, 3))), relative_sd=float(rms(fluctuation, (0, 1, 2, 3))),
                                            alpha_rmse=float(rms(fits[..., 6] - alpha, (0, 1, 2))),
                                            alpha_domain_frequency=float(np.mean(abs(fits[..., 6]) >= 3 - 1e-6)),
                                            fraction_boundary_frequency=float(np.mean(np.any(fits[..., :6] < 1e-7, axis=-1)))))
                for li, law in enumerate(cfg['toy_laws']):
                    if ci != 1: continue
                    pair = d['toy_lr'][:, :, ai, :, li]
                    diff = coverage_difference(pair[:, :, 1], pair[:, :, 0])
                    for parameter in range(8):
                        values = diff[..., parameter] if parameter < 7 else diff[..., :6].mean(axis=-1)
                        stat = independent_mc(values)
                        comparisons.append(dict(model=model, ensemble='original_conditional', alpha_injected=alpha, case='paired_cases', law=law,
                                                comparison='matched_minus_raw', parameter=parameter if parameter < 7 else 'macro', **stat))
        # Alpha0 finite-pool split coverage; one cluster per shared partition.
        for ci, case in enumerate(CASES):
            for li, law in enumerate(cfg['toy_laws']):
                lr = d['perm_lr'][:, :, :, ci, li].transpose(1, 0, 2, 3)  # permutation,seed,direction,parameter
                fits = d['perm_fits'][:, :, :, ci, li, 1].transpose(1, 0, 2, 3)
                indicator = np.where(np.isfinite(lr), (lr <= 1).astype(float), np.nan); perbin = []
                for parameter in range(7):
                    stat = block_mc(indicator[..., parameter]); perbin.append(stat['value'])
                    cover_rows.append(dict(model=model, ensemble='event_split', alpha_injected=0., case=case, law=law, parameter=parameter, **stat))
                macro = block_mc(indicator[..., :6].mean(axis=-1))
                ftrue = d['null_truth'][:, 0, :d['perm_fits'].shape[1]].transpose(1, 0, 2, 3)
                relative = fits[..., :6] / ftrue - 1
                # Spread within each fixed seed/direction over both label and count draws.
                fluctuation = (fits[..., :6] - fits[..., :6].mean(axis=0, keepdims=True)) / ftrue
                global_rows.append(dict(model=model, ensemble='event_split', alpha_injected=0., case=case, law=law,
                                        macro_coverage=macro['value'], macro_mc_se=macro['mc_se'], independent_blocks=macro['valid'],
                                        worst_bin_coverage=min(perbin[:6]), high_bin_coverage=perbin[5], alpha_coverage=perbin[6],
                                        relative_rmse=float(rms(relative, (0, 1, 2, 3))), relative_sd=float(rms(fluctuation, (0, 1, 2, 3))),
                                        alpha_rmse=float(rms(fits[..., 6], (0, 1, 2))),
                                        alpha_domain_frequency=float(np.mean(abs(fits[..., 6]) >= 3 - 1e-6)),
                                        fraction_boundary_frequency=float(np.mean(np.any(fits[..., :6] < 1e-7, axis=-1)))))
                if ci == 1:
                    pair = d['perm_lr'][:, :, :, :, li].transpose(1, 0, 2, 3, 4)
                    diff = coverage_difference(pair[..., 1, :], pair[..., 0, :])
                    for parameter in range(8):
                        stat = block_mc(diff[..., parameter] if parameter < 7 else diff[..., :6].mean(axis=-1))
                        comparisons.append(dict(model=model, ensemble='event_split', alpha_injected=0., case='paired_cases', law=law,
                                                comparison='matched_minus_raw', parameter=parameter if parameter < 7 else 'macro', **stat))
            # Shared uniforms also pair cross-source and control coverage.
            for ensemble in ['original_conditional', 'event_split']:
                alpha_indices = range(3) if ensemble == 'original_conditional' else [1]
                for ai in alpha_indices:
                    if ensemble == 'original_conditional':
                        pair = d['toy_lr'][:, :, ai, ci]
                        diff = coverage_difference(pair[:, :, 0], pair[:, :, 1])
                    else:
                        pair = d['perm_lr'][:, :, :, ci].transpose(1, 0, 2, 3, 4)
                        diff = coverage_difference(pair[..., 0, :], pair[..., 1, :])
                    for parameter in range(8):
                        values = diff[..., parameter] if parameter < 7 else diff[..., :6].mean(axis=-1)
                        stat = independent_mc(values) if ensemble == 'original_conditional' else block_mc(values)
                        comparisons.append(dict(model=model, ensemble=ensemble, alpha_injected=ALPHAS[ai], case=case, law='paired_laws',
                                                comparison='cross_minus_control', parameter=parameter if parameter < 7 else 'macro', **stat))
    primary = sorted([r for r in tests if r['primary']], key=lambda r: r['p_plus_one']); assert len(primary) == 24
    current = 0.
    for i, row in enumerate(primary):
        current = max(current, min(1., (len(primary) - i) * row['p_plus_one'])); row['holm_p'] = current
    for name, rows in [('model_summary', model_rows), ('randomization_tests', tests), ('matching_changes', match_rows),
                       ('bin_summary', bins_rows), ('coverage_summary', cover_rows), ('toy_summary', global_rows),
                       ('coverage_comparisons', comparisons), ('stage25_reproduction', reproduction)]: write_table(out / f'{name}.tsv', rows)
    fig, axes = plt.subplots(2, 3, figsize=(12, 6), constrained_layout=True)
    for column, model in enumerate(cfg['models']):
        for row_index, metric in enumerate(['closure_rms', 'alpha_error_rms']):
            ax = axes[row_index, column]; scale = 100 if metric == 'closure_rms' else 1
            for ci, case in enumerate(CASES):
                point = next(r['value'] for r in model_rows if r['model'] == model and r['case'] == case and r['alpha_injected'] == 0 and r['method'] == 'profile_alpha' and r['metric'] == metric)
                ax.plot(ci, scale * point, '*', color='black', ms=11, label='Original source split' if ci == 0 else None)
                for ni, null in enumerate(NULLS):
                    samples = references[model, 1, ci, 1, metric, ni]; samples = samples[np.isfinite(samples)]
                    low, med, high = np.quantile(samples, [.025, .5, .975]); x = ci + (ni - .5) * .18
                    ax.errorbar(x, scale * med, yerr=[[scale * (med - low)], [scale * (high - med)]], fmt='o', color=f'C{ni}', capsize=4,
                                label=null + ' 95% reference' if ci == 0 else None)
            ax.set(xticks=[0, 1], xticklabels=['Raw', 'Run/bin matched'], title=model,
                   ylabel='Closure RMS (%)' if metric == 'closure_rms' else 'Alpha error RMS'); ax.grid(alpha=.25)
    axes[0, -1].legend(fontsize=6); save_svg(fig, out / 'source_randomization.svg'); plt.close(fig)
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.5), sharey=True, constrained_layout=True)
    for ax, model in zip(axes, cfg['models']):
        for ci, case in enumerate(CASES):
            for li, law in enumerate(cfg['toy_laws']):
                rows = [r for r in cover_rows if r['model'] == model and r['ensemble'] == 'original_conditional' and r['case'] == case and r['law'] == law and r['parameter'] == 5]
                ax.errorbar(ALPHAS, [100 * r['value'] for r in rows], yerr=[100 * r['mc_se'] for r in rows],
                            fmt='o-' if li == 0 else 's--', color=f'C{ci}', capsize=2, label=f'{case}, {law}')
        ax.axhline(68.2689, color='gray', lw=1); ax.set(title=model, xlabel='Injected alpha', ylabel='Highest-bin profile coverage (%)'); ax.grid(alpha=.25)
    axes[-1].legend(fontsize=6); save_svg(fig, out / 'matched_coverage.svg'); plt.close(fig)
    summary = dict(runs=runs, table_rows={k:len(v) for k,v in tables.items()}, shared_randomization_counts_identical=True,
                   primary_tests=24, holm_rejections=sum(r['holm_p'] < .05 for r in primary),
                   numerical_failure_cells=sum(r['failure_cells'] for r in runs.values()),
                   unsupported_cases=sum(r['unsupported_cases'] for r in runs.values()),
                   totals=dict(worker_wall_s=sum(r['wall_s'] for r in runs.values()), worker_cpu_s=sum(r['cpu_s'] for r in runs.values()),
                               peak_rss_KiB=max(r['max_rss_KiB'] for r in runs.values()), solver_calls=sum(r['numerical_stats']['solver_calls'] for r in runs.values()),
                               solver_failures=sum(r['numerical_stats']['solver_failures'] for r in runs.values()),
                               model_observed_uniform_block_instances=sum(r['independent_observed_uniform_blocks'] for r in runs.values()),
                               unique_observed_rng_blocks=len(set(s for spec in cfg['models'].values() for s in spec['seeds'])) * 2 * 3 * 200,
                               unique_event_rng_blocks=len(set(s for spec in cfg['models'].values() for s in spec['seeds'])) * 2 * 200,
                               shared_permutations_per_null=1000, shared_event_coverage_partitions=200), report_wall_s=time.perf_counter() - tick)
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
