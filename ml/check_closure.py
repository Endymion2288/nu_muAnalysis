#!/usr/bin/env python3
"""Independent event-level reconstruction of stage23 response and shape inputs."""
import json
import time
from pathlib import Path

import numpy as np
import yaml

from closure import read_table


def main():
    tick = time.perf_counter()
    root = Path(__file__).resolve().parents[1]; out = root / 'workbook/stage23_energy_ml'
    cfg = yaml.safe_load((root / 'ml/configs/closure.yaml').read_text())
    with np.load(root / 'ntuples/energy_ml_stage12/dataset/validation.npz') as data:
        y, mu, groups = data['ML_truth_E_GeV'], data['ML_mu_p_GeV'], data['group']
        keys = {k: data[k] for k in ['run', 'eventID']}
    fold_map = {r['group']: r['fold'] for r in read_table(out / 'folds.tsv')}
    folds = np.array([fold_map[g] for g in groups]); components = np.array([g.split(':')[0] for g in groups])
    b = np.digitize(y, cfg['truth_edges_GeV']) - 1
    centers = np.sqrt(np.array(cfg['truth_edges_GeV'][:-1]) * cfg['truth_edges_GeV'][1:])
    bins_table = read_table(out / 'closure_bins.tsv')
    response_table = read_table(out / 'response.tsv'); edges_table = read_table(out / 'reco_edges.tsv')
    metric_table = read_table(out / 'metrics.tsv')
    worst_response, worst_truth, worst_sigma, worst_kkt = 0., 0., 0., 0.
    checked = 0
    for model, spec in cfg['models'].items():
        if spec.get('kind') == 'mu': predictions = [mu * spec['scale']]
        else:
            with np.load(root / spec['path']) as saved:
                for k in keys: np.testing.assert_array_equal(saved[k], keys[k])
                np.testing.assert_array_equal(saved['truth_E_GeV'], y)
                np.testing.assert_array_equal(saved['group'], groups)
                predictions = [saved[f'seed_{s}'] for s in spec['seeds']]
        for seed, scores in enumerate(predictions):
            for scheme in ['energy', 'rank']:
                for direction in ['A_to_B', 'B_to_A']:
                    selected = lambda r: r['model'] == model and int(r['seed']) == seed and r['scheme'] == scheme and r['direction'] == direction
                    source = folds == direction[0]; pseudo = ~source
                    ed = np.array([float(r['value_GeV']) for r in edges_table if selected(r)])
                    expected_edges = np.array(cfg['energy_reco_internal_GeV']) if scheme == 'energy' else np.quantile(scores[source], np.arange(1, 10) / 10)
                    np.testing.assert_array_equal(ed, expected_edges)
                    reco = np.digitize(scores, ed)
                    for case in cfg['cases']:
                        rw = source.astype(float); pw = pseudo.astype(float)
                        if case == 'component_matched':
                            for w in [rw, pw]:
                                total = w.sum()
                                for component in ['charm', 'k', 'pi']:
                                    mask = components == component
                                    w[mask] *= mask.mean() / (w[mask].sum() / total)
                        elif case != 'nominal':
                            weight = (y / (800 if case.startswith('tilt') else centers[b])) ** cfg['tilt_exponents'][case]
                            if case.startswith('within'):
                                for bb in range(6):
                                    mask = pseudo & (b == bb)
                                    weight[mask] *= mask.sum() / weight[mask].sum()
                            pw *= weight
                        hist = np.histogram2d(reco, b, bins=[np.arange(11) - .5, np.arange(7) - .5], weights=rw)[0]
                        response = hist / hist.sum(axis=0)
                        truth = np.bincount(b, weights=pw, minlength=6); truth /= truth.sum()
                        observed = np.bincount(reco, weights=pw, minlength=10); observed /= observed.sum()
                        rows = [r for r in bins_table if selected(r) and r['case'] == case]
                        fitted = np.array([float(r['fitted_fraction']) for r in rows])
                        saved_truth = np.array([float(r['true_fraction']) for r in rows])
                        worst_truth = max(worst_truth, np.max(abs(truth - saved_truth)))
                        np.testing.assert_allclose(truth, saved_truth, rtol=1e-12, atol=1e-13)
                        if case in ['nominal', 'component_matched']:
                            saved_response = np.array([float(r['probability']) for r in response_table if selected(r) and r['case'] == case]).reshape(10, 6)
                            worst_response = max(worst_response, np.max(abs(response - saved_response)))
                            np.testing.assert_allclose(response, saved_response, rtol=1e-12, atol=1e-13)
                        # Explicit independent tangent information calculation.
                        tangent = np.concatenate([np.eye(5), -np.ones((1, 5))], axis=0)
                        prob = response @ truth
                        a = response @ tangent
                        fisher = sum(np.outer(v, v) / p for v, p in zip(a, prob) if p > 0) * 1000
                        covariance = tangent @ np.linalg.inv(fisher) @ tangent.T
                        sigma = np.sqrt(np.diag(covariance)) / truth
                        saved_sigma = np.array([float(r['relative_sigma']) for r in rows])
                        worst_sigma = max(worst_sigma, np.max(abs(sigma - saved_sigma)))
                        np.testing.assert_allclose(sigma, saved_sigma, rtol=1e-10, atol=1e-10)
                        grad = -response.T @ (observed / np.maximum(response @ fitted, 1e-15))
                        active = fitted > 1e-7
                        lagrange = grad[active].mean()
                        kkt = max(np.max(abs(grad[active] - lagrange)), np.max(np.maximum(lagrange - grad[~active], 0), initial=0))
                        row = next(r for r in metric_table if selected(r) and r['case'] == case)
                        worst_kkt = max(worst_kkt, kkt)
                        np.testing.assert_allclose(float(row['kkt']), kkt, rtol=1e-6, atol=1e-10)
                        np.testing.assert_allclose(fitted.sum(), 1, atol=1e-10)
                        np.testing.assert_allclose([float(r['fractional_bias']) for r in rows], fitted / truth - 1, rtol=1e-10, atol=1e-11)
                        checked += 1
        # Reconstruct aggregate squared errors from signed per-direction values.
        with np.load(root / f'ml/artifacts/stage23/{model}/bootstrap.npz') as saved:
            for si, scheme in enumerate(['energy', 'rank']):
                for ci, case in enumerate(cfg['cases']):
                    for metric, column in [('bias', 'fractional_bias'), ('sigma', 'relative_sigma')]:
                        for bb in range(6):
                            rows = [r for r in bins_table if r['model'] == model and r['scheme'] == scheme and r['case'] == case and int(r['bin']) == bb]
                            expected = np.mean([float(r[column]) ** 2 for r in rows])
                            np.testing.assert_allclose(saved[f'central_{metric}_sq'][si, ci, bb], expected, rtol=1e-13, atol=1e-13)
            for f in ['A', 'B']:
                unique_groups = sorted(set(groups))
                mask = np.array([fold_map[g] == f for g in unique_groups])
                assert (saved['draws'][:, mask].sum(axis=1) == 11).all()
    result = dict(events=len(y), central_cases_checked=checked, maximum_response_difference=float(worst_response),
                  maximum_truth_fraction_difference=float(worst_truth), maximum_relative_sigma_difference=float(worst_sigma),
                  maximum_kkt=float(worst_kkt), independent_event_histograms=True, within_bin_normalization_verified=True,
                  seed_direction_aggregation_verified=True, fold_bootstrap_counts_verified=True,
                  wall_s=time.perf_counter() - tick, calibration_test_challenge_evaluated=False)
    (out / 'independent_checks.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__': main()
