#!/usr/bin/env python3
"""Fixed-alpha source-crossed shape integration, bootstraps and paired toys."""
import argparse
import json
import platform
import resource
import time
from pathlib import Path

import numpy as np
import scipy

from closure import DIRECTIONS, evaluate, fit_shape, load_data, write_table
from within_response import (ALPHAS, METHODS, config, derivative, histograms,
                             profile_information, pseudo_shapes, responses, synthetic_checks)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--model', required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args(); tick, cpu = time.perf_counter(), time.process_time()
    cfg = config(args.repo); checks = synthetic_checks(cfg)
    out = args.output_dir; out.mkdir(parents=True, exist_ok=True)
    y, bins, gi, groups, fold, predictions = load_data(args.repo, cfg, args.model, args.smoke)
    nb, nt = (8, 8) if args.smoke else (cfg['bootstrap_replicates'], cfg['toys'])
    ns = len(predictions)
    rng = np.random.default_rng(cfg['seed']); draws = np.zeros((nb, len(groups)), dtype=int)
    for name in ['A', 'B']:
        indices = np.flatnonzero(fold == name)
        draws[:, indices] = rng.multinomial(len(indices), np.full(len(indices), 1 / len(indices)), size=nb)
    central_bias = np.full((3, 3, ns, 2, 6), np.nan)
    central_sigma = np.full_like(central_bias, np.nan)
    boot_bias = np.full((nb, 3, 3, ns, 2, 6), np.nan)
    boot_sigma = np.full_like(boot_bias, np.nan)
    profile_sigma = np.full((ns, 2, 6), np.nan)
    profile_alpha = np.full((ns, 2), np.nan)
    boot_profile_sigma = np.full((nb, ns, 2, 6), np.nan)
    boot_profile_alpha = np.full((nb, ns, 2), np.nan)
    metrics, perbin, matrix_rows, subcounts, profiles, selfchecks, toys, failures = [], [], [], [], [], [], [], []
    total_fits = dict(central=0, bootstrap=0, selfcheck=0, toy=0)
    for si, scores in enumerate(predictions):
        hist, hlog, sub = histograms(y, bins, gi, scores, len(groups), cfg)
        for di, direction in enumerate(DIRECTIONS):
            key = dict(model=args.model, seed=si, direction=direction)
            rw = (fold == direction[0]).astype(float); pw = 1 - rw
            source = np.einsum('g,agkj->akj', rw, hist)
            pseudo = np.einsum('g,agkj->akj', pw, hist)
            mats = responses(source); truth, qs = pseudo_shapes(pseudo)
            assert truth is not None
            source_log = np.einsum('g,gkj->kj', rw, hlog)
            sigma_profile, profile = profile_information(mats[1][0], derivative(source[1], source_log), truth, cfg)
            profiles.append(dict(**key, **profile))
            if sigma_profile is not None:
                profile_sigma[si, di] = sigma_profile; profile_alpha[si, di] = profile['alpha_sigma']
            for k in range(12):
                subcounts.append(dict(**key, internal_bin=k, low_GeV=float(100 * 2 ** (k / 2)),
                                      high_GeV=float(100 * 2 ** ((k + 1) / 2)),
                                      response_events=float(source[1, k].sum()), pseudo_events=float(pseudo[1, k].sum())))
            nominal_result = evaluate(mats[1][0], truth, qs[1], cfg); total_fits['central'] += 1
            fitted_cache = {}
            for ai, alpha in enumerate(ALPHAS):
                for mi, method in enumerate(METHODS):
                    response = mats[ai][mi]; cell = dict(**key, alpha=alpha, method=method)
                    if response is None:
                        failures.append(dict(**cell, kind='central', replicate=-1, status='empty_internal_truth'))
                        continue
                    if ai == 1: result = nominal_result
                    else:
                        result = evaluate(response, truth, qs[ai], cfg); total_fits['central'] += 1
                    fitted, bias, sigma, cov, info = result
                    metrics.append(dict(**cell, **info))
                    central_bias[ai, mi, si, di] = bias; central_sigma[ai, mi, si, di] = sigma
                    fitted_cache[ai, mi] = (fitted, sigma * truth)
                    for b in range(6):
                        perbin.append(dict(**cell, bin=b, true_fraction=float(truth[b]),
                                           fitted_fraction=float(fitted[b]) if fitted is not None else np.nan,
                                           fractional_bias=float(bias[b]), relative_sigma=float(sigma[b]),
                                           profile_relative_sigma=float(profile_sigma[si, di, b])))
                    if ai == 1 and mi != 0: continue
                    for j in range(10):
                        for b in range(6): matrix_rows.append(dict(**cell, reco_bin=j, truth_bin=b, probability=float(response[j, b])))
                    recovered, check = fit_shape(response, response @ truth, cfg); total_fits['selfcheck'] += 1
                    ferror = float(np.max(abs(recovered - truth))) if recovered is not None else np.inf
                    qerror = float(np.max(abs(response @ recovered - response @ truth))) if recovered is not None else np.inf
                    selfchecks.append(dict(**cell, fraction_error=ferror, reco_error=qerror,
                                           passed=bool(check['status'] == 'ok' and ferror < 2e-5 and qerror < 1e-7)))
            # A separate RNG per seed/direction/law/alpha prevents one method from
            # consuming random numbers that would change another method's toys.
            for ai, alpha in enumerate(ALPHAS):
                for li, law in enumerate(cfg['toy_laws']):
                    trng = np.random.default_rng(np.random.SeedSequence([cfg['seed'], 24, si, di, ai, li]))
                    mean = qs[ai] if law == 'cross_source' else mats[ai][2] @ truth
                    counts = trng.multinomial(cfg['benchmark_selected_events'], mean, size=nt)
                    nominal_toys = None
                    for mi, method in enumerate(METHODS):
                        response = mats[ai][mi]
                        if response is None: continue
                        toy_fits = np.full((nt, 6), np.nan)
                        if ai == 1 and mi > 0:
                            toy_fits = nominal_toys
                        else:
                            for ti, q in enumerate(counts):
                                fitted, info = fit_shape(response, q, cfg); total_fits['toy'] += 1
                                if fitted is not None: toy_fits[ti] = fitted
                            if ai == 1: nominal_toys = toy_fits
                        valid = np.isfinite(toy_fits).all(axis=-1)
                        diff = toy_fits[valid] - truth
                        sigma_abs = fitted_cache[ai, mi][1]
                        for b in range(6):
                            local = diff[:, b]
                            toys.append(dict(**key, alpha=alpha, method=method, law=law, bin=b, requested=nt,
                                             valid=int(valid.sum()), failures=int((~valid).sum()),
                                             boundary_frequency=float(np.mean(np.any(toy_fits[valid] < 1e-7, axis=-1))),
                                             relative_bias=float(local.mean() / truth[b]),
                                             relative_rms=float(np.sqrt(np.mean(local ** 2)) / truth[b]),
                                             pull_mean=float(np.mean(local / sigma_abs[b])),
                                             pull_std=float(np.std(local / sigma_abs[b], ddof=1)),
                                             coverage_68=float(np.mean(abs(local) <= sigma_abs[b]))))
            for bi, draw in enumerate(draws):
                src = np.einsum('g,agkj->akj', rw * draw, hist)
                ps = np.einsum('g,agkj->akj', pw * draw, hist)
                matrices = responses(src); fractions, observed = pseudo_shapes(ps)
                if fractions is None or matrices[1][0] is None:
                    failures.append(dict(**key, alpha=np.nan, method='all', kind='bootstrap', replicate=bi, status='empty_parent_truth')); continue
                log_src = np.einsum('g,gkj->kj', rw * draw, hlog)
                prof_sigma, prof = profile_information(matrices[1][0], derivative(src[1], log_src), fractions, cfg)
                if prof_sigma is not None:
                    boot_profile_sigma[bi, si, di] = prof_sigma; boot_profile_alpha[bi, si, di] = prof['alpha_sigma']
                else: failures.append(dict(**key, alpha=0., method='profile', kind='bootstrap', replicate=bi, status='fisher'))
                nominal = evaluate(matrices[1][0], fractions, observed[1], cfg); total_fits['bootstrap'] += 1
                for ai, alpha in enumerate(ALPHAS):
                    for mi, method in enumerate(METHODS):
                        cell = dict(**key, alpha=alpha, method=method, kind='bootstrap', replicate=bi)
                        response = matrices[ai][mi]
                        if response is None:
                            failures.append(dict(**cell, status='empty_internal_truth')); continue
                        if ai == 1: result = nominal
                        else:
                            result = evaluate(response, fractions, observed[ai], cfg); total_fits['bootstrap'] += 1
                        _, bias, sigma, _, info = result
                        if info['status'] != 'ok' or not info['identifiable']:
                            failures.append(dict(**cell, status=info['status'] if info['status'] != 'ok' else 'fisher'))
                        boot_bias[bi, ai, mi, si, di] = bias; boot_sigma[bi, ai, mi, si, di] = sigma
            print(f'{args.model} seed={si} {direction} complete', flush=True)
    np.savez_compressed(out / 'bootstrap.npz', bias=boot_bias, sigma=boot_sigma,
                        central_bias=central_bias, central_sigma=central_sigma,
                        profile_sigma=profile_sigma, profile_alpha=profile_alpha,
                        boot_profile_sigma=boot_profile_sigma, boot_profile_alpha=boot_profile_alpha, draws=draws)
    for filename, rows in [('metrics', metrics), ('closure_bins', perbin), ('response', matrix_rows),
                           ('internal_counts', subcounts), ('profile', profiles), ('selfchecks', selfchecks),
                           ('toys', toys), ('failures', failures)]: write_table(out / f'{filename}.tsv', rows)
    summary = dict(model=args.model, smoke=args.smoke, events=len(y), groups=len(groups), seeds=ns,
                   bootstrap=nb, toys_per_cell=nt, total_fits=total_fits, failure_cells=len(failures),
                   selfcheck_failures=sum(not r['passed'] for r in selfchecks), synthetic_checks=checks,
                   wall_s=time.perf_counter() - tick, cpu_s=time.process_time() - cpu,
                   max_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, host=platform.node(),
                   numpy=np.__version__, scipy=scipy.__version__, calibration_test_challenge_evaluated=False)
    (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n'); print(json.dumps(summary), flush=True)


if __name__ == '__main__': main()
