#!/usr/bin/env python3
"""Stage25 point inference, actual profile sets, paired toys and source bootstrap."""
import argparse
import json
import platform
import resource
import time
from pathlib import Path

import numpy as np
import scipy

from closure import DIRECTIONS, fisher, load_data, write_table
from profile_response import METHODS, Inference, Response, config, moments, synthetic_checks
from within_response import ALPHAS, histograms, profile_information, pseudo_shapes, responses


def packed(result):
    return np.r_[result['f'], result['alpha']]


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--model', required=True); parser.add_argument('--seed-index', type=int, default=0)
    parser.add_argument('--output-dir', type=Path, required=True); parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args(); tick, cpu = time.perf_counter(), time.process_time()
    cfg = config(args.repo); si = args.seed_index
    assert si in cfg['models'][args.model]['seeds']
    cfg['models'][args.model]['seeds'] = [si]
    checks = synthetic_checks(cfg)
    out = args.output_dir; out.mkdir(parents=True, exist_ok=True)
    y, bins, gi, groups, folds, predictions = load_data(args.repo, cfg, args.model, args.smoke)
    scores = predictions[0]; ng = len(groups); nb, nt = (4, 4) if args.smoke else (cfg['bootstrap_replicates'], cfg['toys'])
    rng = np.random.default_rng(cfg['seed']); draws = np.zeros((nb, ng), dtype=int)
    for name in ['A', 'B']:
        indices = np.flatnonzero(folds == name)
        draws[:, indices] = rng.multinomial(len(indices), np.full(len(indices), 1 / len(indices)), size=nb)
    mh, loge, reco = moments(y, bins, gi, scores, ng, cfg)
    h, _, _ = histograms(y, bins, gi, scores, ng, cfg)
    coeffs = np.zeros((2, cfg['moment_order'] + 1, 6, 10)); truth = np.zeros((2, 6)); qs = np.zeros((2, 3, 2, 10))
    central = np.full((2, 3, 2, 7), np.nan); central_nll = np.full((2, 3, 2), np.nan)
    boots = np.full((nb, 2, 3, 2, 7), np.nan); boot_truth = np.full((nb, 2, 6), np.nan)
    fits = np.full((2, 3, 2, nt, 2, 7), np.nan); losses = np.full((2, 3, 2, nt, 2), np.nan)
    lr = np.full((2, 3, 2, nt, 2, 7), np.nan); toy_counts = np.zeros((2, 3, 2, nt, 10), dtype=np.int16)
    stats = dict(solver_calls=0, solver_failures=0, iterations=0)
    metrics, estimates, intervals, toy_rows, toy_global, failures, compression = [], [], [], [], [], [], []
    minimum_raw_lr = 0.; negative_lr_clipped = 0
    for di, direction in enumerate(DIRECTIONS):
        key = dict(model=args.model, seed=si, direction=direction)
        rw = (folds == direction[0]).astype(float); pw = 1 - rw
        coeff = np.einsum('g,kgbr->kbr', rw, mh); coeffs[di] = coeff
        response = Response(coeff); inference = Inference(response, cfg, stats)
        src = np.einsum('g,agkj->akj', rw, h); pseudo = np.einsum('g,agkj->akj', pw, h)
        ftrue, qcross = pseudo_shapes(pseudo); truth[di] = ftrue
        reference = responses(src)
        max_r, max_dr = 0., 0.
        for alpha in np.linspace(-3, 3, 13):
            weight = rw[gi] * np.exp(alpha * loge)
            direct = np.bincount(bins * 10 + reco, weights=weight, minlength=60).reshape(6, 10)
            d_direct = np.bincount(bins * 10 + reco, weights=weight * loge, minlength=60).reshape(6, 10)
            total = direct.sum(axis=-1)
            exact = (direct / total[:, None]).T
            slope = (d_direct / total[:, None]).T - exact * (d_direct.sum(axis=-1) / total)[None, :]
            r, dr = response.at(alpha)
            max_r = max(max_r, float(np.max(abs(r - exact)))); max_dr = max(max_dr, float(np.max(abs(dr - slope))))
        assert max_r < 1e-12 and max_dr < 1e-12
        compression.append(dict(**key, response_max_difference=max_r, derivative_max_difference=max_dr, grid_points=13))
        for ai, alpha in enumerate(ALPHAS):
            cell = dict(**key, alpha_injected=alpha)
            r, dr = response.at(alpha)
            qs[di, ai, 0] = qcross[ai]; qs[di, ai, 1] = reference[ai][2] @ ftrue
            bests = [inference.fit(qcross[ai], alpha), inference.fit(qcross[ai])]
            cov, _ = fisher(r, ftrue, cfg)
            sigmas = [np.r_[np.sqrt(np.diag(cov)), np.nan], np.full(7, np.nan)]
            sigma_profile, info_profile = profile_information(r, dr, ftrue, cfg)
            if sigma_profile is not None: sigmas[1] = np.r_[sigma_profile * ftrue, info_profile['alpha_sigma']]
            for mi, (method, best) in enumerate(zip(METHODS, bests)):
                central[di, ai, mi] = packed(best); central_nll[di, ai, mi] = best['nll']
                if best['status'] != 'ok': failures.append(dict(**cell, method=method, kind='central', trial=-1, parameter=-1, status=best['status'])); continue
                q = qcross[ai]; predicted = response.at(best['alpha'])[0] @ best['f']; positive = q > 0
                deviance = 2 * cfg['benchmark_selected_events'] * np.sum(q[positive] * np.log(q[positive] / np.maximum(predicted[positive], 1e-15)))
                metrics.append(dict(**cell, method=method, alpha_hat=best['alpha'], closure_rms=float(np.sqrt(np.mean((best['f'] / ftrue - 1) ** 2))),
                                    deviance_N1000=float(deviance), nll=best['nll'], kkt=best['kkt'], start_spread=best['start_spread'],
                                    fraction_boundaries=int(np.sum(best['f'] < 1e-7)), alpha_at_bound=bool(abs(best['alpha']) > 3 - 1e-6)))
                for parameter in range(7):
                    actual = ftrue[parameter] if parameter < 6 else alpha
                    estimate = packed(best)[parameter]
                    estimates.append(dict(**cell, method=method, parameter=parameter, truth=float(actual), estimate=float(estimate),
                                          bias=float(estimate / actual - 1) if parameter < 6 else float(estimate - actual),
                                          local_sigma=float(sigmas[mi][parameter])))
                parameters = ([5] if mi == 0 else [5, 6]) if args.smoke else range(6 + mi)
                if args.smoke and ai != 1: parameters = []
                for parameter in parameters:
                    interval = inference.interval(qcross[ai], best, parameter, alpha if mi == 0 else None)
                    intervals.append(dict(**cell, method=method, parameter=parameter, mle=float(packed(best)[parameter]), **interval))
        for ai, alpha in enumerate(ALPHAS):
            for li, law in enumerate(cfg['toy_laws']):
                cell = dict(**key, alpha_injected=alpha, law=law)
                trng = np.random.default_rng(np.random.SeedSequence([cfg['seed'], 24, si, di, ai, li]))
                counts = trng.multinomial(cfg['benchmark_selected_events'], qs[di, ai, li], size=nt)
                toy_counts[di, ai, li] = counts
                for ti, observed in enumerate(counts):
                    bests = [inference.fit(observed, alpha), inference.fit(observed)]
                    for mi, best in enumerate(bests):
                        fits[di, ai, li, ti, mi] = packed(best); losses[di, ai, li, ti, mi] = best['nll']
                        if best['status'] != 'ok':
                            failures.append(dict(**cell, method=METHODS[mi], kind='toy_fit', trial=ti, parameter=-1, status=best['status'])); continue
                        for parameter in range(6):
                            partial = inference.conditional(observed, best, parameter, ftrue[parameter], alpha if mi == 0 else None)
                            statistic, raw = inference.lr(partial, best)
                            if np.isfinite(raw): minimum_raw_lr = min(minimum_raw_lr, raw); negative_lr_clipped += int(raw < 0 and np.isfinite(statistic))
                            lr[di, ai, li, ti, mi, parameter] = statistic
                            if np.isnan(statistic): failures.append(dict(**cell, method=METHODS[mi], kind='toy_profile', trial=ti, parameter=parameter, status=partial['status'] if partial['status'] != 'ok' else 'negative_lr'))
                    statistic, raw = inference.lr(bests[0], bests[1])
                    if np.isfinite(raw): minimum_raw_lr = min(minimum_raw_lr, raw); negative_lr_clipped += int(raw < 0 and np.isfinite(statistic))
                    lr[di, ai, li, ti, 1, 6] = statistic
                    if np.isnan(statistic): failures.append(dict(**cell, method=METHODS[1], kind='toy_profile', trial=ti, parameter=6, status='alpha_lr'))
                for mi, method in enumerate(METHODS):
                    local = fits[di, ai, li, :, mi]
                    valid_point = np.isfinite(local).all(axis=-1)
                    toy_global.append(dict(**cell, method=method, toys=nt, valid=int(valid_point.sum()),
                                           fraction_boundary_frequency=float(np.mean(np.any(local[valid_point, :6] < 1e-7, axis=-1))),
                                           alpha_domain_frequency=float(np.mean(abs(local[valid_point, 6]) > 3 - 1e-6))))
                    cov, _ = fisher(response.at(alpha)[0], ftrue, cfg)
                    for parameter in range(6 + mi):
                        actual = ftrue[parameter] if parameter < 6 else alpha
                        values = local[:, parameter]; valid = np.isfinite(lr[di, ai, li, :, mi, parameter])
                        diff = values[valid_point] - actual
                        sigma = np.sqrt(cov[parameter, parameter]) if parameter < 6 else np.nan
                        toy_rows.append(dict(**cell, method=method, parameter=parameter, toys=nt, valid_profile=int(valid.sum()),
                                             coverage_lr=float(np.mean(lr[di, ai, li, valid, mi, parameter] <= cfg['likelihood_ratio_threshold'])),
                                             bias=float(diff.mean() / actual) if parameter < 6 else float(diff.mean()),
                                             rmse=float(np.sqrt(np.mean(diff ** 2)) / actual) if parameter < 6 else float(np.sqrt(np.mean(diff ** 2))),
                                             wald_known_coverage=float(np.mean(abs(diff) <= sigma)) if mi == 0 else np.nan))
                print(f'{args.model} seed={si} {direction} alpha={alpha} {law} toys complete', flush=True)
        for bi, draw in enumerate(draws):
            try: boot_response = Response(np.einsum('g,kgbr->kbr', rw * draw, mh))
            except ValueError:
                failures.append(dict(**key, alpha_injected=np.nan, method='all', kind='bootstrap', trial=bi, parameter=-1, status='empty_truth')); continue
            psh = np.einsum('g,agkj->akj', pw * draw, h)
            fractions, observed = pseudo_shapes(psh)
            if fractions is None:
                failures.append(dict(**key, alpha_injected=np.nan, method='all', kind='bootstrap', trial=bi, parameter=-1, status='empty_truth')); continue
            boot_truth[bi, di] = fractions
            boot_inference = Inference(boot_response, cfg, stats)
            for ai, alpha in enumerate(ALPHAS):
                for mi, method in enumerate(METHODS):
                    result = boot_inference.fit(observed[ai], alpha if mi == 0 else None)
                    boots[bi, di, ai, mi] = packed(result)
                    if result['status'] != 'ok': failures.append(dict(**key, alpha_injected=alpha, method=method, kind='bootstrap', trial=bi, parameter=-1, status=result['status']))
        print(f'{args.model} seed={si} {direction} bootstrap complete', flush=True)
    np.savez_compressed(out / 'inference.npz', coefficients=coeffs, truth=truth, qs=qs, central=central, central_nll=central_nll,
                        bootstrap=boots, boot_truth=boot_truth, draws=draws, toy_counts=toy_counts, toy_fits=fits, toy_nll=losses, toy_lr=lr)
    for row in failures: row.setdefault('law', 'not_applicable')
    for filename, rows in [('metrics', metrics), ('estimates', estimates), ('intervals', intervals), ('toys', toy_rows),
                           ('toy_global', toy_global), ('failures', failures), ('compression', compression)]: write_table(out / f'{filename}.tsv', rows)
    summary = dict(model=args.model, seed=si, smoke=args.smoke, events=len(y), groups=ng, bootstrap=nb, toys_per_cell=nt,
                   total_toys=2 * 3 * 2 * nt, numerical_stats=stats, failure_cells=len(failures), minimum_raw_lr=minimum_raw_lr,
                   negative_lr_clipped=negative_lr_clipped, synthetic_checks=checks, wall_s=time.perf_counter() - tick,
                   cpu_s=time.process_time() - cpu, max_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                   host=platform.node(), numpy=np.__version__, scipy=scipy.__version__, calibration_test_challenge_evaluated=False)
    (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n'); print(json.dumps(summary), flush=True)


if __name__ == '__main__': main()
