"""Standalone diagnostic figures, executed within the full Condor job."""
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

out=Path('workbook/stage195_energy_ml')
s=json.loads((out/'full_summary.json').read_text())
with (out/'full_bins.tsv').open() as f:rows=list(csv.DictReader(f,delimiter='\t'))
fig,axes=plt.subplots(2,2,figsize=(10,7),sharex=True)
for j,ax in enumerate(axes.flat):
    chosen=[r for r in rows if int(r['module'])==j and r['group']=='within2ns' and int(r['N']) and float(r['Lo_peak_upper_mV'])<=2000]
    x=[(float(r['Lo_peak_lower_mV'])+float(r['Lo_peak_upper_mV']))/2 for r in chosen]
    y=[float(r['median_difference_pC']) for r in chosen]
    b=s['noise'][j]['empirical_bound_pC']
    ax.axhspan(-b,b,color='grey',alpha=.2,label='Random-control L1 envelope (conditional)')
    ax.plot(x,y,'o-',label='Held-out median Hi - rho Lo')
    ax.axhline(0,c='k',lw=.6)
    ax.set_title(f'Module {j}; status0, SNR>=10, |dt|<=2 ns')
    ax.set_ylabel('Charge difference [pC]')
    ax.set_xlabel('Lo raw peak [mV]')
    ax.legend(fontsize=7)
fig.suptitle('Same-module relative-response diagnostic; no calibrated signal-error coverage')
fig.tight_layout()
for ext in ['png','svg']:fig.savefig(out/f'conditional_noise_envelope.{ext}',dpi=150)
svg=out/'conditional_noise_envelope.svg'
svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
plt.close(fig)
