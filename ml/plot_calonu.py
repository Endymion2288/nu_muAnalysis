#!/usr/bin/env python3
"""Export the locked same-event CaloNu comparison and its measured depth dependence."""
import csv
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def read(path):
    return list(csv.DictReader(path.open(), delimiter='\t'))


def save(fig, path):
    fig.savefig(path)
    path.write_text('\n'.join(s.rstrip() for s in path.read_text().splitlines()) + '\n')


def points(ax, rows, subsets, key, models, scale=1):
    for j, (model, label, color) in enumerate(models):
        selected = [next(r for r in rows if r['subset'] == s and r['model'] == model) for s in subsets]
        x = np.arange(len(selected)) + (j - .5) * .1
        values = np.array([float(r[key]) for r in selected]) * scale
        lo = np.array([float(r[key + '_lo']) for r in selected]) * scale
        hi = np.array([float(r[key + '_hi']) for r in selected]) * scale
        ax.vlines(x, lo, hi, color=color, alpha=.7)
        ax.plot(x, values, 'o-', label=label, color=color, ms=4)
    ax.set_xticks(np.arange(len(subsets)))
    ax.grid(alpha=.2)


def main():
    root = Path(__file__).resolve().parents[1] / 'workbook/stage35_energy_ml'
    metrics = read(root / 'test_metrics.tsv')
    paired = read(root / 'test_paired.tsv')
    response = read(root / 'test_readout_response.tsv')
    models = [('C0_cal', '65 inputs: CaloNu off', '#0072B2'), ('C1_cal', '70 inputs: CaloNu on', '#D55E00')]
    fig, ax = plt.subplots(2, 2, figsize=(11, 8), constrained_layout=True)
    reco = ['reco_p_100_250', 'reco_p_250_1000', 'reco_p_ge1000']
    points(ax[0, 0], metrics, reco, 'log_RMSE', models)
    ax[0, 0].set_xticklabels(['100–250', '250–1000', '≥1000 (reference)'])
    ax[0, 0].set(xlabel='Reconstructed muon p [GeV]', ylabel='Neutrino log-RMSE')
    ax[0, 0].legend()
    points(ax[0, 1], metrics, reco, 'R68', models, 100)
    ax[0, 1].set_xticklabels(['100–250', '250–1000', '≥1000 (reference)'])
    ax[0, 1].set(xlabel='Reconstructed muon p [GeV]', ylabel='Neutrino relative error R68 [%]')
    depth = ['vertex_z_-3000_-2928', 'vertex_z_-2812_-2650', 'vertex_z_-2650_-2300',
             'vertex_z_-2300_-1950', 'vertex_z_-1769.65_-1619.65']
    selected = [next(r for r in paired if r['subset'] == s and r['reference'] == 'C0_cal') for s in depth]
    x = np.arange(len(selected))
    ax[1, 0].vlines(x, [100 * float(r['relative_log_RMSE_gain_lo']) for r in selected],
                   [100 * float(r['relative_log_RMSE_gain_hi']) for r in selected], color='#009E73')
    ax[1, 0].plot(x, [100 * float(r['relative_log_RMSE_gain']) for r in selected], 'o-', color='#009E73')
    ax[1, 0].axhline(0, color='gray', lw=.7)
    ax[1, 0].set_xticks(x, ['−3000\n−2928', '−2812\n−2650', '−2650\n−2300', '−2300\n−1950', 'Lead\nblock'])
    ax[1, 0].set(xlabel='True interaction z interval [mm], diagnostic only', ylabel='Relative log-RMSE gain [%]')
    ax[1, 0].grid(alpha=.2)
    selected = [next(r for r in response if r['subset'] == s) for s in depth]
    ax[1, 1].vlines(x, [100 * float(r['nonzero_fraction_lo']) for r in selected],
                   [100 * float(r['nonzero_fraction_hi']) for r in selected], color='#CC79A7')
    ax[1, 1].plot(x, [100 * float(r['nonzero_fraction']) for r in selected], 'o-', color='#CC79A7')
    ax[1, 1].set_xticks(x, ['−3000\n−2928', '−2812\n−2650', '−2650\n−2300', '−2300\n−1950', 'Lead\nblock'])
    ax[1, 1].set(xlabel='True interaction z interval [mm], diagnostic only', ylabel='Finite nonzero CaloNu total [%]', ylim=(0, 105))
    ax[1, 1].grid(alpha=.2)
    fig.suptitle('Same-event CaloNu ablation: 3,247 locked test events, unit MC\n95% source intervals; calibration uncertainty propagated; strict primary confirmation unavailable')
    save(fig, root / 'calonu_ablation.svg')
    fig.savefig('/tmp/stage35_calonu.png', dpi=140)
    plt.close(fig)


if __name__ == '__main__':
    main()
