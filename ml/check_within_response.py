#!/usr/bin/env python3
"""Independent event histograms and Schur-complement checks for stage24."""
import json
import time
from pathlib import Path

import numpy as np

from closure import read_table
from within_response import config


def main():
    root = Path(__file__).resolve().parents[1];out = root / 'workbook/stage24_energy_ml';cfg = config(root)
    tick = time.perf_counter()
    with np.load(root / 'ntuples/energy_ml_stage12/dataset/validation.npz') as data:
        y, mu, groups = data['ML_truth_E_GeV'], data['ML_mu_p_GeV'], data['group']
        keys = {k: data[k] for k in ['run', 'eventID']}
    folds = {r['group']: r['fold'] for r in read_table(root / 'workbook/stage23_energy_ml/folds.tsv')}
    fold = np.array([folds[g] for g in groups])
    bins = np.digitize(y, cfg['truth_edges_GeV']) - 1
    internal = np.digitize(y, 100 * 2 ** (np.arange(13) / 2)) - 1
    centers = np.sqrt(np.array(cfg['truth_edges_GeV'][:-1]) * cfg['truth_edges_GeV'][1:])
    loge = np.log(y / centers[bins]); tangent = np.vstack([np.eye(5), -np.ones(5)])
    table = read_table(out / 'closure_bins.tsv'); response_rows = read_table(out / 'response.tsv'); profile_rows = read_table(out / 'profile.tsv')
    maximum = dict(response=0., truth=0., sigma=0., profile_sigma=0., alpha_sigma=0., derivative=0., signed_bias=0.)
    counts = 0; all_arrays = {}
    for model, spec in cfg['models'].items():
        if spec.get('kind') == 'mu': predictions = [mu * spec['scale']]
        else:
            with np.load(root / spec['path']) as data:
                for k in keys: np.testing.assert_array_equal(data[k], keys[k])
                np.testing.assert_array_equal(data['group'], groups)
                np.testing.assert_array_equal(data['truth_E_GeV'], y)
                predictions = [data[f'seed_{s}'] for s in spec['seeds']]
        for si, scores in enumerate(predictions):
            reco = np.digitize(scores, cfg['energy_reco_internal_GeV'])
            for direction in ['A_to_B', 'B_to_A']:
                source = fold == direction[0]; pseudo = ~source
                select = lambda r: r['model'] == model and int(r['seed']) == si and r['direction'] == direction
                hsub = np.histogram2d(reco[source], internal[source], bins=[np.arange(11) - .5, np.arange(13) - .5])[0]
                rsub = hsub / hsub.sum(axis=0)
                h0 = hsub.reshape(10, 6, 2).sum(axis=-1); r0 = h0 / h0.sum(axis=0)
                true = np.bincount(bins[pseudo], minlength=6).astype(float); true /= true.sum()
                weighted_hist = lambda a: np.histogram2d(reco[source], bins[source], bins=[np.arange(11) - .5, np.arange(7) - .5], weights=(y[source] / centers[bins[source]]) ** a)[0]
                hlog = np.histogram2d(reco[source], bins[source], bins=[np.arange(11) - .5, np.arange(7) - .5], weights=loge[source])[0]
                slope = hlog / h0.sum(axis=0) - r0 * (hlog.sum(axis=0) / h0.sum(axis=0))
                step = 1e-5
                hm, hp = weighted_hist(-step), weighted_hist(step)
                fd = (hp / hp.sum(axis=0) - hm / hm.sum(axis=0)) / (2 * step)
                error = float(np.max(abs(slope - fd))); maximum['derivative'] = max(maximum['derivative'], error); assert error < 1e-8
                # Independent block inversion, rather than a 6x6 direct inverse.
                q = r0 @ true; a = r0 @ tangent; v = slope @ true
                positive = q > 0; q = q[positive]; a = a[positive]; v = v[positive]
                iff = 1000 * (a.T / q) @ a; cross = 1000 * a.T @ (v / q); iaa = 1000 * np.sum(v ** 2 / q)
                inv = np.linalg.inv(iff); residual = iaa - cross @ inv @ cross
                var_alpha = 1 / residual
                covariance = tangent @ (inv + np.outer(inv @ cross, inv @ cross) * var_alpha) @ tangent.T
                profile_sigma = np.sqrt(np.diag(covariance)) / true
                pr = next(r for r in profile_rows if select(r))
                error = abs(float(pr['alpha_sigma']) - np.sqrt(var_alpha)); maximum['alpha_sigma'] = max(maximum['alpha_sigma'], float(error))
                np.testing.assert_allclose(float(pr['alpha_sigma']), np.sqrt(var_alpha), rtol=1e-6)
                for alpha in [-1., 0., 1.]:
                    continuous_h = weighted_hist(alpha); continuous = continuous_h / continuous_h.sum(axis=0)
                    mixture = np.bincount(internal[source], weights=(y[source] / centers[bins[source]]) ** alpha, minlength=12).reshape(6, 2)
                    mixture /= mixture.sum(axis=1)[:, None]
                    fine = (rsub.reshape(10, 6, 2) * mixture[None, :, :]).sum(axis=-1)
                    for method, response in [('coarse6', r0), ('fine12', fine), ('continuous', continuous)]:
                        rows = [r for r in table if select(r) and float(r['alpha']) == alpha and r['method'] == method]
                        if alpha != 0 or method == 'coarse6':
                            saved = np.array([float(r['probability']) for r in response_rows if select(r) and float(r['alpha']) == alpha and r['method'] == method]).reshape(10, 6)
                            maximum['response'] = max(maximum['response'], float(np.max(abs(saved - response))))
                            np.testing.assert_allclose(saved, response, rtol=1e-12, atol=1e-13)
                        truth_saved = np.array([float(r['true_fraction']) for r in rows])
                        maximum['truth'] = max(maximum['truth'], float(np.max(abs(truth_saved - true))))
                        np.testing.assert_array_equal(truth_saved, true)
                        fitted = np.array([float(r['fitted_fraction']) for r in rows])
                        saved_bias = np.array([float(r['fractional_bias']) for r in rows])
                        maximum['signed_bias'] = max(maximum['signed_bias'], float(np.max(abs(saved_bias - (fitted / true - 1)))))
                        np.testing.assert_allclose(saved_bias, fitted / true - 1, atol=1e-13)
                        q = response @ true; design = response @ tangent
                        information = 1000 * sum(np.outer(row, row) / prob for row, prob in zip(design, q) if prob > 0)
                        cov = tangent @ np.linalg.inv(information) @ tangent.T; sigma = np.sqrt(np.diag(cov)) / true
                        saved_sigma = np.array([float(r['relative_sigma']) for r in rows])
                        maximum['sigma'] = max(maximum['sigma'], float(np.max(abs(saved_sigma - sigma))))
                        np.testing.assert_allclose(saved_sigma, sigma, rtol=1e-10, atol=1e-10)
                        saved_profile = np.array([float(r['profile_relative_sigma']) for r in rows])
                        maximum['profile_sigma'] = max(maximum['profile_sigma'], float(np.max(abs(saved_profile - profile_sigma))))
                        np.testing.assert_allclose(saved_profile, profile_sigma, rtol=1e-6)
                        counts += 1
        with np.load(root / f'ml/artifacts/stage24/{model}/bootstrap.npz') as data: all_arrays[model] = {k: data[k] for k in data.files}
    # Independent paired method contrasts, including the preregistered pooled metric.
    for row in read_table(out / 'method_comparisons.tsv'):
        d = all_arrays[row['model']]; metric = row['metric']; left = cfg['methods'].index(row['baseline']); right = cfg['methods'].index(row['candidate'])
        if metric == 'shift':
            center = d['central_bias'] - d['central_bias'][1:2]; boot = d['bias'] - d['bias'][:, 1:2]
        else:
            center = d['central_bias' if metric == 'closure' else 'central_sigma']; boot = d['bias' if metric == 'closure' else 'sigma']
        if row['case'] == 'pooled_pm':
            point = np.sqrt(np.mean(center[[0, 2]] ** 2, axis=(0, 2, 3, 4)))
            replicates = np.sqrt(np.mean(boot[:, [0, 2]] ** 2, axis=(1, 3, 4, 5)))
        else:
            ai = ['minus', 'nominal', 'plus'].index(row['case'])
            point = np.sqrt(np.mean(center[ai] ** 2, axis=(1, 2, 3)))
            replicates = np.sqrt(np.mean(boot[:, ai] ** 2, axis=(2, 3, 4)))
        delta = replicates[:, right] - replicates[:, left]; valid = np.isfinite(delta)
        quantiles = np.quantile(delta[valid], [.025, .975])
        np.testing.assert_allclose([float(row[k]) for k in ['delta', 'low95', 'high95']], [point[right] - point[left], *quantiles], rtol=1e-13, atol=1e-13)
        assert valid.sum() == int(row['valid'])
    result = dict(central_cases=counts, independent_event_histograms=True, schur_profile_verified=True,
                  maximum_absolute_differences=maximum, paired_comparisons_verified=90,
                  calibration_test_challenge_evaluated=False, wall_s=time.perf_counter() - tick)
    (out / 'independent_checks.json').write_text(json.dumps(result, indent=2) + '\n'); print(json.dumps(result, indent=2))


if __name__ == '__main__': main()
