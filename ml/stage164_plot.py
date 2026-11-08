"""Standalone matched-control and traditional-risk comparison figure."""
import csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from stage164_common import OUT
rows=list(csv.DictReader((OUT/'paired.tsv').open(),delimiter='\t'))
fig,axes=plt.subplots(1,2,figsize=(13,4.8),layout='constrained')
contrasts=[('H','A','Unaccepted H / A (cached)'),('AZ','A','Depth / A'),('AZH','AZ','H conditional on depth'),('AZH','H','Depth conditional on H')]
for ax,role,title in zip(axes,[2,3],['Calibration development','Test development']):
    for j,(a,b,label) in enumerate(contrasts):
        values=[next(r for r in rows if int(r['role'])==role and r['candidate']==a and r['reference']==b and r['stratum']==layer) for layer in ['E50_100','E100_200','all']]
        x=np.arange(3)+(j-1.5)*.14;y=np.array([float(r['RMSE_ratio']) for r in values]);lo=np.array([float(r['low95']) for r in values]);hi=np.array([float(r['high95']) for r in values])
        ax.errorbar(x,y,yerr=[np.maximum(0,y-lo),np.maximum(0,hi-y)],fmt='o',capsize=3,label=label)
    ax.axhline(1,color='gray',lw=1);ax.set_xticks([0,1,2],['50–100 GeV','100–200 GeV','All selected']);ax.set_ylabel('Paired log-RMSE ratio (conditional 95% interval)');ax.set_title(title);ax.grid(axis='y',alpha=.25)
axes[0].legend(fontsize=8);fig.suptitle('Same-support response experiment; conditional replay cohort, no promotion')
fig.savefig(OUT/'energy_comparisons.svg');fig.savefig(OUT/'energy_comparisons.png',dpi=150);plt.close(fig)
path=OUT/'energy_comparisons.svg';path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
