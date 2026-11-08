"""Fixed paired energy-risk figures from the declared bootstrap tables, batch only."""
import csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
OUT=Path('workbook/stage186_energy_ml');rows=list(csv.DictReader((OUT/'energy_paired.tsv').open(),delimiter='\t'))
fig,axes=plt.subplots(1,2,figsize=(10,4))
for ax,reference,title in [(axes[0],'traditional','Low-energy performance vs traditional'),(axes[1],'R','Ideal vs actual readout')]:
 layers=['E50_100','E100_200'];arms=['A','R','I'] if reference=='traditional' else ['I']
 for i,arm in enumerate(arms):
  data=[next(r for r in rows if r['role']=='3' and r['candidate']==arm and r['reference']==reference and r['stratum']==layer) for layer in layers]
  x=[j+(i-(len(arms)-1)/2)*.12 for j in range(2)];y=[float(r['RMSE_ratio']) for r in data];low=[a-float(r['low95']) for a,r in zip(y,data)];high=[float(r['high95'])-a for a,r in zip(y,data)]
  ax.errorbar(x,y,yerr=[low,high],fmt='o',capsize=3,label=arm)
 ax.axhline(1,color='gray',ls='--',lw=1)
 if reference=='traditional':ax.axhline(1.05,color='darkred',ls=':',lw=1,label='Original upper95 gate')
 ax.set_xticks([0,1],['50–100 GeV','100–200 GeV']);ax.set_ylabel('Weighted log-RMSE ratio');ax.set_title(title);ax.legend();ax.grid(alpha=.2)
fig.suptitle('Original test role; paired incoming 95% intervals (developed pool)');fig.tight_layout();fig.savefig(OUT/'energy_low_bins.png',dpi=180);fig.savefig(OUT/'energy_low_bins.pdf');plt.close(fig)
