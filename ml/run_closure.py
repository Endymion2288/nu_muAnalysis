#!/usr/bin/env python3
"""Stage23 worker: frozen forward closure, group bootstrap and known-response toys."""
import argparse
import json
import platform
import resource
import time
from pathlib import Path

import numpy as np
import scipy
import yaml

from closure import (DIRECTIONS, SCHEMES, evaluate, fisher, fit_shape, histograms,
                     load_data, matrices, synthetic_checks, write_table)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--model', required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args()
    wall, cpu = time.perf_counter(), time.process_time()
    cfg = yaml.safe_load((args.repo / 'ml/configs/closure.yaml').read_text())
    checks = synthetic_checks(cfg)
    out = args.output_dir; out.mkdir(parents=True, exist_ok=True)
    y, bins, gi, groups, fold, predictions = load_data(args.repo, cfg, args.model, args.smoke)
    nboot = 8 if args.smoke else cfg['bootstrap_replicates']
    ntoys = 8 if args.smoke else cfg['toys']
    nseeds = len(predictions)
    # The bootstrap RNG is model independent, and not shared with toy draws.
    rng = np.random.default_rng(cfg['seed'])
    draws = np.zeros((nboot, len(groups)), dtype=int)
    for name in ['A', 'B']:
        indices = np.flatnonzero(fold == name)
        draws[:, indices] = rng.multinomial(len(indices), np.full(len(indices), 1 / len(indices)), size=nboot)
    components = np.array([g.split(':')[0] for g in groups])
    target_mix = {c: float(np.mean(components[gi] == c)) for c in np.unique(components)}
    central, perbin, response_rows, correlations, edges_rows, selfchecks, toys, failures, support_rows = [], [], [], [], [], [], [], [], []
    boot_bias = np.full((nboot, 2, 5, nseeds, 2, 6), np.nan)
    boot_sigma = np.full_like(boot_bias, np.nan)
    central_bias = np.full((2, 6, nseeds, 2, 6), np.nan)
    central_sigma = np.full_like(central_bias, np.nan)
    toy_rng = np.random.default_rng(cfg['seed'] + 100)
    for si, scores in enumerate(predictions):
        for scheme_index, scheme in enumerate(SCHEMES):
            for di, direction in enumerate(DIRECTIONS):
                source_fold = direction[0]
                rw = (fold == source_fold).astype(float); pw = 1 - rw
                source_events = rw[gi] > 0
                edges = np.array(cfg['energy_reco_internal_GeV']) if scheme == 'energy' else np.quantile(scores[source_events], np.arange(1, 10) / 10)
                assert len(np.unique(edges)) == 9
                reco = np.searchsorted(edges, scores, side='right')
                hist = histograms(y, bins, gi, reco, groups, cfg)
                key = dict(model=args.model, seed=si, scheme=scheme, direction=direction)
                for ei, edge in enumerate(edges):
                    edges_rows.append(dict(**key, edge=ei, value_GeV=float(edge)))
                support_rows.append(dict(**key, response_events=int(source_events.sum()), pseudo_events=int((~source_events).sum()),
                                         response_below100=int(np.sum(source_events & (scores < 100))),
                                         pseudo_below100=int(np.sum(~source_events & (scores < 100))),
                                         response_above6400=int(np.sum(source_events & (scores >= 6400))),
                                         pseudo_above6400=int(np.sum(~source_events & (scores >= 6400)))))
                for ci, case in enumerate(cfg['cases']):
                    rweights, pweights = rw.copy(), pw.copy()
                    if case == 'component_matched':
                        for mask in [rweights, pweights]:
                            total = mask[gi].sum()
                            for c in target_mix:
                                local = components == c
                                fraction = mask[gi[components[gi] == c]].sum() / total
                                mask[local] *= target_mix[c] / fraction
                    response, truth, observed, status = matrices(hist, case, rweights, pweights, cfg)
                    assert status == 'ok'
                    fhat, bias, sigma, cov, info = evaluate(response, truth, observed, cfg)
                    central.append(dict(**key, case=case, **info))
                    central_bias[scheme_index, ci, si, di] = bias ** 2
                    central_sigma[scheme_index, ci, si, di] = sigma ** 2
                    for b in range(6):
                        perbin.append(dict(**key, case=case, bin=b, true_fraction=float(truth[b]),
                                           fitted_fraction=float(fhat[b]) if fhat is not None else np.nan,
                                           fractional_bias=float(bias[b]), relative_sigma=float(sigma[b])))
                    if case in ['nominal', 'component_matched']:
                        for j in range(10):
                            for b in range(6):
                                response_rows.append(dict(**key, case=case, reco_bin=j, truth_bin=b, probability=float(response[j, b])))
                        if cov is not None:
                            corr = cov / np.sqrt(np.outer(np.diag(cov), np.diag(cov)))
                            for b in range(6):
                                for b2 in range(6):
                                    correlations.append(dict(**key, case=case, bin=b, other_bin=b2, correlation=float(corr[b, b2])))
                    if case != 'nominal':
                        continue
                    for perturb in ['nominal', 'high_double']:
                        f = truth.copy()
                        if perturb == 'high_double': f[-2:] *= 2; f /= f.sum()
                        recovered, check = fit_shape(response, response @ f, cfg)
                        fraction_error = float(np.max(abs(recovered - f))) if recovered is not None else np.inf
                        reco_error = float(np.max(abs(response @ recovered - response @ f))) if recovered is not None else np.inf
                        selfchecks.append(dict(**key, perturb=perturb, fraction_error=fraction_error, reco_error=reco_error,
                                               passed=bool(check['status'] == 'ok' and (cov is None or fraction_error < 2e-5) and reco_error < 1e-7)))
                    sigma_abs = sigma * truth
                    toy_fits = np.full((ntoys, 6), np.nan); boundary = 0; toy_failures = 0
                    for ti, counts in enumerate(toy_rng.multinomial(cfg['benchmark_selected_events'], response @ truth, size=ntoys)):
                        fitted, info_toy = fit_shape(response, counts, cfg)
                        if fitted is None:
                            toy_failures += 1
                        else:
                            toy_fits[ti] = fitted
                            boundary += int(np.any(fitted < 1e-7))
                    residual = toy_fits - truth
                    valid = np.isfinite(residual).all(axis=1)
                    for b in range(6):
                        local = residual[valid, b]
                        toys.append(dict(**key, bin=b, toys=ntoys, valid=int(valid.sum()), failures=toy_failures,
                                         boundary_frequency=boundary / max(1, valid.sum()),
                                         relative_bias=float(local.mean() / truth[b]), relative_rms=float(np.sqrt(np.mean(local ** 2)) / truth[b]),
                                         pull_mean=float(np.mean(local / sigma_abs[b])), pull_std=float(np.std(local / sigma_abs[b], ddof=1)),
                                         coverage_68=float(np.mean(abs(local) <= sigma_abs[b]))))
                for bi, draw in enumerate(draws):
                    for ci, case in enumerate(cfg['bootstrap_cases']):
                        response, truth, observed, status = matrices(hist, case, rw * draw, pw * draw, cfg)
                        if status != 'ok':
                            failures.append(dict(**key, replicate=bi, case=case, status=status))
                            continue
                        _, bias, sigma, _, info = evaluate(response, truth, observed, cfg)
                        if info['status'] != 'ok' or not info['identifiable']:
                            failures.append(dict(**key, replicate=bi, case=case,
                                                 status=info['status'] if info['status'] != 'ok' else 'fisher'))
                        boot_bias[bi, scheme_index, ci, si, di] = bias ** 2
                        boot_sigma[bi, scheme_index, ci, si, di] = sigma ** 2
                print(f'{args.model} seed={si} scheme={scheme} direction={direction} complete', flush=True)
    # Equal weight for seeds and reciprocal directions; never cancel signed bias.
    np.savez_compressed(out / 'bootstrap.npz', bias_sq=boot_bias.mean(axis=(3, 4)), sigma_sq=boot_sigma.mean(axis=(3, 4)),
                        central_bias_sq=central_bias.mean(axis=(2, 3)), central_sigma_sq=central_sigma.mean(axis=(2, 3)), draws=draws)
    for filename, rows in [('metrics', central), ('closure_bins', perbin), ('response', response_rows),
                           ('correlations', correlations), ('reco_edges', edges_rows), ('selfchecks', selfchecks),
                           ('toys', toys), ('bootstrap_failures', failures), ('flows', support_rows)]:
        write_table(out / f'{filename}.tsv', rows)
    summary = dict(model=args.model, smoke=args.smoke, events=len(y), seeds=nseeds, groups=len(groups),
                   folds={name: dict(groups=int(np.sum(fold == name)), events=int(np.sum(fold[gi] == name))) for name in ['A', 'B']},
                   target_components=target_mix, bootstrap=nboot, toys=ntoys, failure_cells=len(failures),
                   selfcheck_failures=sum(not r['passed'] for r in selfchecks), synthetic_checks=checks,
                   wall_s=time.perf_counter() - wall, cpu_s=time.process_time() - cpu,
                   max_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                   host=platform.node(), numpy=np.__version__, scipy=scipy.__version__,
                   calibration_test_challenge_evaluated=False)
    (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
