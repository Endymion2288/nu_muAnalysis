#!/usr/bin/env python3
"""Plot native signal/noise and a saved fit with an overflowing analytic integral."""
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from diagnose_calonu_native import stable_shape


repo = Path(__file__).resolve().parents[1]
out = repo/'workbook/stage37_energy_ml'
with np.load(repo/'ntuples/energy_ml_stage37/native_response.npz') as z:
    d = {k: z[k] for k in z.files}
cases = json.loads(str(d['cases_json']))
regular = [r for r in cases if r['role'] == 'regular']
diagnosis = list(csv.DictReader((out/'nonfinite_integral_diagnosis.tsv').open(), delimiter='\t'))
fig, axes = plt.subplots(2, 2, figsize=(10, 7.4), constrained_layout=True)
ax = axes[0, 0]
for lo, hi, label in [(100, 250, 'reco p 100-250 GeV'), (250, 1000, 'reco p 250-1000 GeV')]:
    rows = [r for r in regular if lo <= r['reco_p_GeV'] < hi]
    ax.scatter([r['hit_energy_total_MeV'] for r in rows], [r['predicted_peak_sigma'] for r in rows], s=20, alpha=.75, label=label)
ax.axhline(5, color='black', ls='--', lw=1, label='5 sigma threshold')
ax.set(xscale='log', yscale='log', xlabel='Saved sensitive-hit energy [MeV]', ylabel='Nominal signal peak / noise sigma', title='96 regular cases; no CaloNu selection')
ax.legend(fontsize=8)
ax = axes[0, 1]
for key, label in [('raw_total_pC', 'Positive-sample raw'), ('noise_total_pC', 'Gaussian rectification scale'),
                   ('predicted_signal_total_pC', 'Nominal HITS signal')]:
    ax.plot(np.arange(96), sorted(r[key] for r in regular), label=label, lw=1.5)
ax.set(yscale='log', xlabel='Separate quantile rank (unpaired)', ylabel='Four-channel charge [pC]', title='Signal is usually below the noise pedestal')
ax.legend(fontsize=8)
row = diagnosis[0]
j = next(j for j, r in enumerate(cases) if r['group'] == int(row['group']) and r['input_entry'] == int(row['input_entry']))
i = int(row['branch'])
ax = axes[1, 0]
t = np.linspace(780, 930, 2001)
pars = [d[k][j, i] for k in ['peak', 'mean', 'width', 'alpha', 'nval']]
ax.plot(d['saved_time'][j, i], d['saved_wave'][j, i], '.', ms=3, label='Saved baseline-subtracted waveform')
ax.plot(t, [stable_shape(x, *pars) for x in t], label='Saved CB parameters; stable evaluation')
ax.set(xlabel='Time [ns]', ylabel='Amplitude [mV]', title='Group 0, entry 11189, branch 0; saved status = 0')
ax.text(.98, .95, 'Saved / replay integral: -inf\nStable integral: 120.344 mV ns', transform=ax.transAxes, ha='right', va='top', fontsize=8)
ax.legend(fontsize=7, loc='upper left')
ax = axes[1, 1]
ax.plot(range(1, len(diagnosis)+1), [float(r['log_ROOT_analytic_A']) for r in diagnosis], 'o', label='Saved nonfinite diagnostic modules')
ax.axhline(np.log(np.finfo(float).max), color='black', ls='--', label='Double precision overflow limit')
ax.set(xlabel='Diagnostic module index (enriched sample)', ylabel='log of analytic intermediate A', title='Finite fit shape; overflowing analytic integral')
ax.legend(fontsize=8)
fig.savefig(out/'native_response.svg')
svg = out/'native_response.svg'
svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
fig.savefig('/tmp/stage37_native_response.png', dpi=130)
plt.close(fig)
