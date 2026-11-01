#!/usr/bin/env python3
"""Budget-limited nominal representation study; inputs are frozen stage30 predictions."""
import argparse
import csv
import json
import resource
import time
from pathlib import Path

import numpy as np

from information_gap import class_index, configuration
from probability_information import (checks, curvature_information, fit_mixture,
                                      probability_metrics, score_information)
from train_bdt import write_table


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--seed-index', type=int, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--smoke', action='store_true')
    p.add_argument('--within', action='store_true')
    args = p.parse_args(); cfg = configuration(args.repo); out = args.output_dir
    out.mkdir(parents=True, exist_ok=True); tick = time.perf_counter(); cpu = time.process_time()
    selfchecks = checks()
    source = args.repo / f'ml/artifacts/stage30/main/seed_{args.seed_index}/predictions.npz'
    with np.load(source) as z: data = {k: z[k] for k in z.files}
    n = len(data['truth_E_GeV']); labels = class_index(data['truth_E_GeV'], cfg)
    prior = data['prior']; names = ['q_full', 'q_mean', 'q_scalar', 'q_ten']
    _, gid = np.unique(data['group'], return_inverse=True); ng = int(gid.max()+1)
    nominal = np.ones(n); f0 = np.bincount(labels, minlength=6)/n
    rng = np.random.default_rng(cfg['split_seed'])
    draws = rng.multinomial(ng, np.full(ng, 1/ng), size=3 if args.smoke else cfg['representation_bootstrap_replicates'])
    toy_idx = rng.integers(n, size=(3 if args.smoke else cfg['toys'], cfg['benchmark_selected_events']))
    fold_rows = list(csv.DictReader((args.repo/'workbook/stage23_energy_ml/folds.tsv').open(), delimiter='\t'))
    fold_lookup = {r['group']: r['fold'] for r in fold_rows}
    folds = np.array([fold_lookup[g] for g in data['group']])
    cases = dict(nominal=nominal, source_A=(folds == 'A').astype(float), source_B=(folds == 'B').astype(float))
    if args.within:
        center = np.sqrt(np.array(cfg['energy_edges_GeV'][:-1])*cfg['energy_edges_GeV'][1:])
        for name, exponent in [('within_minus', -1), ('within_plus', 1)]:
            w = (data['truth_E_GeV']/center[labels])**exponent
            w *= np.bincount(labels, minlength=6)[labels] / np.bincount(labels, weights=w, minlength=6)[labels]
            cases[name] = w
    rows = []; bins = []; reliability = []; probabilities = []; boot = {}; toys = {}; failures = []
    # Raw classifier is a calibration control; it is not an extra trained candidate.
    for name in ['classifier'] + names:
        q = data[name]
        assert q.shape == (n, 6) and np.isfinite(q).all() and (q >= 0).all()
        np.testing.assert_allclose(q.sum(1), 1, atol=2e-6)
        pm = probability_metrics(q, labels)
        ece = 0.
        for b in range(6):
            for j in range(10):
                mask = (q[:, b] >= j/10) & (q[:, b] < (j+1)/10 if j < 9 else q[:, b] <= 1)
                if not mask.any(): continue
                predicted = q[mask, b].mean(); observed = (labels[mask] == b).mean()
                ece += mask.sum()/n * abs(predicted-observed)/6
                reliability.append(dict(model=name, class_bin=b, probability_bin=j, N=int(mask.sum()),
                                        mean_probability=predicted, observed_fraction=observed))
        probabilities.append(dict(model=name, **pm, classwise_ECE=ece))
    for name in names:
        ratio = data[name].astype(float)/prior
        for case, weights in cases.items():
            f = np.bincount(labels, weights=weights, minlength=6)/weights.sum()
            fitted, status = fit_mixture(ratio, weights, f)
            information, covariance = score_information(ratio, labels, weights)
            curvature, _ = curvature_information(ratio, fitted, weights)
            assert status['success'] and information['valid'] and curvature['valid']
            relative_bias = fitted/f-1
            rows.append(dict(model=name, case=case, N=int((weights > 0).sum()),
                             score_relative_sigma_RMS=information['relative_sigma_RMS'],
                             curvature_relative_sigma_RMS=curvature['relative_sigma_RMS'],
                             relative_bias_RMS=float(np.sqrt(np.mean(relative_bias**2))),
                             min_score_eigenvalue=information['min_eigenvalue'],
                             score_condition=information['condition'], kkt=status['kkt'], boundary=status['boundary']))
            for b in range(6):
                bins.append(dict(model=name, case=case, bin=b, truth_fraction=f[b], fitted_fraction=fitted[b],
                                 relative_bias=relative_bias[b], score_relative_sigma=information['relative_sigma'][b],
                                 weakest_direction=information['weakest_direction'][b]))
        sigmas = []; biases = []
        for bi, multiplicities in enumerate(draws):
            w = multiplicities[gid].astype(float)
            info, _ = score_information(ratio, labels, w)
            f = np.bincount(labels, weights=w, minlength=6)/w.sum()
            fitted, status = fit_mixture(ratio, w, f)
            valid = info['valid'] and status['success']
            sigmas.append(info['relative_sigma_RMS'] if valid else np.nan)
            biases.append(float(np.sqrt(np.mean((fitted/f-1)**2))) if valid else np.nan)
            if not valid: failures.append(dict(model=name, bootstrap=bi, valid=valid))
        boot[f'{name}_sigma'] = np.array(sigmas); boot[f'{name}_bias'] = np.array(biases)
        fits = []; boundary = []; success = []; kkts = []
        for idx in toy_idx:
            fitted, status = fit_mixture(ratio[idx], np.ones(len(idx)), f0)
            fits.append(fitted); boundary.append(status['boundary']); success.append(status['success']); kkts.append(status['kkt'])
        toys[f'{name}_fits'] = np.stack(fits); toys[f'{name}_boundary'] = np.array(boundary)
        toys[f'{name}_success'] = np.array(success); toys[f'{name}_kkt'] = np.array(kkts)
        print(json.dumps(rows[-len(cases)]), flush=True)
    write_table(out/'spectrum_metrics.tsv', rows); write_table(out/'spectrum_bins.tsv', bins)
    write_table(out/'probability_metrics.tsv', probabilities); write_table(out/'reliability.tsv', reliability)
    if failures: write_table(out/'failures.tsv', failures)
    np.savez_compressed(out/'sampling.npz', f0=f0, **boot, **toys)
    summary = dict(seed=cfg['seeds'][args.seed_index], seed_index=args.seed_index, smoke=args.smoke,
                   within=args.within, validation_events=n, groups=ng, checks=selfchecks,
                   bootstrap_replicates=len(draws), toys=len(toy_idx), failures=len(failures),
                   wall_s=time.perf_counter()-tick, cpu_s=time.process_time()-cpu,
                   peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                   calibration_test_challenge_evaluated=False)
    (out/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
