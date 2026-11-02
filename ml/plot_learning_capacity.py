#!/usr/bin/env python3
"""Finite capacity and training-support gains with source-paired intervals."""
import csv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from learning_capacity import OUT

rows=list(csv.DictReader((OUT/'paired.tsv').open(),delimiter='\t'))
fig,ax=plt.subplots(figsize=(8.4,4.4),constrained_layout=True)
pairs=[('L3_F6','L5_F6','Depth5 vs depth3; F6'),('L3_F6','L3_F6z','True z increment; depth3'),('L5_F6','L5_F6z','True z increment; depth5')]
for shift,stratum,label in [(-.16,'focus','Reco p 100–1000 GeV'),(0,'p100_250','Reco p 100–250 GeV'),(.16,'p250_1000','Reco p 250–1000 GeV')]:
    v=[next(r for r in rows if r['support']=='A_full' and r['stratum']==stratum and r['reference']==a and r['model']==b) for a,b,_ in pairs]
    g=np.array([float(r['relative_gain']) for r in v])*100;lo=np.array([float(r['CI025']) for r in v])*100;hi=np.array([float(r['CI975']) for r in v])*100
    ax.errorbar(g,np.arange(len(v))+shift,xerr=[g-lo,hi-g],fmt='o',capsize=3,label=label)
ax.axvline(0,color='k',lw=.8);ax.axvline(2,color='k',ls=':',label='2% practical criterion')
ax.set(yticks=range(3),yticklabels=[p[2] for p in pairs],xlabel='Relative log-RMSE improvement [%]',title='Full development support: 14309 events / 81 sources')
ax.invert_yaxis();ax.legend(fontsize=8);fig.savefig(OUT/'capacity_contrasts.svg');plt.close(fig)
fig,ax=plt.subplots(figsize=(8.4,4.4),constrained_layout=True)
labels=[('B_training_support','I0','A0','More support; original calibration'),('B_training_support','I0','A0_common_B','More training support; common B-cal'),
        ('A_B_sources','L3_F6','L5_F6','Depth5; original 21 sources'),('A_remaining_sources','L3_F6','L5_F6','Depth5; all remaining 60 sources')]
v=[next(r for r in rows if r['support']==s and r['stratum']=='focus' and r['reference']==a and r['model']==b) for s,a,b,_ in labels]
g=np.array([float(r['relative_gain']) for r in v])*100;lo=np.array([float(r['CI025']) for r in v])*100;hi=np.array([float(r['CI975']) for r in v])*100
ax.errorbar(g,np.arange(len(v)),xerr=[g-lo,hi-g],fmt='o',capsize=3)
ax.axvline(0,color='k',lw=.8);ax.axvline(2,color='k',ls=':')
ax.set(yticks=range(len(v)),yticklabels=[f'{label}\nN={r["N"]}; sources={r["sources"]}' for (_,_,_,label),r in zip(labels,v)],
       xlabel='Relative log-RMSE improvement [%]',title='Same-event comparisons; reco p 100–1000 GeV')
ax.invert_yaxis();fig.savefig(OUT/'support_contrasts.svg');plt.close(fig)
for path in [OUT/'capacity_contrasts.svg',OUT/'support_contrasts.svg']:path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
