#!/usr/bin/env python3
"""Standalone figures for the pre-specified source-transfer contrasts."""
import csv
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from source_transfer import OUT,REPO

rows=list(csv.DictReader((OUT/'paired.tsv').open(),delimiter='\t'))
labels=[('all','All events'),('focus','Reco p 100–1000 GeV'),('p100_250','Reco p 100–250 GeV'),('p250_1000','Reco p 250–1000 GeV'),
        ('p1000_up','Reco p >=1000 GeV (reference)'),('focus_y0.8_1.01','High y >=0.8; focus'),('focus_z-2300_-1950','Downstream target; focus')]
v=[next(r for r in rows if r['stratum']==s) for s,_ in labels]
g=np.array([float(r['relative_gain']) for r in v])*100;lo=np.array([float(r['CI025']) for r in v])*100;hi=np.array([float(r['CI975']) for r in v])*100
fig,ax=plt.subplots(figsize=(8.3,4.6),constrained_layout=True)
ax.errorbar(g,np.arange(len(v)),xerr=[g-lo,hi-g],fmt='o',capsize=3,label='Frozen Z vs X; paired sources')
ax.axvline(0,color='k',lw=.8);ax.axvline(2,color='k',ls=':',label='2% focus criterion')
ax.set(yticks=range(len(v)),yticklabels=[f'{label}\nN={r["N"]}; sources={r["sources"]}' for (_,label),r in zip(labels,v)],
       xlabel='Relative log-RMSE improvement [%]',title='Source-external development replication; 95% intervals')
ax.invert_yaxis();ax.legend(fontsize=8);fig.savefig(OUT/'source_transfer.svg');plt.close(fig)
regions=['focus_z-3000_-2928','focus_z-2812_-2600','focus_z-2600_-2300','focus_z-2300_-1950','focus_z-1769.65_-1619.65']
old=list(csv.DictReader((REPO/'workbook/stage47_energy_ml/paired.tsv').open(),delimiter='\t'))
fig,ax=plt.subplots(figsize=(8.3,4.3),constrained_layout=True)
for shift,records,label in [(-.1,old,'Original 21 sources (historical)'),(.1,rows,'External 60 sources (development)')]:
    v=[next(r for r in records if r['stratum']==s and r['reference']=='local' and r['model']=='oracle_z') for s in regions]
    g=np.array([float(r['relative_gain']) for r in v])*100;lo=np.array([float(r['CI025']) for r in v])*100;hi=np.array([float(r['CI975']) for r in v])*100
    ax.errorbar(g,np.arange(5)+shift,xerr=[g-lo,hi-g],fmt='o',capsize=3,label=label)
ax.axvline(0,color='k',lw=.8);ax.set(yticks=range(5),yticklabels=[s.removeprefix('focus_z').replace('_',' to ')+' mm' for s in regions],
    xlabel='Z vs X relative log-RMSE improvement [%]',title='Truth depth for diagnosis; different supports, no causal subtraction')
ax.invert_yaxis();ax.legend(fontsize=8);fig.savefig(OUT/'depth_transfer.svg');plt.close(fig)
for p in [OUT/'source_transfer.svg',OUT/'depth_transfer.svg']:p.write_text('\n'.join(line.rstrip() for line in p.read_text().splitlines())+'\n')
