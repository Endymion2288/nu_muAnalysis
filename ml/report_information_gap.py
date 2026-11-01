#!/usr/bin/env python3
"""Same-event source-paired oracle diagnostics, including nonlinear response metrics."""
import argparse
import csv
import json
import resource
import time
from pathlib import Path

import numpy as np

from information_gap import configuration, training_summary
from train_bdt import metric_values, write_table


def quantile_bootstrap(residual, gid, draws):
    order = np.argsort(residual); values = residual[order]
    output = []
    for chunk in np.array_split(draws, max(1, int(np.ceil(len(draws) / 24)))):
        cum = np.cumsum(chunk[:, gid[order]], axis=1)
        total = cum[:, -1]
        qs = []
        for q in [.16, .5, .84]:
            location = q * (total - 1)
            lo = np.floor(location).astype(int); hi = np.ceil(location).astype(int)
            a = np.array([np.searchsorted(row, v + 1) for row, v in zip(cum, lo)])
            b = np.array([np.searchsorted(row, v + 1) for row, v in zip(cum, hi)])
            qs.append(values[a] * (hi - location) + values[b] * (location - lo) +
                      values[a] * (lo == hi))
        output.append(np.stack([qs[1], (qs[2] - qs[0]) / 2]))
    return np.concatenate(output, axis=1)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--controls', action='store_true')
    args = p.parse_args(); root = args.repo; cfg = configuration(root)
    tick = time.perf_counter(); cpu = time.process_time()
    out = root / 'workbook/stage30_energy_ml'; art = root / 'ml/artifacts/stage30'
    with np.load(root / 'ntuples/energy_ml_stage15/validation_truth.npz') as z:
        truth = {k: z[k] for k in ['run', 'eventID', 'truth_E_GeV', 'y_lepton',
                 'lead_primary_parent_confirmed', 'vertex_x_mm', 'vertex_y_mm', 'vertex_z_mm',
                 'primary_p_GeV', 'reco_p_GeV']}
    y = truth['truth_E_GeV']; n = len(y); pred = {}; costs = []; groups = None
    models = list(cfg['oracle']) + (list(cfg['controls']) if args.controls else [])
    for mode in ['main'] + (['controls'] if args.controls else []):
        for i in range(3):
            folder = out / mode / f'seed_{i}'
            run = training_summary(folder)
            assert not run['smoke'] and not run['calibration_test_challenge_evaluated']
            assert run['cfg'] == cfg
            with np.load(art / mode / f'seed_{i}/predictions.npz') as z:
                for k in ['run', 'eventID', 'truth_E_GeV']:
                    np.testing.assert_array_equal(truth[k], z[k])
                if groups is None: groups = z['group']
                else: np.testing.assert_array_equal(groups, z['group'])
                for name in cfg['oracle' if mode == 'main' else 'controls']:
                    pred.setdefault(name, []).append(z[name])
            costs += list(csv.DictReader((folder / 'costs.tsv').open(), delimiter='\t'))
    pred = {k: np.stack(v) for k, v in pred.items()}
    _, gid = np.unique(groups, return_inverse=True); ng = int(gid.max()+1)
    draws = np.random.default_rng(cfg['split_seed']).multinomial(ng, np.full(ng, 1/ng),
                                                               size=cfg['bootstrap_replicates'])
    edges = cfg['energy_edges_GeV']
    masks = [('all', 'all', np.ones(n, bool))]
    masks += [('energy_GeV', f'{a}_{b}', (y >= a) & (y < b)) for a, b in zip(edges[:-1], edges[1:])]
    yy = truth['y_lepton']; ze = cfg['vertex_z_edges_mm']; z = truth['vertex_z_mm']
    masks += [('y_lepton', f'{a:g}_{b:g}', (yy >= a) & (yy < b))
              for a, b in zip(cfg['y_edges'][:-1], cfg['y_edges'][1:])]
    confirmed = truth['lead_primary_parent_confirmed']
    masks += [('primary', 'confirmed', confirmed), ('primary', 'unconfirmed', ~confirmed)]
    masks += [('vertex_z_mm', f'{a}_{b}', (z >= a) & (z < b)) for a, b in zip(ze[:-1], ze[1:])]
    radius = np.hypot(truth['vertex_x_mm'], truth['vertex_y_mm'])
    masks += [('vertex_r_mm', 'lt50', radius < 50), ('vertex_r_mm', 'ge50', radius >= 50),
              ('y_confirmed', 'ge0.8', confirmed & (yy >= .8))]
    loss = {k: np.mean(np.log(a/y)**2, axis=0) for k, a in pred.items()}
    residual = {k: a/y-1 for k, a in pred.items()}
    keys = ['log_RMSE', 'mean_bias', 'median_bias', 'R68', 'tail_0p5', 'tail_1']
    pairs = [('A0', k) for k in models if k != 'A0'] + [('Ap', 'Apv'), ('Av', 'Apv'), ('Av', 'Ap')]
    if args.controls: pairs.append(('Az', 'Av'))
    per_seed = []; metrics = []; paired = []; interactions = []; strata_scores = {}
    for label, value, mask in masks:
        counts = np.bincount(gid[mask], minlength=ng); den = draws @ counts; valid = den > 0
        samples = {}; center = {}
        for name in models:
            center[name] = {}; samples[name] = {}
            rr = residual[name][:, mask]
            for si, a in enumerate(pred[name]):
                per_seed.append(dict(model=name, seed=cfg['seeds'][si], stratum=label, value=value,
                                     **metric_values(y, a, mask)))
            vectors = dict(log_RMSE=loss[name][mask], mean_bias=rr.mean(0),
                           tail_0p5=(abs(rr) > .5).mean(0), tail_1=(abs(rr) > 1).mean(0))
            for key, v in vectors.items():
                center[name][key] = np.sqrt(v.mean()) if key == 'log_RMSE' else v.mean()
                sums = np.bincount(gid[mask], weights=v, minlength=ng)
                b = (draws[valid] @ sums) / den[valid]
                samples[name][key] = np.sqrt(b) if key == 'log_RMSE' else b
            qs = np.mean([quantile_bootstrap(r, gid[mask], draws[valid]) for r in rr], axis=0)
            for qi, key in enumerate(['median_bias', 'R68']):
                quantiles = np.quantile(rr, [.16, .5, .84], axis=1)
                center[name][key] = float(np.mean(quantiles[1] if qi == 0 else (quantiles[2]-quantiles[0])/2))
                samples[name][key] = qs[qi]
            for key in keys:
                lo, hi = np.quantile(samples[name][key], [.025, .975])
                metrics.append(dict(model=name, stratum=label, value=value, N=int(mask.sum()),
                                    groups=int((counts > 0).sum()), metric=key,
                                    point=center[name][key], CI025=lo, CI975=hi, bootstrap_valid=int(valid.sum())))
        strata_scores[(label, value)] = (center, samples)
        for left, right in pairs:
            for key in keys:
                lo, hi = np.quantile(samples[right][key]-samples[left][key], [.025, .975])
                paired.append(dict(reference=left, model=right, stratum=label, value=value, metric=key,
                                   N=int(mask.sum()), delta=center[right][key]-center[left][key],
                                   CI025=lo, CI975=hi, bootstrap_valid=int(valid.sum())))
        si = samples['Ap']['log_RMSE']+samples['Av']['log_RMSE']-samples['Apv']['log_RMSE']-samples['A0']['log_RMSE']
        lo, hi = np.quantile(si, [.025, .975])
        point = center['Ap']['log_RMSE']+center['Av']['log_RMSE']-center['Apv']['log_RMSE']-center['A0']['log_RMSE']
        interactions.append(dict(stratum=label, value=value, metric='log_RMSE', I=point, CI025=lo, CI975=hi))
    # Macro risk uses all six bins, including rare highest bin; same source draws.
    centers = {}; boots = {}
    for name in models:
        c = []; b = []
        for lo, hi in zip(edges[:-1], edges[1:]):
            center, sample = strata_scores[('energy_GeV', f'{lo}_{hi}')]
            assert len(sample[name]['log_RMSE']) == len(draws)
            c.append(center[name]['log_RMSE']**2); b.append(sample[name]['log_RMSE']**2)
        centers[name] = np.sqrt(np.mean(c)); boots[name] = np.sqrt(np.mean(b, axis=0))
    macro = []; gains = []; macro_pairs = []
    for name in models:
        lo, hi = np.quantile(boots[name], [.025, .975])
        macro.append(dict(model=name, macro_log_RMSE=centers[name], CI025=lo, CI975=hi))
    for name in models:
        if name == 'A0': continue
        b = boots['A0'] - boots[name]; relative = b / boots['A0']
        lo, hi = np.quantile(b, [.025, .975]); rl, rh = np.quantile(relative, [.025, .975])
        gains.append(dict(model=name, gain=centers['A0']-centers[name], CI025=lo, CI975=hi,
                          relative_gain=1-centers[name]/centers['A0'], relative_CI025=rl, relative_CI975=rh))
    for left, right in pairs:
        lo, hi = np.quantile(boots[right]-boots[left], [.025, .975])
        macro_pairs.append(dict(reference=left, model=right, delta=centers[right]-centers[left], CI025=lo, CI975=hi))
    interaction = boots['Ap']+boots['Av']-boots['Apv']-boots['A0']
    lo, hi = np.quantile(interaction, [.025, .975])
    interactions.append(dict(stratum='macro', value='six_energy_bins', metric='log_RMSE',
                             I=centers['Ap']+centers['Av']-centers['Apv']-centers['A0'], CI025=lo, CI975=hi))
    av = next(r for r in gains if r['model'] == 'Av')
    gate = dict(controls_required=bool(av['relative_gain'] >= cfg['minimum_relative_gain'] and av['CI025'] > 0), **av)
    response_diagnostic = []
    for label, mask in [('low_y', yy < .2), ('high_y', yy >= .8),
                         ('high_y_confirmed', (yy >= .8) & confirmed),
                         ('high_y_unconfirmed', (yy >= .8) & ~confirmed)]:
        ratio = truth['reco_p_GeV'][mask]/truth['primary_p_GeV'][mask]
        delta = np.log(pred['Ap'][:, mask]/pred['A0'][:, mask])
        response_diagnostic.append(dict(stratum=label, N=int(mask.sum()), confirmed=int(confirmed[mask].sum()),
            median_truth_E_GeV=float(np.median(y[mask])), median_primary_p_GeV=float(np.median(truth['primary_p_GeV'][mask])),
            median_reco_p_over_vertex_p=float(np.median(ratio)), response_outside_factor2=float(((ratio > 2) | (ratio < .5)).mean()),
            median_log_Ap_over_A0=float(np.mean(np.median(delta, axis=1))),
            primary_energy_fraction_median=float(np.median(1-yy[mask]))))
    for filename, rows in [('oracle_seed_metrics.tsv', per_seed), ('oracle_metrics.tsv', metrics),
                           ('oracle_paired.tsv', paired), ('oracle_interaction.tsv', interactions),
                           ('oracle_macro.tsv', macro), ('oracle_gains.tsv', gains),
                           ('oracle_macro_paired.tsv', macro_pairs), ('costs.tsv', costs)]:
        write_table(out / filename, rows)
    write_table(out/'y_response_diagnostic.tsv', response_diagnostic)
    (out / 'control_gate.json').write_text(json.dumps(gate, indent=2)+'\n')
    summary = dict(controls_included=args.controls, validation_events=n, groups=ng,
                   wall_s=time.perf_counter()-tick, cpu_s=time.process_time()-cpu,
                   peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    (out / 'oracle_report_resources.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(dict(macro=macro, gains=gains, interaction=interactions[-1], gate=gate, resources=summary), indent=2))


if __name__ == '__main__':
    main()
