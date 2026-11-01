#!/usr/bin/env python3
"""Source-paired stage44 figures, exported as standalone SVG."""
import csv
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

out=Path(__file__).resolve().parents[1]/'workbook/stage44_energy_ml'
rows=list(csv.DictReader((out/'paired.tsv').open(),delimiter='\t'))
fig,ax=plt.subplots(figsize=(8,4),constrained_layout=True)
pairs=[('I0','counts','F6 + station counts vs F6'),('I0','local','F6 + local activity vs F6'),
       ('counts','local','Local activity vs counts'),('null','local','Local activity vs shuffled axes')]
for shift,s,label in [(-.16,'focus','100–1000 GeV'),(0,'p100_250','100–250 GeV'),(.16,'p250_1000','250–1000 GeV')]:
    v=[next(r for r in rows if r['stratum']==s and r['reference']==a and r['model']==b) for a,b,_ in pairs]
    g=np.array([float(r['relative_gain']) for r in v])*100
    lo=np.array([float(r['CI025']) for r in v])*100;hi=np.array([float(r['CI975']) for r in v])*100
    ax.errorbar(g,np.arange(len(v))+shift,xerr=[g-lo,hi-g],fmt='o',capsize=3,label=label)
ax.axvline(0,color='k',lw=.8);ax.axvline(2,color='k',ls=':',label='2% vs F6 practical threshold')
ax.set(yticks=range(len(pairs)),yticklabels=[p[2] for p in pairs],xlabel='Relative log-RMSE improvement [%]',title='Same-event development evidence; source-paired 95% intervals')
ax.invert_yaxis();ax.legend(fontsize=8);fig.savefig(out/'local_activity_gain.svg');plt.close(fig)
fig,ax=plt.subplots(figsize=(8,4),constrained_layout=True)
strata=['focus_z-3000_-2928','focus_z-2812_-2600','focus_z-2600_-2300','focus_z-2300_-1950','focus_z-1769.65_-1619.65']
for shift,ref,name,label in [(-.1,'I0','local','Local vs F6'),(.1,'null','local','Local vs shuffled axes')]:
    v=[next(r for r in rows if r['stratum']==s and r['reference']==ref and r['model']==name) for s in strata]
    g=np.array([float(r['relative_gain']) for r in v])*100;lo=np.array([float(r['CI025']) for r in v])*100;hi=np.array([float(r['CI975']) for r in v])*100
    ax.errorbar(g,np.arange(len(v))+shift,xerr=[g-lo,hi-g],fmt='o',capsize=3,label=label)
ax.axvline(0,color='k',lw=.8);ax.set(yticks=range(5),yticklabels=[s.removeprefix('focus_z').replace('_',' to ')+' mm' for s in strata],xlabel='Relative log-RMSE improvement [%]',title='Truth depth for diagnosis only; reco p 100–1000 GeV')
ax.invert_yaxis();ax.legend();fig.savefig(out/'depth_gain.svg');plt.close(fig)
for path in [out/'local_activity_gain.svg',out/'depth_gain.svg']:
    path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
