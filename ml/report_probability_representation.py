#!/usr/bin/env python3
"""Combine seeds without ensembling, preserving paired source draws and toys."""
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
matplotlib.rcParams['svg.hashsalt'] = 'nu_mu_stage30'
import matplotlib.pyplot as plt
import numpy as np

from information_gap import configuration
from probability_information import categorical_information, probability_metrics
from train_bdt import write_table


def read(path):
    return list(csv.DictReader(path.open(), delimiter='\t'))


def rms(values):
    return float(np.sqrt(np.mean(np.asarray(values)**2)))


def main():
    root = Path(__file__).resolve().parents[1]; out = root/'workbook/stage30_energy_ml'
    cfg = configuration(root); names = ['q_full', 'q_mean', 'q_scalar', 'q_ten']
    per_seed = []; bin_rows = []; probability = []; reliability = []; arrays = []; runs = []
    for si in range(3):
        folder = out/f'representation/seed_{si}'
        run = json.loads((folder/'summary.json').read_text())
        assert not run['smoke'] and not run['within'] and run['failures'] == 0
        assert run['bootstrap_replicates'] == cfg['representation_bootstrap_replicates']
        assert run['toys'] == cfg['toys'] and not run['calibration_test_challenge_evaluated']
        runs.append(run)
        for dest, filename in [(per_seed, 'spectrum_metrics.tsv'), (bin_rows, 'spectrum_bins.tsv'),
                               (probability, 'probability_metrics.tsv'), (reliability, 'reliability.tsv')]:
            dest.extend(dict(seed=cfg['seeds'][si], **r) for r in read(folder/filename))
        with np.load(root/f'ml/artifacts/stage30/representation/seed_{si}/sampling.npz') as z:
            arrays.append({k: z[k] for k in z.files})
    f0 = arrays[0]['f0']
    for a in arrays: np.testing.assert_array_equal(a['f0'], f0)
    # Proper scores explicitly retain zero-probability failures; clipping is a labelled diagnostic.
    event_losses = {}; truth_probability = []; group = None; category_histograms = []
    for si, seed in enumerate(cfg['seeds']):
        with np.load(root/f'ml/artifacts/stage30/main/seed_{si}/predictions.npz') as z:
            labels = np.searchsorted(cfg['energy_edges_GeV'], z['truth_E_GeV'], side='right')-1
            if group is None: group = z['group']
            else: np.testing.assert_array_equal(group, z['group'])
            _, local_gid = np.unique(group, return_inverse=True)
            category = np.searchsorted([200, 200*np.sqrt(2), 400, 400*np.sqrt(2), 800,
                                       800*np.sqrt(2), 1600, 1600*np.sqrt(2), 3200], z['A0'])
            histogram = np.zeros((int(local_gid.max()+1), 10, 6))
            np.add.at(histogram, (local_gid, category, labels), 1)
            category_histograms.append(histogram)
            for row in probability:
                if row['seed'] == seed:
                    row.update(probability_metrics(z[row['model']], labels))
            for name in ['classifier']+names:
                q = z[name]
                if name != 'q_ten':
                    event_losses.setdefault(name, []).append(-np.log(q[np.arange(len(q)), labels]))
                for b in range(6):
                    mask = labels == b
                    truth_probability.append(dict(seed=seed, model=name, truth_bin=b, N=int(mask.sum()),
                                                  mean_true_probability=float(q[mask, b].mean()),
                                                  **probability_metrics(q[mask], labels[mask])))
        local = [{k: v for k, v in r.items() if k != 'seed'} for r in probability if r['seed'] == seed]
        write_table(out/f'representation/seed_{si}/probability_metrics.tsv', local)
    _, gid = np.unique(group, return_inverse=True); ng = int(gid.max()+1)
    draws = np.random.default_rng(cfg['split_seed']).multinomial(ng, np.full(ng, 1/ng),
                                                               size=cfg['representation_bootstrap_replicates'])
    counts = np.bincount(gid, minlength=ng); den = draws@counts; probability_pairs = []
    for left, right in [('q_mean', 'q_full'), ('q_scalar', 'q_full'), ('classifier', 'q_full')]:
        delta = np.mean(event_losses[right], axis=0)-np.mean(event_losses[left], axis=0)
        b = draws@np.bincount(gid, weights=delta, minlength=ng)/den
        probability_pairs.append(dict(reference=left, model=right, log_score_delta=float(delta.mean()),
                                      CI025=float(np.quantile(b, .025)), CI975=float(np.quantile(b, .975))))
    category_point = []; category_boot = []
    for histogram in category_histograms:
        category_point.append(categorical_information(histogram.sum(0))[0]['relative_sigma_RMS'])
        category_boot.append([categorical_information(np.einsum('g,gjb->jb', d, histogram))[0]['relative_sigma_RMS'] for d in draws])
    category_sigma = np.sqrt(np.mean(np.array(category_boot)**2, axis=0))
    category_center = rms(category_point)
    sigma = {}; bias = {}; summary = []; toy_rows = []; toy_summary = []
    for name in names:
        sigma[name] = np.sqrt(np.mean([a[f'{name}_sigma']**2 for a in arrays], axis=0))
        bias[name] = np.sqrt(np.mean([a[f'{name}_bias']**2 for a in arrays], axis=0))
        for case in ['nominal', 'source_A', 'source_B']:
            selected = [r for r in per_seed if r['model'] == name and r['case'] == case]
            row = dict(model=name, case=case,
                       score_relative_sigma_RMS=rms([float(r['score_relative_sigma_RMS']) for r in selected]),
                       curvature_relative_sigma_RMS=rms([float(r['curvature_relative_sigma_RMS']) for r in selected]),
                       relative_bias_RMS=rms([float(r['relative_bias_RMS']) for r in selected]))
            row.update(score_CI025=float(np.quantile(sigma[name], .025)) if case == 'nominal' else 'unmeasured',
                       score_CI975=float(np.quantile(sigma[name], .975)) if case == 'nominal' else 'unmeasured',
                       bias_CI025=float(np.quantile(bias[name], .025)) if case == 'nominal' else 'unmeasured',
                       bias_CI975=float(np.quantile(bias[name], .975)) if case == 'nominal' else 'unmeasured')
            summary.append(row)
        fits = np.stack([a[f'{name}_fits'] for a in arrays])
        success = np.stack([a[f'{name}_success'] for a in arrays])
        assert success.all()
        rel = fits/f0-1; mean = rel.mean(1); sd = rel.std(1, ddof=1)
        for si in range(3):
            for b in range(6):
                toy_rows.append(dict(model=name, seed=cfg['seeds'][si], bin=b,
                                     toy_mean_relative_bias=mean[si, b], toy_relative_SD=sd[si, b],
                                     mean_MC_standard_error=sd[si, b]/np.sqrt(cfg['toys'])))
        toy_summary.append(dict(model=name, toys_per_seed=cfg['toys'],
                                toy_relative_bias_RMS=rms(mean), toy_relative_SD_RMS=rms(sd),
                                toy_relative_RMSE=rms(rel),
                                boundary_fraction=float(np.mean([a[f'{name}_boundary'] for a in arrays])),
                                max_KKT=max(float(a[f'{name}_kkt'].max()) for a in arrays)))
    paired = []
    centers = {r['model']: r for r in summary if r['case'] == 'nominal'}
    for reference, model in [('q_mean', 'q_full'), ('q_ten', 'q_full'), ('q_scalar', 'q_full'), ('q_ten', 'q_scalar')]:
        rel = 1-sigma[model]/sigma[reference]
        delta = sigma[model]-sigma[reference]; bd = bias[model]-bias[reference]
        valid = np.isfinite(delta) & np.isfinite(bd)
        paired.append(dict(reference=reference, model=model,
                           relative_gain=1-centers[model]['score_relative_sigma_RMS']/centers[reference]['score_relative_sigma_RMS'],
                           relative_CI025=float(np.quantile(rel[valid], .025)), relative_CI975=float(np.quantile(rel[valid], .975)),
                           sigma_delta=centers[model]['score_relative_sigma_RMS']-centers[reference]['score_relative_sigma_RMS'],
                           sigma_CI025=float(np.quantile(delta[valid], .025)), sigma_CI975=float(np.quantile(delta[valid], .975)),
                           bias_delta=centers[model]['relative_bias_RMS']-centers[reference]['relative_bias_RMS'],
                           bias_CI025=float(np.quantile(bd[valid], .025)), bias_CI975=float(np.quantile(bd[valid], .975)),
                           bootstrap_valid=int(valid.sum())))
    gain = paired[0]
    gate = dict(within_required=bool(gain['relative_gain'] >= cfg['minimum_relative_gain'] and gain['relative_CI025'] > 0), **gain)
    (out/'representation_gate.json').write_text(json.dumps(gate, indent=2)+'\n')
    categorical_checks = []
    for name in ['q_full', 'q_scalar']:
        relative = 1-sigma[name]/category_sigma
        categorical_checks.append(dict(model=name, reference='A0_ten_exact_categorical_Fisher',
            reference_relative_sigma_RMS=category_center,
            relative_gain=1-centers[name]['score_relative_sigma_RMS']/category_center,
            relative_CI025=float(np.quantile(relative, .025)), relative_CI975=float(np.quantile(relative, .975))))
    prob_summary = []
    for name in ['classifier']+names:
        rows = [r for r in probability if r['model'] == name]
        prob_summary.append(dict(model=name, **{k: float(np.sum([float(r[k]) for r in rows])) if k == 'zero_true_probability_count'
                                                 else float(np.mean([float(r[k]) for r in rows]))
                                                 for k in rows[0] if k not in ['model', 'seed']}))
    for filename, rows in [('representation_seed_metrics.tsv', per_seed), ('representation_bins.tsv', bin_rows),
                           ('probability_seed_metrics.tsv', probability), ('probability_summary.tsv', prob_summary),
                           ('probability_paired.tsv', probability_pairs), ('probability_truth_bins.tsv', truth_probability),
                           ('categorical_information_check.tsv', categorical_checks),
                           ('probability_reliability.tsv', reliability), ('representation_summary.tsv', summary),
                           ('representation_paired.tsv', paired), ('representation_toys.tsv', toy_rows),
                           ('representation_toy_summary.tsv', toy_summary)]:
        write_table(out/filename, rows)
    # Keep the legacy observation's result as an explicitly labelled historical reference.
    legacy = [r for r in read(root/'workbook/stage23_energy_ml/model_summary.tsv')
              if r.get('model') == 'bdt_UU' and r['scheme'] == 'energy' and r['case'] == 'nominal']
    (out/'historical_scalar_reference.json').write_text(json.dumps(dict(
        source='workbook/stage23_energy_ml/model_summary.tsv', rows=legacy,
        limitation='Same validation events, different training/early-stopping/response estimation; not a dimensionality-only contrast.'), indent=2)+'\n')
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.4), layout='constrained')
    macro = read(out/'oracle_macro.tsv'); x = np.arange(len(macro))
    point = np.array([float(r['macro_log_RMSE']) for r in macro])
    axes[0].errorbar(x, point, yerr=[point-[float(r['CI025']) for r in macro],
                                      [float(r['CI975']) for r in macro]-point], fmt='o', capsize=4)
    axes[0].set(xticks=x, xticklabels=[r['model'] for r in macro], ylabel='Macro log-RMSE', title='A: isolated oracle inputs')
    centers_list = [centers[n] for n in names]; point = 100*np.array([r['score_relative_sigma_RMS'] for r in centers_list])
    axes[1].errorbar(np.arange(4), point, yerr=[point-100*np.array([float(r['score_CI025']) for r in centers_list]),
                                             100*np.array([float(r['score_CI975']) for r in centers_list])-point], fmt='o', capsize=4)
    axes[1].set(xticks=np.arange(4), xticklabels=['Full q', 'Mean(q)', 'Scalar spline', 'Scalar 10 bins'],
                ylabel='Response-calibrated score: relative sigma RMS [%]', title='B: N=1000, fixed shape')
    path = out/'information_gap.svg'
    fig.savefig(path, metadata={'Date': None}); plt.close(fig)
    path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
    print(json.dumps(dict(summary=summary, paired=paired, toys=toy_summary, gate=gate), indent=2))


if __name__ == '__main__':
    main()
