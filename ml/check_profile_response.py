#!/usr/bin/env python3
"""Independent grid profiles, toy replay and endpoint checks for stage25."""
import json
import time
from pathlib import Path

import numpy as np
from scipy.optimize import minimize, minimize_scalar

from closure import fit_shape, load_data, read_table
from profile_response import Response, config, moments, nll
from within_response import histograms, pseudo_shapes


def convex(q, r, cfg, fixed_bin=None, value=None):
    if fixed_bin is None:
        f, info = fit_shape(r, q, cfg)
        assert info['status'] == 'ok'
        return float(-q @ np.log(np.maximum(r @ f, 1e-15)))
    indices = np.flatnonzero(np.arange(6) != fixed_bin)
    if value >= 1 - 1e-14:
        p = r[:, fixed_bin]
        return np.inf if np.any((p == 0) & (q > 0)) else float(-q @ np.log(np.maximum(p, 1e-15)))
    def objective(x):
        probability = np.maximum(r[:, fixed_bin] * value + r[:, indices] @ x, 1e-15)
        return -q @ np.log(probability), -r[:, indices].T @ (q / probability)
    result = minimize(objective, np.full(5, (1 - value) / 5), jac=True, method='SLSQP',
                      bounds=[(0., 1 - value)] * 5,
                      constraints={'type': 'eq', 'fun': lambda x: x.sum() - (1 - value), 'jac': lambda x: np.ones(5)},
                      options={'ftol': 1e-13, 'maxiter': 500})
    assert result.success, result.message
    return float(result.fun)


def scan_profile(q, response, cfg, fixed_bin=None, value=None):
    grid = np.linspace(-3, 3, 25)
    objective = lambda alpha: convex(q, response.at(alpha)[0], cfg, fixed_bin, value)
    losses = np.array([objective(a) for a in grid])
    index = int(np.argmin(losses))
    low, high = grid[max(0, index - 1)], grid[min(24, index + 1)]
    result = minimize_scalar(objective, method='bounded', bounds=(low, high), options={'xatol': 1e-7})
    return min(float(losses[index]), float(result.fun))


def main():
    tick = time.perf_counter(); root = Path(__file__).resolve().parents[1];out = root / 'workbook/stage25_energy_ml';cfg = config(root)
    intervals = read_table(out / 'intervals.tsv'); centers_checked = 0; toys_checked = 0; endpoints_checked = 0
    max_center_loss = 0.; max_toy_loss = 0.; max_endpoint_lr = 0.; max_nll_difference = 0.; counts_replayed = 0
    reproduction = []
    for model, spec in cfg['models'].items():
        for seed in spec['seeds']:
            with np.load(root / f'ml/artifacts/stage25/{model}/seed_{seed}/inference.npz') as saved: data = {k: saved[k] for k in saved.files}
            for di, direction in enumerate(['A_to_B', 'B_to_A']):
                response = Response(data['coefficients'][di])
                for ai, alpha in enumerate([-1., 0., 1.]):
                    q = data['qs'][di, ai, 0]
                    mle = data['central'][di, ai, 1];loss = data['central_nll'][di, ai, 1]
                    independent = scan_profile(q, response, cfg)
                    difference = abs(independent - loss);max_center_loss = max(max_center_loss, difference)
                    assert difference < 2e-8, (model, seed, direction, alpha, difference)
                    assert abs(mle[:6].sum() - 1) < 1e-9 and mle[:6].min() >= 0 and abs(mle[6]) <= 3
                    centers_checked += 1
                    for li, law in enumerate(cfg['toy_laws']):
                        trng = np.random.default_rng(np.random.SeedSequence([cfg['seed'], 24, seed, di, ai, li]))
                        counts = trng.multinomial(1000, data['qs'][di, ai, li], size=200)
                        np.testing.assert_array_equal(counts, data['toy_counts'][di, ai, li]); counts_replayed += 200
                        fits = data['toy_fits'][di, ai, li]; qtoy = counts / 1000
                        for mi in [0, 1]:
                            for ti, point in enumerate(fits[:, mi]):
                                probability = response.at(point[6])[0] @ point[:6]
                                actual = -qtoy[ti] @ np.log(np.maximum(probability, 1e-15))
                                max_nll_difference = max(max_nll_difference, abs(float(actual - data['toy_nll'][di, ai, li, ti, mi])))
                                assert abs(actual - data['toy_nll'][di, ai, li, ti, mi]) < 1e-11
                        lr_alpha = 2000 * (data['toy_nll'][di, ai, li, :, 0] - data['toy_nll'][di, ai, li, :, 1])
                        np.testing.assert_allclose(np.maximum(lr_alpha, 0), data['toy_lr'][di, ai, li, :, 1, 6], atol=1e-10, rtol=1e-10)
                        # One fixed, preregistered array position per cell audits
                        # the joint optimizer against a grid of convex fits.
                        ti = 0; qcheck = qtoy[ti]
                        independent = scan_profile(qcheck, response, cfg)
                        difference = abs(independent - data['toy_nll'][di, ai, li, ti, 1]);max_toy_loss = max(max_toy_loss, difference)
                        assert difference < 2e-8, (model, seed, direction, alpha, law, difference)
                        toys_checked += 1
                # A small fixed endpoint audit: nominal A->B, seed0, alpha and
                # highest f bin, plus the known-alpha highest-bin interval.
                if seed != 0 or di != 0: continue
                selected = [r for r in intervals if r['model'] == model and int(r['seed']) == seed and r['direction'] == direction
                            and float(r['alpha_injected']) == 0 and int(r['parameter']) in [5, 6]]
                q = data['qs'][di, 1, 0]
                for row in selected:
                    mi = ['known_alpha', 'profile_alpha'].index(row['method']);base = data['central_nll'][di, 1, mi]
                    parameter = int(row['parameter'])
                    for side in ['low', 'high']:
                        if row[side + '_limited'] == 'True': continue
                        value = float(row[side])
                        if parameter == 6: loss = convex(q, response.at(value)[0], cfg)
                        elif mi == 0: loss = convex(q, response.at(0.)[0], cfg, parameter, value)
                        else: loss = scan_profile(q, response, cfg, parameter, value)
                        statistic = 2000 * (loss - base)
                        max_endpoint_lr = max(max_endpoint_lr, abs(statistic - 1))
                        assert abs(statistic - 1) < 2e-4, (model, parameter, side, statistic)
                        endpoints_checked += 1
        # Audit the largest stage24/current known-alpha bootstrap difference
        # against the same reconstructed event response and objective.
        with np.load(root / f'ml/artifacts/stage24/{model}/bootstrap.npz') as prior:
            old_bias = prior['bias'][:, :, 2].copy()  # draw, alpha, seed, direction, bin
        current = []
        for seed in spec['seeds']:
            with np.load(root / f'ml/artifacts/stage25/{model}/seed_{seed}/inference.npz') as saved:
                current.append(saved['bootstrap'][..., 0, :6] / saved['boot_truth'][:, :, None, :] - 1)
        current = np.stack(current, axis=3).transpose(0, 2, 3, 1, 4)
        difference = abs(current - old_bias)
        bi, ai, si, di, _ = np.unravel_index(np.argmax(difference), difference.shape)
        seed = spec['seeds'][si]; local_cfg = {**cfg, 'models': {model: {**spec, 'seeds': [seed]}}}
        y, bins, gi, groups, folds, predictions = load_data(root, local_cfg, model, False)
        mh, _, _ = moments(y, bins, gi, predictions[0], len(groups), cfg)
        h, _, _ = histograms(y, bins, gi, predictions[0], len(groups), cfg)
        with np.load(root / f'ml/artifacts/stage25/{model}/seed_{seed}/inference.npz') as saved:
            draw = saved['draws'][bi]; new_f = saved['bootstrap'][bi, di, ai, 0, :6]
        rw = (folds == ['A', 'B'][di]).astype(float)
        response = Response(np.einsum('g,kgbr->kbr', rw * draw, mh))
        truth, q = pseudo_shapes(np.einsum('g,agkj->akj', (1 - rw) * draw, h))
        old_f = (old_bias[bi, ai, si, di] + 1) * truth
        r = response.at([-1., 0., 1.][ai])[0]
        loss_difference = abs(nll(r, old_f, q[ai]) - nll(r, new_f, q[ai]))
        assert loss_difference < 2e-11
        reproduction.append(dict(model=model, draw=int(bi), alpha_index=int(ai), seed=seed, direction=int(di),
                                 maximum_relative_bias_difference=float(difference.max()),
                                 maximum_fraction_difference=float(abs(old_f - new_f).max()),
                                 common_response_nll_difference=float(loss_difference)))
    result = dict(central_global_profiles_independently_scanned=centers_checked, selected_toy_profiles_independently_scanned=toys_checked,
                  toy_counts_replayed=counts_replayed, endpoint_roots_checked=endpoints_checked,
                  maximum_central_nll_difference=max_center_loss, maximum_selected_toy_nll_difference=max_toy_loss,
                  maximum_endpoint_lr_difference=max_endpoint_lr, maximum_toy_nll_difference=max_nll_difference,
                  all_alpha_lr_recomputed=True, stage24_worst_difference_audits=reproduction,
                  calibration_test_challenge_evaluated=False, wall_s=time.perf_counter() - tick)
    (out / 'independent_checks.json').write_text(json.dumps(result, indent=2) + '\n');print(json.dumps(result, indent=2))


if __name__ == '__main__': main()
