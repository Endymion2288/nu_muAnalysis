#!/usr/bin/env python3
"""Aggregate stage23 paired source bootstrap and compact spectrum diagnostics."""
import argparse
import json
import resource
import time
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import yaml

from closure import SCHEMES, read_table, write_table


def save_svg(figure, path):
    figure.savefig(path)
    path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines()) + '\n')


def interval(values):
    valid = np.isfinite(values)
    bounds = np.quantile(values[valid], [.025, .975]) if valid.any() else [np.nan, np.nan]
    return dict(low95=float(bounds[0]), high95=float(bounds[1]), valid=int(valid.sum()),
                failure_fraction=float(1 - valid.mean()))


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--compact', action='store_true', help='Remove byte-verified, merged worker report shards')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = root / 'workbook/stage23_energy_ml'
    tick, cpu = time.perf_counter(), time.process_time()
    cfg = yaml.safe_load((root / 'ml/configs/closure.yaml').read_text())
    models = list(cfg['models'])
    tables = {}
    runs = {}
    for filename in ['metrics', 'closure_bins', 'response', 'correlations', 'reco_edges', 'selfchecks', 'toys', 'bootstrap_failures', 'flows']:
        rows = []
        for model in models:
            p = out / model / f'{filename}.tsv'
            if p.exists(): rows.extend(read_table(p))
        if rows:
            write_table(out / f'{filename}.tsv', rows)
        elif (out / f'{filename}.tsv').exists():
            rows = read_table(out / f'{filename}.tsv')
        tables[filename] = rows
    for model in models:
        p = out / model / 'summary.json'
        if p.exists(): runs[model] = json.loads(p.read_text())
        else: runs[model] = json.loads((out / 'summary.json').read_text())['runs'][model]
        run = runs[model]
        assert not run['smoke'] and run['events'] == 13375 and run['groups'] == 22
        assert run['bootstrap'] == 500 and run['toys'] == 200 and not run['calibration_test_challenge_evaluated']
    bootstrap = {}
    common = None
    for model in models:
        with np.load(root / f'ml/artifacts/stage23/{model}/bootstrap.npz') as data:
            bootstrap[model] = {k: data[k] for k in data.files}
        if common is None: common = bootstrap[model]['draws']
        else: np.testing.assert_array_equal(common, bootstrap[model]['draws'])
    summary_rows, bin_rows, pair_rows = [], [], []
    for model in models:
        data = bootstrap[model]
        for si, scheme in enumerate(SCHEMES):
            for ci, case in enumerate(cfg['cases']):
                for metric in ['bias', 'sigma']:
                    square = data[f'central_{metric}_sq'][si, ci]
                    center = float(np.sqrt(square.mean()))
                    boot = np.sqrt(data[f'{metric}_sq'][:, si, ci].mean(axis=-1)) if ci < 5 else None
                    stats = interval(boot) if boot is not None else dict(low95=np.nan, high95=np.nan, valid=0, failure_fraction=np.nan)
                    summary_rows.append(dict(model=model, scheme=scheme, case=case, metric=metric,
                                             value=center, high_bin=float(np.sqrt(square[-1])), **stats))
                    for b in range(6):
                        stats = interval(np.sqrt(data[f'{metric}_sq'][:, si, ci, b])) if ci < 5 else dict(low95=np.nan, high95=np.nan, valid=0, failure_fraction=np.nan)
                        bin_rows.append(dict(model=model, scheme=scheme, case=case, metric=metric, bin=b,
                                             value=float(np.sqrt(square[b])), **stats))
    for baseline, candidate in cfg['pairs']:
        for si, scheme in enumerate(SCHEMES):
            for ci, case in enumerate(cfg['bootstrap_cases']):
                for metric in ['bias', 'sigma']:
                    for b in [-1, 0, 1, 2, 3, 4, 5]:
                        points, boots = [], []
                        for model in [baseline, candidate]:
                            data = bootstrap[model]
                            point = data[f'central_{metric}_sq'][si, ci]
                            boot = data[f'{metric}_sq'][:, si, ci]
                            points.append(np.sqrt(point.mean() if b == -1 else point[b]))
                            boots.append(np.sqrt(boot.mean(axis=-1) if b == -1 else boot[:, b]))
                        pair_rows.append(dict(baseline=baseline, candidate=candidate, scheme=scheme, case=case,
                                              metric=metric, bin=b, delta=float(points[1] - points[0]),
                                              **interval(boots[1] - boots[0])))
    write_table(out / 'model_summary.tsv', summary_rows)
    write_table(out / 'bin_summary.tsv', bin_rows)
    write_table(out / 'paired_comparisons.tsv', pair_rows)
    # Descriptive paired contrasts of the frozen stresses against nominal;
    # this does not select a new stress exponent or refit a response.
    stress_rows = []
    for model in models:
        data = bootstrap[model]
        for si, scheme in enumerate(SCHEMES):
            for ci, case in enumerate(cfg['bootstrap_cases'][1:], start=1):
                for metric in ['bias', 'sigma']:
                    points = np.sqrt(data[f'central_{metric}_sq'][si].mean(axis=-1))
                    boots = np.sqrt(data[f'{metric}_sq'][:, si].mean(axis=-1))
                    stress_rows.append(dict(model=model, scheme=scheme, case=case, metric=metric,
                                            delta=float(points[ci] - points[0]),
                                            **interval(boots[:, ci] - boots[:, 0])))
    write_table(out / 'stress_changes.tsv', stress_rows)
    toy_summary = []
    for model in models:
        for scheme in SCHEMES:
            for b in range(6):
                rows = [r for r in tables['toys'] if r['model'] == model and r['scheme'] == scheme and int(r['bin']) == b]
                weights = np.array([int(r['valid']) for r in rows])
                average = lambda key: float(np.average([float(r[key]) for r in rows], weights=weights))
                toy_summary.append(dict(model=model, scheme=scheme, bin=b, toys=int(weights.sum()),
                                        failures=sum(int(r['failures']) for r in rows),
                                        boundary_frequency=average('boundary_frequency'),
                                        relative_rms=float(np.sqrt(np.average([float(r['relative_rms']) ** 2 for r in rows], weights=weights))),
                                        rms_relative_bias=float(np.sqrt(np.average([float(r['relative_bias']) ** 2 for r in rows], weights=weights))),
                                        pull_std=average('pull_std'), coverage_68=average('coverage_68')))
    write_table(out / 'toy_summary.tsv', toy_summary)
    # Source-fold composition is diagnostic, and uses validation only.
    with np.load(root / 'ntuples/energy_ml_stage12/dataset/validation.npz') as data:
        y, groups = data['ML_truth_E_GeV'], data['group']
    fold_map = {r['group']: r['fold'] for r in read_table(out / 'folds.tsv')}
    components = np.array([g.split(':')[0] for g in groups]); folds = np.array([fold_map[g] for g in groups])
    bins = np.searchsorted(cfg['truth_edges_GeV'], y, side='right') - 1
    source_rows = []
    for fold in ['A', 'B']:
        for b in range(6):
            mask = (folds == fold) & (bins == b)
            for component in ['charm', 'k', 'pi']:
                n = int(np.sum(mask & (components == component)))
                source_rows.append(dict(fold=fold, bin=b, component=component, events=n,
                                        fraction_in_bin=n / mask.sum()))
    write_table(out / 'source_composition.tsv', source_rows)
    checks = dict(rows={name: len(rows) for name, rows in tables.items()},
                  all_selfchecks_passed=all(r['passed'] == 'True' for r in tables['selfchecks']),
                  maximum_selfclosure_fraction_error=max(float(r['fraction_error']) for r in tables['selfchecks']),
                  maximum_selfclosure_reco_error=max(float(r['reco_error']) for r in tables['selfchecks']),
                  central_fit_failures=sum(r['status'] != 'ok' for r in tables['metrics']),
                  nonidentifiable_central=sum(r['identifiable'] != 'True' for r in tables['metrics']),
                  maximum_kkt=max(float(r['kkt']) for r in tables['metrics']),
                  paired_draws_identical=True)
    control = {}
    for key in ['bias_sq', 'sigma_sq', 'central_bias_sq', 'central_sigma_sq']:
        a, b = bootstrap['mu_p'][key], bootstrap['mu_p_over0p8'][key]
        axis = 1 if key in ['bias_sq', 'sigma_sq'] else 0
        ar, br = np.take(a, 1, axis=axis), np.take(b, 1, axis=axis)
        np.testing.assert_allclose(ar, br, rtol=0, atol=1e-12, equal_nan=True)
        control[key] = float(np.nanmax(abs(ar - br)))
    checks['mu_rank_scale_control'] = control
    assert checks['central_fit_failures'] == 0
    assert checks['nonidentifiable_central'] == 0
    assert checks['all_selfchecks_passed']
    # Scientific plots show descriptive central values; intervals are in tables.
    colors = plt.cm.tab10(np.arange(6))
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
    for ax, scheme in zip(axes, SCHEMES):
        for model, color in zip(models, colors):
            rows = [r for r in bin_rows if r['model'] == model and r['scheme'] == scheme and r['case'] == 'nominal' and r['metric'] == 'sigma']
            ax.plot(np.arange(6), [r['value'] * 100 for r in rows], 'o-', color=color, label=model)
        ax.set(title=f'{scheme} bins; known response, N=1000', ylabel='Relative spectrum uncertainty (%)', xlabel='True energy bin (GeV)')
        ax.set_xticks(np.arange(6), ['100–200', '200–400', '400–800', '800–1600', '1600–3200', '3200–6400'], rotation=40)
        ax.grid(alpha=.25); ax.set_ylim(bottom=0)
    axes[-1].legend(fontsize=8)
    save_svg(fig, out / 'information.svg'); plt.close(fig)
    fig, axes = plt.subplots(2, 2, figsize=(12, 7), constrained_layout=True)
    for si, scheme in enumerate(SCHEMES):
        for col, metric in enumerate(['bias', 'sigma']):
            ax = axes[si, col]
            for model, color in zip(models, colors):
                rows = [r for r in summary_rows if r['model'] == model and r['scheme'] == scheme and r['metric'] == metric]
                ax.plot(np.arange(6), [r['value'] * 100 for r in rows], 'o-', label=model, color=color)
            ax.set_title(f'{scheme}: ' + ('cross-source closure RMS' if metric == 'bias' else 'known-response statistical RMS, N=1000'))
            ax.set_xticks(np.arange(6), cfg['cases'], rotation=30, ha='right'); ax.set_ylabel('RMS relative fraction (%)'); ax.grid(alpha=.25)
    axes[0, 1].legend(fontsize=8)
    save_svg(fig, out / 'closure_stresses.svg'); plt.close(fig)
    summary = dict(runs=runs, checks=checks,
                   totals=dict(worker_wall_s=sum(r['wall_s'] for r in runs.values()), worker_cpu_s=sum(r['cpu_s'] for r in runs.values()),
                               peak_rss_KiB=max(r['max_rss_KiB'] for r in runs.values()),
                               bootstrap_direction_case_fits=500 * 2 * 5 * 2 * sum(r['seeds'] for r in runs.values()),
                               requested_toy_fits=200 * 2 * 2 * sum(r['seeds'] for r in runs.values())),
                   report_wall_s=time.perf_counter() - tick, report_cpu_s=time.process_time() - cpu,
                   report_peak_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    if args.compact:
        removed = []
        for model in models:
            folder = out / model
            if not folder.exists(): continue
            for p in folder.iterdir():
                if p.suffix == '.tsv':
                    shard = read_table(p)
                    merged = tables[p.stem]
                    assert [r for r in merged if r['model'] == model] == shard
                elif p.name == 'summary.json':
                    assert json.loads(p.read_text()) == runs[model]
                else: raise ValueError(f'Unrecognized shard {p}')
                removed.append(dict(path=str(p.relative_to(root)), bytes=p.stat().st_size)); p.unlink()
            folder.rmdir()
        (out / 'compaction.json').write_text(json.dumps(dict(removed=removed, bytes=sum(r['bytes'] for r in removed)), indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
