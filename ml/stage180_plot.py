"""Render validated aggregate TSV only; no ROOT/NPZ or physics recomputation."""
import csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage180_energy_ml'
rows=list(csv.DictReader((OUT/'full_amplitude_bins.tsv').open(),delimiter='\t'))
fig,ax=plt.subplots(figsize=(8,4.8),layout='constrained')
for module in range(4):
    chosen=[r for r in rows if int(r['module'])==module and r['validation_median_relative_residual'] and float(r['Lo_peak_upper_mV'])<=2000]
    x=[(float(r['Lo_peak_lower_mV'])+float(r['Lo_peak_upper_mV']))/2 for r in chosen]
    y=[100*float(r['validation_median_relative_residual']) for r in chosen]
    ax.plot(x,y,'o-',label=f'Module {module}',linewidth=1.3,markersize=4)
ax.set_yscale('symlog',linthresh=10);ax.axhline(0,color='0.4',linewidth=.7)
ax.set(xlabel='CaloLo raw peak bin centre [mV]',ylabel='Held-out median relative ratio residual [%]',
    title='Run 15838: fixed even-entry scale, odd-entry response')
ax.grid(alpha=.25);ax.legend(ncol=2)
fig.savefig(OUT/'relative_response.png',dpi=170);fig.savefig(OUT/'relative_response.svg')
svg=OUT/'relative_response.svg'
svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
