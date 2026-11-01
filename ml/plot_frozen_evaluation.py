#!/usr/bin/env python3
"""Standalone stage34 plots, using measured tables only."""
import csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def read(path):
    return list(csv.DictReader(path.open(), delimiter='\t'))


def save_svg(fig, path):
    fig.savefig(path)
    path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines()) + '\n')


def errors(ax, rows, key, labels, models, scale=1):
    x = np.arange(len(labels))
    for j, (model, label, color) in enumerate(models):
        values = [next(r for r in rows if r['subset'] == s and r['model'] == model) for s in labels]
        y = np.array([float(r[key]) for r in values]) * scale
        lo = np.array([float(r[key + '_lo']) for r in values]) * scale
        hi = np.array([float(r[key + '_hi']) for r in values]) * scale
        # Percentile intervals can exclude the plug-in point; draw endpoints directly.
        xx = x + (j - (len(models) - 1) / 2) * .12
        ax.vlines(xx, lo, hi, color=color, alpha=.8)
        ax.plot(xx, y, 'o-', color=color, label=label, ms=4)
    ax.set_xticks(x)
    ax.grid(alpha=.2)


def main():
    root = Path(__file__).resolve().parents[1] / 'workbook/stage34_energy_ml'
    rows = read(root / 'test_metrics.tsv')
    models = [('F5_cal', 'F5 calibrated', '#0072B2'), ('F6_cal', 'F6 calibrated', '#D55E00')]
    reco = ['reco_p_100_250', 'reco_p_250_1000', 'reco_p_ge1000']
    fig, ax = plt.subplots(2, 2, figsize=(11, 8), constrained_layout=True)
    errors(ax[0, 0], rows, 'log_RMSE', reco, models)
    ax[0, 0].set_xticklabels(['100–250', '250–1000', '≥1000 (reference)'])
    ax[0, 0].set(xlabel='Reconstructed muon p [GeV]', ylabel='Neutrino log-RMSE')
    ax[0, 0].legend()
    errors(ax[0, 1], rows, 'mean_bias', reco, models, 100)
    ax[0, 1].set_xticklabels(['100–250', '250–1000', '≥1000 (reference)'])
    ax[0, 1].axhline(0, color='gray', lw=.7)
    ax[0, 1].set(xlabel='Reconstructed muon p [GeV]', ylabel='Mean neutrino relative bias [%]')
    mu = read(root / 'test_muon_production_response.tsv')
    mu = [dict(r, model='raw_mu') for r in mu]
    errors(ax[1, 0], mu, 'R68', ['confirmed_truth_p_100_250', 'confirmed_truth_p_250_1000',
                               'confirmed_truth_p_ge1000'], [('raw_mu', 'Raw muon vs production p', '#009E73')], 100)
    ax[1, 0].set_xticklabels(['100–250', '250–1000', '≥1000 (reference)'])
    ax[1, 0].set(xlabel='Primary muon p [GeV], confirmed only', ylabel='Muon relative error R68 [%]')
    ys = ['confirmed_y_0_0.1', 'confirmed_y_0.1_0.2', 'confirmed_y_0.2_0.4',
          'confirmed_y_0.4_0.6', 'confirmed_y_0.6_0.8', 'confirmed_y_0.8_1.0']
    errors(ax[1, 1], rows, 'log_RMSE', ys, models)
    ax[1, 1].set_xticklabels(['0–.1', '.1–.2', '.2–.4', '.4–.6', '.6–.8', '.8–1'])
    ax[1, 1].set(xlabel='Leptonic y, confirmed only', ylabel='Neutrino log-RMSE')
    fig.suptitle('Locked test: unit MC, source-group 95% intervals\nCalibration uncertainty propagated; no detector/interaction closure')
    save_svg(fig, root / 'locked_test.svg')
    fig.savefig('/tmp/stage34_locked_test.png', dpi=140)
    plt.close(fig)
    challenge = read(root / 'challenge_pi_common_energy.tsv')
    fig, ax = plt.subplots(figsize=(7, 4), constrained_layout=True)
    for j, (model, label, color) in enumerate(models):
        r = [next(v for v in challenge if v['partition'] == p and v['model'] == model) for p in ['test', 'challenge']]
        x = np.arange(2) + (j - .5) * .1
        ax.vlines(x, [float(v['lo']) for v in r], [float(v['hi']) for v in r], color=color)
        ax.plot(x, [float(v['macro_log_RMSE']) for v in r], 'o-', color=color, label=label)
    ax.set_xticks([0, 1], ['Nominal π (test)', 'SIBYLL π (challenge)'])
    ax.set(ylabel='Common-energy macro log-RMSE', title='π-only comparison, common true-energy bins\nUnit mixtures; frozen nominal calibration')
    ax.grid(alpha=.2)
    ax.legend()
    save_svg(fig, root / 'pi_challenge.svg')
    plt.close(fig)


if __name__ == '__main__':
    main()
