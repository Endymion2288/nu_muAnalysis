#!/usr/bin/env python3
"""Stage26 source-mixture diagnostics and finite-pool randomization worker."""
import argparse
import json
import platform
import resource
import time
from pathlib import Path

import numpy as np
import scipy

from closure import DIRECTIONS, write_table
from profile_response import Inference, METHODS, synthetic_checks
from source_response import (ALPHAS, CASES, NULLS, aggregate, config, counts_from_uniform,
                             direct_check, event_basis, load_events, make_response,
                             random_partition, target_mix)


def packed(best):
    return np.r_[best['f'], best['alpha']]


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--model', required=True); parser.add_argument('--seed-index', type=int, default=0)
    parser.add_argument('--output-dir', type=Path, required=True); parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args(); tick, cpu = time.perf_counter(), time.process_time()
    cfg = config(args.repo); seed = args.seed_index
    assert seed in cfg['models'][args.model]['seeds']; cfg['models'][args.model]['seeds'] = [seed]
    checks = synthetic_checks(cfg); out = args.output_dir; out.mkdir(parents=True, exist_ok=True)
    y, bins, gi, groups, fold, predictions, runs, ri = load_events(args.repo, cfg, args.model, args.smoke)
    nr = len(runs); scores = predictions[0]; nt = 2 if args.smoke else cfg['toys']; npart = 2 if args.smoke else cfg['permutation_coverage_replicates']
    basis, index, loge, reco = event_basis(y, bins, ri, scores, nr, cfg)
    pool = aggregate(basis, index, np.ones(len(y)), nr); target = target_mix(pool)
    original = fold[gi] == 'A'; a_coeff = aggregate(basis, index, original, nr)
    coefficients = np.stack([a_coeff, pool - a_coeff])
    truth = np.zeros((2, 6)); qs = np.full((2, 3, 2, 2, 10), np.nan)
    central = np.full((2, 3, 2, 2, 7), np.nan); center_loss = np.full((2, 3, 2, 2), np.nan)
    toy_counts = np.zeros((2, 3, 2, 2, nt, 10), dtype=np.int16)
    toy_fits = np.full((2, 3, 2, 2, nt, 2, 7), np.nan); toy_loss = np.full((2, 3, 2, 2, nt, 2), np.nan)
    toy_lr = np.full((2, 3, 2, 2, nt, 7), np.nan)
    null_point = np.full((2, npart, 2, 3, 2, 2, 7), np.nan)
    null_loss = np.full((2, npart, 2, 3, 2, 2), np.nan)
    null_truth = np.full((2, npart, 2, 6), np.nan)
    null_counts = np.zeros((2, npart, 2, nr, 6), dtype=np.int16)
    null_support = np.zeros((2, npart, 2, 2), dtype=bool)
    perm_counts = np.zeros((npart, 2, 2, 2, 10), dtype=np.int16)
    perm_fits = np.full((npart, 2, 2, 2, 2, 7), np.nan); perm_loss = np.full((npart, 2, 2, 2, 2), np.nan)
    perm_lr = np.full((npart, 2, 2, 2, 7), np.nan)
    stats = dict(solver_calls=0, solver_failures=0, iterations=0)
    failures, metrics, compression, composition = [], [], [], []
    kkt_max = 0.; start_spread_max = 0.; negative_clipped = 0

    def log_failure(kind, ni, trial, di, ai, ci, method, parameter, status):
        failures.append(dict(model=args.model, seed=seed, kind=kind, null_index=ni, trial=trial,
                             direction=DIRECTIONS[di], alpha_injected=ALPHAS[ai], case=CASES[ci],
                             method=method, parameter=parameter, status=status))

    def fit_pair(inference, q, alpha, identity):
        nonlocal kkt_max, start_spread_max
        bests = [inference.fit(q, alpha), inference.fit(q)]
        for mi, best in enumerate(bests):
            if best['status'] != 'ok': log_failure(*identity, METHODS[mi], -1, best['status'])
            else:
                kkt_max = max(kkt_max, best['kkt']); start_spread_max = max(start_spread_max, best['start_spread'])
        return bests

    def actual_lr(inference, observed, bests, fractions, identity):
        nonlocal negative_clipped
        result = np.full(7, np.nan)
        if bests[1]['status'] != 'ok': return result
        for parameter in range(7):
            partial = inference.conditional(observed, bests[1], parameter, fractions[parameter]) if parameter < 6 else bests[0]
            statistic, raw = inference.lr(partial, bests[1]); result[parameter] = statistic
            if np.isfinite(raw) and raw < 0 and np.isfinite(statistic): negative_clipped += 1
            if not np.isfinite(statistic): log_failure(*identity, 'profile_alpha', parameter, 'profile_or_negative_lr')
        return result

    # Original-source centers and conditional toy coverage, with paired uniforms.
    for di, direction in enumerate(DIRECTIONS):
        src, pseudo = coefficients[di], coefficients[1 - di]
        counts = pseudo[0].sum(axis=(0, 2)); ftrue = counts / counts.sum(); truth[di] = ftrue
        mask = original if di == 0 else ~original
        compression.append(dict(model=args.model, seed=seed, direction=direction,
                                **direct_check(src, target, y, bins, ri, reco, loge, mask, nr)))
        n = src[0].sum(axis=-1)
        for b in range(6):
            effective = 1 / np.sum(np.divide(target[:, b] ** 2, n[:, b], out=np.zeros(nr), where=n[:, b] > 0))
            for r in range(nr):
                composition.append(dict(model=args.model, seed=seed, direction=direction, truth_bin=b, run=int(runs[r]),
                                        source_events=int(n[r, b]), pseudo_events=int(pseudo[0, r, b].sum()),
                                        source_fraction=float(n[r, b] / n[:, b].sum()), target_fraction=float(target[r, b]),
                                        matched_effective_source_events=float(effective)))
        for ai, alpha in enumerate(ALPHAS):
            uniforms = np.random.default_rng(np.random.SeedSequence([cfg['seed'], 26, 2, seed, di, ai])).random((nt, 1000))
            for ci in range(2):
                response = make_response(src, target, ci); pseudo_response = make_response(pseudo, target, ci)
                inference = Inference(response, cfg, stats)
                qs[di, ai, ci, 0] = pseudo_response.at(alpha)[0] @ ftrue
                qs[di, ai, ci, 1] = response.at(alpha)[0] @ ftrue
                q = qs[di, ai, ci, 0]
                bests = fit_pair(inference, q, alpha, ('central', -1, -1, di, ai, ci))
                for mi, best in enumerate(bests):
                    central[di, ai, ci, mi] = packed(best); center_loss[di, ai, ci, mi] = best['nll']
                    pred = response.at(best['alpha'])[0] @ best['f']; positive = q > 0
                    dev = 2000 * np.sum(q[positive] * np.log(q[positive] / np.maximum(pred[positive], 1e-15)))
                    metrics.append(dict(model=args.model, seed=seed, direction=direction, alpha_injected=alpha,
                                        case=CASES[ci], method=METHODS[mi], alpha_hat=best['alpha'],
                                        closure_rms=float(np.sqrt(np.mean((best['f'] / ftrue - 1) ** 2))),
                                        deviance_N1000=float(dev), kkt=best['kkt'], start_spread=best['start_spread']))
                for li in range(2):
                    for ti, uniform in enumerate(uniforms):
                        observed = counts_from_uniform(qs[di, ai, ci, li], uniform)
                        toy_counts[di, ai, ci, li, ti] = observed
                        identity = ('observed_toy_' + cfg['toy_laws'][li], -1, ti, di, ai, ci)
                        bests = fit_pair(inference, observed, alpha, identity)
                        toy_fits[di, ai, ci, li, ti] = [packed(best) for best in bests]
                        toy_loss[di, ai, ci, li, ti] = [best['nll'] for best in bests]
                        toy_lr[di, ai, ci, li, ti] = actual_lr(inference, observed, bests, ftrue, identity)
            print(f'{args.model} seed={seed} original {direction} alpha={alpha} complete', flush=True)

    # No event cache: aggregate each randomly relabelled source once, then reuse.
    for ni in range(2):
        for trial in range(npart):
            assigned = random_partition(ni, trial, ri, bins, gi, groups, fold, cfg)
            ac = aggregate(basis, index, assigned, nr); split = [ac, pool - ac]
            for di in range(2):
                src, pseudo = split[di], split[1 - di]
                null_counts[ni, trial, di] = src[0].sum(axis=-1).astype(int)
                counts = pseudo[0].sum(axis=(0, 2)); ftrue = counts / counts.sum(); null_truth[ni, trial, di] = ftrue
                for ci in range(2):
                    try:
                        response = make_response(src, target, ci); pseudo_response = make_response(pseudo, target, ci)
                    except ValueError as err:
                        log_failure('unsupported', ni, trial, di, 1, ci, 'all', -1, str(err)); continue
                    null_support[ni, trial, di, ci] = True
                    inference = Inference(response, cfg, stats)
                    for ai, alpha in enumerate(ALPHAS):
                        qcross = pseudo_response.at(alpha)[0] @ ftrue
                        bests = fit_pair(inference, qcross, alpha, ('null_point', ni, trial, di, ai, ci))
                        null_point[ni, trial, di, ai, ci] = [packed(best) for best in bests]
                        null_loss[ni, trial, di, ai, ci] = [best['nll'] for best in bests]
                        if ni != 0 or alpha != 0.: continue
                        uniforms = np.random.default_rng(np.random.SeedSequence([cfg['seed'], 26, 3, seed, trial, di])).random(1000)
                        laws = [qcross, response.at(alpha)[0] @ ftrue]
                        for li, probability in enumerate(laws):
                            observed = counts_from_uniform(probability, uniforms); perm_counts[trial, di, ci, li] = observed
                            identity = ('permutation_toy_' + cfg['toy_laws'][li], ni, trial, di, ai, ci)
                            bests = fit_pair(inference, observed, alpha, identity)
                            perm_fits[trial, di, ci, li] = [packed(best) for best in bests]
                            perm_loss[trial, di, ci, li] = [best['nll'] for best in bests]
                            perm_lr[trial, di, ci, li] = actual_lr(inference, observed, bests, ftrue, identity)
            if (trial + 1) % 25 == 0 or trial + 1 == npart:
                print(f'{args.model} seed={seed} {NULLS[ni]} {trial + 1}/{npart} complete', flush=True)
    np.savez_compressed(out / 'source_inference.npz', coefficients=coefficients, pool=pool, target=target, truth=truth,
                        qs=qs, central=central, central_nll=center_loss, toy_counts=toy_counts, toy_fits=toy_fits,
                        toy_nll=toy_loss, toy_lr=toy_lr, null_point=null_point, null_nll=null_loss, null_truth=null_truth,
                        null_counts=null_counts, null_support=null_support, perm_counts=perm_counts, perm_fits=perm_fits,
                        perm_nll=perm_loss, perm_lr=perm_lr)
    for name, rows in [('metrics', metrics), ('compression', compression), ('composition', composition), ('failures', failures)]:
        write_table(out / (name + '.tsv'), rows)
    summary = dict(model=args.model, seed=seed, smoke=args.smoke, events=len(y), groups=len(groups), runs=runs.tolist(),
                   permutations_per_null=npart, observed_toys_per_cell=nt, observed_toy_count=2 * 3 * 2 * 2 * nt,
                   event_null_toy_count=npart * 2 * 2 * 2, independent_observed_uniform_blocks=2 * 3 * nt,
                   independent_event_null_partitions=npart, numerical_stats=stats,
                   failure_cells=sum(r['kind'] != 'unsupported' for r in failures),
                   unsupported_cases=sum(r['kind'] == 'unsupported' for r in failures), maximum_kkt=kkt_max,
                   maximum_start_spread=start_spread_max, negative_lr_clipped=negative_clipped, synthetic_checks=checks,
                   wall_s=time.perf_counter() - tick, cpu_s=time.process_time() - cpu,
                   max_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, host=platform.node(),
                   numpy=np.__version__, scipy=scipy.__version__, calibration_test_challenge_evaluated=False)
    (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n'); print(json.dumps(summary), flush=True)


if __name__ == '__main__': main()
