#!/usr/bin/env python3
"""Stage27 independent response/mean MC and observation-counting worker."""
import argparse
import json
import platform
import resource
import time
from pathlib import Path

import numpy as np
import scipy

from closure import load_data, write_table
from independent_response import (LAYERS, aggregate, basis, config, count_uniforms,
                                  local_covariance, population_checks, sample_weights)
from profile_response import Inference, Response, synthetic_checks
from source_response import counts_from_uniform


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--model', required=True); parser.add_argument('--seed-index', type=int, default=0)
    parser.add_argument('--alpha-index', type=int, default=1); parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--smoke', action='store_true'); args = parser.parse_args()
    tick, cpu = time.perf_counter(), time.process_time(); cfg = config(args.repo)
    seed = args.seed_index; ai = args.alpha_index; alpha = cfg['alphas'][ai]
    assert seed in cfg['models'][args.model]['seeds']; cfg['models'][args.model]['seeds'] = [seed]
    checks = synthetic_checks(cfg)
    y, bins, gi, groups, fold, predictions = load_data(args.repo, cfg, args.model, False)
    powers, index, logs, reco = basis(y, bins, predictions[0], cfg)
    pool = aggregate(powers, index, np.ones(len(y))); population = Response(pool)
    counts = np.bincount(bins, minlength=6); truth = counts / len(y); sizes = counts // 2
    checks.update(population_checks(population, bins, reco, logs))
    covariance, covariance_info = local_covariance(population, truth, alpha, bins, reco, logs, sizes, cfg)
    nt = 2 if args.smoke else cfg['replicates']; nw = 1 if args.smoke else cfg['width_trials']
    fits = np.full((nt, 4, 2, 2, 7), np.nan); losses = np.full((nt, 4, 2, 2), np.nan)
    lrs = np.full((nt, 4, 2, 7), np.nan); observed_counts = np.zeros((nt, 4, 10), dtype=np.int16)
    qs = np.full((nt, 4, 10), np.nan); statuses = np.zeros((nt, 4, 2, 2), dtype=np.int8)
    all_failures, intervals = [], []; stats = dict(solver_calls=0, solver_failures=0, iterations=0)
    kkt_max = 0.; spread_max = 0.; negative_clips = 0
    out = args.output_dir; out.mkdir(parents=True, exist_ok=True)

    def failure(ti, li, count, method, parameter, status):
        all_failures.append(dict(model=args.model, seed=seed, alpha_injected=alpha, trial=ti,
                                 layer=LAYERS[li], counting=count, method=method, parameter=parameter, status=status))

    for ti in range(nt):
        weights = [sample_weights(bins, sizes, side, ti, cfg) for side in range(2)]
        for w in weights: np.testing.assert_array_equal(np.bincount(bins, weights=w, minlength=6), sizes)
        responses = [population] + [Response(aggregate(powers, index, w)) for w in weights]
        uniform = count_uniforms(seed, ai, ti, cfg)
        for li in range(4):
            response = responses[1] if li in [1, 3] else population
            mean_response = responses[2] if li in [2, 3] else population
            q = mean_response.at(alpha)[0] @ truth; qs[ti, li] = q
            observed = counts_from_uniform(q, uniform); observed_counts[ti, li] = observed
            inference = Inference(response, cfg, stats)
            for ci, data in enumerate([q, observed]):
                bests = [inference.fit(data, alpha), inference.fit(data)]
                for mi, best in enumerate(bests):
                    fits[ti, li, ci, mi] = np.r_[best['f'], best['alpha']]
                    losses[ti, li, ci, mi] = best['nll']
                    statuses[ti, li, ci, mi] = int(best['status'] == 'ok')
                    if best['status'] != 'ok': failure(ti, li, ci, mi, -1, best['status'])
                    else:
                        kkt_max = max(kkt_max, best['kkt']); spread_max = max(spread_max, best['start_spread'])
                if bests[1]['status'] != 'ok': continue
                for parameter in range(7):
                    partial = inference.conditional(data, bests[1], parameter, truth[parameter]) if parameter < 6 else bests[0]
                    statistic, raw = inference.lr(partial, bests[1]); lrs[ti, li, ci, parameter] = statistic
                    if np.isfinite(raw) and raw < 0 and np.isfinite(statistic): negative_clips += 1
                    if not np.isfinite(statistic): failure(ti, li, ci, 1, parameter, 'profile_or_negative_lr')
                if alpha == cfg['width_alpha'] and ti < nw and ci == 1:
                    for parameter in cfg['width_parameters']:
                        interval = inference.interval(data, bests[1], parameter)
                        intervals.append(dict(model=args.model, seed=seed, alpha_injected=alpha, trial=ti, layer=LAYERS[li],
                                              parameter=parameter, mle=float(fits[ti, li, ci, 1, parameter]), **interval))
                        if interval['interval_status'] != 'ok': failure(ti, li, ci, 1, parameter, interval['interval_status'])
        if (ti + 1) % 25 == 0 or ti + 1 == nt:
            print(f'{args.model} seed={seed} alpha={alpha} trial={ti+1}/{nt}', flush=True)
    np.savez_compressed(out / 'independent_inference.npz', pool=pool, truth=truth, sizes=sizes, local_covariance=covariance,
                        fits=fits, losses=losses, lrs=lrs, counts=observed_counts, qs=qs, statuses=statuses)
    write_table(out / 'intervals.tsv', intervals); write_table(out / 'failures.tsv', all_failures)
    summary = dict(model=args.model, seed=seed, alpha_index=ai, alpha_injected=alpha, smoke=args.smoke,
                   events=len(y), groups=len(groups), truth_counts=counts.tolist(), mc_counts=sizes.tolist(),
                   replicates=nt, counting_instances=nt*4, mean_instances=nt*4, intervals=len(intervals),
                   failure_cells=len(all_failures), numerical_stats=stats, maximum_kkt=kkt_max,
                   maximum_start_spread=spread_max, negative_lr_clipped=negative_clips, checks=checks,
                   local_covariance_info=covariance_info, wall_s=time.perf_counter()-tick, cpu_s=time.process_time()-cpu,
                   max_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, host=platform.node(),
                   numpy=np.__version__, scipy=scipy.__version__, calibration_test_challenge_evaluated=False)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)


if __name__ == '__main__': main()
