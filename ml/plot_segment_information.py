#!/usr/bin/env python3
"""Event-risk contrasts and local-relation control with paired-source intervals."""
import argparse
import csv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from segment_information import OUT
parser=argparse.ArgumentParser();parser.add_argument('--png');args=parser.parse_args()
rows=list(csv.DictReader((OUT/'paired.tsv').open(),delimiter='\t'))
pairs=[('F6','angles','Angles vs F6'),('F6','convergence','Angles + local convergence vs F6'),('F6','shuffle','Angles + shuffled convergence vs F6'),('angles','convergence','Convergence increment over angles'),('shuffle','convergence','Actual vs shuffled pairing')]
fig,ax=plt.subplots(figsize=(9,5.2),constrained_layout=True)
for shift,stratum,label in [(-.16,'focus','Reco p 100–1000 GeV'),(0,'p100_250','100–250 GeV'),(.16,'p250_1000','250–1000 GeV')]:
    v=[next(r for r in rows if r['support']=='A_full' and r['stratum']==stratum and r['reference']==a and r['model']==b) for a,b,_ in pairs]
    gain=np.array([float(r['relative_gain']) for r in v])*100;lo=np.array([float(r['CI025']) for r in v])*100;hi=np.array([float(r['CI975']) for r in v])*100
    ax.errorbar(gain,np.arange(len(v))+shift,xerr=[gain-lo,hi-gain],fmt='o',capsize=3,label=label)
ax.axvline(0,color='k',lw=.8);ax.axvline(2,color='k',ls=':',label='2% practical criterion')
ax.set(yticks=range(len(pairs)),yticklabels=[r[2] for r in pairs],xlabel='Relative log-RMSE improvement [%]',title='14309 development events / 81 sources; fixed depth5 baseline')
ax.invert_yaxis();ax.legend(fontsize=8);path=OUT/'segment_information.svg';fig.savefig(path)
if args.png:fig.savefig(args.png,dpi=140)
plt.close(fig)
path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
