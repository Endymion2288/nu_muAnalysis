#!/usr/bin/env python3
"""Replay stage26 source partitions, paired toy counts and independent profiles."""
import json
import time
from pathlib import Path

import numpy as np

from check_profile_response import scan_profile
from profile_response import nll
from source_response import (ALPHAS, aggregate, config, counts_from_uniform, event_basis,
                             load_events, make_response, random_partition, target_mix)


def main():
    tick = time.perf_counter(); root = Path(__file__).resolve().parents[1]; cfg = config(root)
    counts_checked = 0; partitions_checked = 0; center_scans = 0; null_scans = 0; toy_scans = 0; conditional_scans = 0
    maximum_global_nll = 0.; maximum_nll_replay = 0.; maximum_conditional_lr = 0.; common_checked = False
    assignments = {}
    for model, spec in cfg['models'].items():
        for seed in spec['seeds']:
            local_cfg = {**cfg, 'models': {model: {**spec, 'seeds': [seed]}}}
            y, bins, gi, groups, fold, predictions, runs, ri = load_events(root, local_cfg, model)
            basis, index, loge, reco = event_basis(y, bins, ri, predictions[0], len(runs), cfg)
            pool = aggregate(basis, index, np.ones(len(y)), len(runs)); target = target_mix(pool)
            with np.load(root / f'ml/artifacts/stage26/{model}/seed_{seed}/source_inference.npz') as z:
                d = {k:z[k] for k in z.files}
            np.testing.assert_array_equal(pool, d['pool']); np.testing.assert_array_equal(target, d['target'])
            original = fold[gi] == 'A'; a = aggregate(basis, index, original, len(runs))
            np.testing.assert_array_equal(np.stack([a, pool - a]), d['coefficients'])

            def replay_fits(response, counts, fits, losses, lrs):
                nonlocal maximum_nll_replay
                for trial, observed in enumerate(counts):
                    for mi in range(2):
                        point = fits[trial, mi]; loss = nll(response.at(point[6])[0], point[:6], observed / 1000)
                        difference = abs(loss - losses[trial, mi]); maximum_nll_replay = max(maximum_nll_replay, difference)
                        assert difference < 2e-11
                expected = np.maximum(2000 * (losses[:, 0] - losses[:, 1]), 0.)
                np.testing.assert_allclose(expected, lrs[:, 6], atol=1e-9, rtol=1e-9)

            for di in range(2):
                src, pseudo = d['coefficients'][di], d['coefficients'][1 - di]
                for ai, alpha in enumerate(ALPHAS):
                    uniforms = np.random.default_rng(np.random.SeedSequence([cfg['seed'], 26, 2, seed, di, ai])).random((200, 1000))
                    for ci in range(2):
                        response = make_response(src, target, ci); other = make_response(pseudo, target, ci)
                        expected = np.stack([other.at(alpha)[0] @ d['truth'][di], response.at(alpha)[0] @ d['truth'][di]])
                        np.testing.assert_allclose(expected, d['qs'][di, ai, ci], atol=1e-14, rtol=0)
                        q = expected[0]; loss = scan_profile(q, response, cfg)
                        difference = abs(loss - d['central_nll'][di, ai, ci, 1]); maximum_global_nll = max(maximum_global_nll, difference)
                        assert difference < 2e-8, (model, seed, di, ai, ci, difference); center_scans += 1
                        for li in range(2):
                            replay = np.stack([counts_from_uniform(expected[li], u) for u in uniforms])
                            np.testing.assert_array_equal(replay, d['toy_counts'][di, ai, ci, li]); counts_checked += 200
                            replay_fits(response, replay, d['toy_fits'][di, ai, ci, li], d['toy_nll'][di, ai, ci, li], d['toy_lr'][di, ai, ci, li])
                            if seed == 0 and di == 0 and ai == 1:
                                observed = replay[0] / 1000; best_loss = d['toy_nll'][di, ai, ci, li, 0, 1]
                                independent = scan_profile(observed, response, cfg); difference = abs(independent - best_loss)
                                maximum_global_nll = max(maximum_global_nll, difference); assert difference < 2e-8; toy_scans += 1
                                loss = scan_profile(observed, response, cfg, 5, float(d['truth'][di, 5]))
                                statistic = max(0., 2000 * (loss - best_loss))
                                difference = abs(statistic - d['toy_lr'][di, ai, ci, li, 0, 5])
                                maximum_conditional_lr = max(maximum_conditional_lr, difference); assert difference < 5e-5; conditional_scans += 1
            for ni in range(2):
                for trial in range(1000):
                    if not common_checked: assignments[ni, trial] = random_partition(ni, trial, ri, bins, gi, groups, fold, cfg)
                    assigned = assignments[ni, trial]
                    if not common_checked:
                        actual = np.bincount((assigned.astype(int) * len(runs) + ri) * 6 + bins, minlength=2 * len(runs) * 6).reshape(2, len(runs), 6)[::-1]
                        np.testing.assert_array_equal(actual, d['null_counts'][ni, trial]); partitions_checked += 1
                        if ni == 0:
                            np.testing.assert_array_equal(actual, d['coefficients'][:, 0].sum(axis=-1))
                        else:
                            for group in range(len(groups)): assert len(np.unique(assigned[gi == group])) == 1
                            components = np.array([g.split(':')[0] for g in groups])
                            chosen = np.array([assigned[gi == group][0] for group in range(len(groups))])
                            for c in set(components):
                                assert np.sum(chosen & (components == c)) == np.sum((fold == 'A') & (components == c))
                    if (ni != 0 or trial >= 200) and trial not in [0, 200]: continue
                    a = aggregate(basis, index, assigned, len(runs)); split = [a, pool - a]
                    for di in range(2):
                        src, pseudo = split[di], split[1 - di]
                        ftrue = pseudo[0].sum(axis=(0, 2)); ftrue /= ftrue.sum()
                        np.testing.assert_allclose(ftrue, d['null_truth'][ni, trial, di], atol=1e-14, rtol=0)
                        for ci in range(2):
                            try: response = make_response(src, target, ci); other = make_response(pseudo, target, ci)
                            except ValueError:
                                assert not d['null_support'][ni, trial, di, ci]; continue
                            assert d['null_support'][ni, trial, di, ci]
                            # Audit fixed first positions of each null, both cases/directions/alphas.
                            if trial in [0, 200]:
                                for ai, alpha in enumerate(ALPHAS):
                                    q = other.at(alpha)[0] @ ftrue
                                    loss = scan_profile(q, response, cfg)
                                    difference = abs(loss - d['null_nll'][ni, trial, di, ai, ci, 1]); maximum_global_nll = max(maximum_global_nll, difference)
                                    assert difference < 2e-8; null_scans += 1
                            if ni != 0 or trial >= 200: continue
                            u = np.random.default_rng(np.random.SeedSequence([cfg['seed'], 26, 3, seed, trial, di])).random(1000)
                            laws = [other.at(0.)[0] @ ftrue, response.at(0.)[0] @ ftrue]
                            for li, q in enumerate(laws):
                                counts = counts_from_uniform(q, u)
                                np.testing.assert_array_equal(counts, d['perm_counts'][trial, di, ci, li]); counts_checked += 1
                                replay_fits(response, counts[None], d['perm_fits'][trial, di, ci, li][None],
                                            d['perm_nll'][trial, di, ci, li][None], d['perm_lr'][trial, di, ci, li][None])
                                if seed == 0 and di == 0 and trial == 0:
                                    best_loss = d['perm_nll'][trial, di, ci, li, 1]
                                    independent = scan_profile(counts / 1000, response, cfg)
                                    difference = abs(independent - best_loss); maximum_global_nll = max(maximum_global_nll, difference)
                                    assert difference < 2e-8; toy_scans += 1
                                    independent = scan_profile(counts / 1000, response, cfg, 5, float(ftrue[5]))
                                    statistic = max(0., 2000 * (independent - best_loss))
                                    difference = abs(statistic - d['perm_lr'][trial, di, ci, li, 5]); maximum_conditional_lr = max(maximum_conditional_lr, difference)
                                    assert difference < 5e-5; conditional_scans += 1
            common_checked = True
            print(f'checked {model} seed={seed}', flush=True)
    result = dict(toy_counts_replayed=counts_checked, common_label_partitions_checked=partitions_checked,
                  central_global_scans=center_scans, selected_null_point_scans=null_scans, selected_toy_global_scans=toy_scans,
                  selected_fraction_lr_scans=conditional_scans, maximum_global_nll_difference=maximum_global_nll,
                  maximum_toy_nll_difference=maximum_nll_replay, maximum_selected_fraction_lr_difference=maximum_conditional_lr,
                  all_alpha_lrs_recomputed=True, calibration_test_challenge_evaluated=False, wall_s=time.perf_counter() - tick)
    (root / 'workbook/stage26_energy_ml/independent_checks.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__': main()
