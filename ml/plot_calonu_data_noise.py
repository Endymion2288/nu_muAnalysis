#!/usr/bin/env python3
"""Standalone scientific figures for the bounded stage43 measurements."""
import csv
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


repo = Path(__file__).resolve().parents[1]; out = repo/'workbook/stage43_energy_ml'
rows = list(csv.DictReader((out/'noise_statistics.tsv').open(), delimiter='\t'))
overall = [r for r in rows if r['stratum'] == 'all']
fig, ax = plt.subplots(1, 2, figsize=(10, 3.5), constrained_layout=True)
for name, color, label in [('finite_pedestal_fixed_RMS_pC', 'C0', 'Measured data block + pedestal'),
                          ('iid_known_pedestal_expected_SD_pC', 'C1', 'IID at measured RMS, known pedestal'),
                          ('iid_40_sample_pedestal_expected_SD_pC', 'C2', 'IID + 40-sample pedestal')]:
    ax[0].plot(range(4), [float(r[name]) for r in overall], 'o-', color=color, label=label)
ax[0].axhline(.05562531697592858, ls=':', color='k', label='Stage42 white-noise RMS')
ax[0].set(xlabel='Module (MC readout order)', ylabel='Fixed-template charge RMS / SD [pC]', xticks=range(4))
ax[0].legend(fontsize=7)
cov = json.loads((out/'noise_covariance.json').read_text())['groups']['all']['charge_correlation']
im = ax[1].imshow(cov, vmin=-1, vmax=1, cmap='coolwarm')
for i in range(4):
    for j in range(4): ax[1].text(j, i, f'{cov[i][j]:.2f}', ha='center', va='center')
ax[1].set(xlabel='Module', ylabel='Module', title='Joint noise charge correlation', xticks=range(4), yticks=range(4))
fig.colorbar(im, ax=ax[1], shrink=.8); fig.savefig(out/'noise_response.svg'); plt.close(fig)

pairs = list(csv.DictReader((out/'paired.tsv').open(), delimiter='\t'))
names = ['ideal_sum', 'data_noise_nominal', 'data_noise_half_gain']
labels = ['Ideal S + sum', 'Data noise / MC gain', 'Data noise / half MC gain']
fig, ax = plt.subplots(figsize=(8, 3.7), constrained_layout=True)
for shift, stratum, label in [(-.15, 'focus', '100–1000 GeV'), (.0, 'p100_250', '100–250 GeV'), (.15, 'p250_1000', '250–1000 GeV')]:
    vals = [next(r for r in pairs if r['stratum'] == stratum and r['reference'] == 'I0' and r['model'] == name) for name in names]
    gain = np.array([float(r['relative_gain']) for r in vals])*100
    lo = np.array([float(r['CI025']) for r in vals])*100; hi = np.array([float(r['CI975']) for r in vals])*100
    ax.errorbar(gain, np.arange(3)+shift, xerr=[gain-lo, hi-gain], fmt='o', label=label, capsize=3)
ax.axvline(0, color='k', lw=.8); ax.axvline(2, color='k', ls=':', label='Frozen practical threshold')
ax.set(yticks=np.arange(3), yticklabels=labels, xlabel='Relative log-RMSE improvement vs F6 [%]',
       title='Same 3703 development MC events; source-paired 95% intervals')
ax.invert_yaxis(); ax.legend(fontsize=8, loc='best'); fig.savefig(out/'energy_gain.svg'); plt.close(fig)

# Matplotlib emits whitespace at SVG path line ends; keep committed figures clean.
for name in ['noise_response.svg', 'energy_gain.svg']:
    path = out/name
    path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
