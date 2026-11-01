#!/usr/bin/env python3
"""Source-paired stage47 figures, exported as standalone SVG."""
import csv
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from coarse_depth import REPO,load_inputs

out=Path(__file__).resolve().parents[1]/'workbook/stage47_energy_ml'
rows=list(csv.DictReader((out/'paired.tsv').open(),delimiter='\t'))
fig,ax=plt.subplots(figsize=(8,4),constrained_layout=True)
pairs=[('local','ordinary_calo','Sensitive S vs X'),('oracle_z','ordinary_calo_z','Sensitive S + z vs X + z'),('ordinary_calo','ordinary_calo_z','Sensitive S + z vs S')]
for shift,s,label in [(-.16,'focus','100–1000 GeV'),(0,'p100_250','100–250 GeV'),(.16,'p250_1000','250–1000 GeV')]:
    v=[next(r for r in rows if r['stratum']==s and r['reference']==a and r['model']==b) for a,b,_ in pairs]
    g=np.array([float(r['relative_gain']) for r in v])*100
    lo=np.array([float(r['CI025']) for r in v])*100;hi=np.array([float(r['CI975']) for r in v])*100
    ax.errorbar(g,np.arange(len(v))+shift,xerr=[g-lo,hi-g],fmt='o',capsize=3,label=label)
ax.axvline(0,color='k',lw=.8);ax.axvline(2,color='k',ls=':',label='2% threshold for S vs X')
ax.set(yticks=range(len(pairs)),yticklabels=[p[2] for p in pairs],xlabel='Relative log-RMSE improvement [%]',title='Development MC; source-paired 95% intervals')
ax.invert_yaxis();ax.legend(fontsize=8);fig.savefig(out/'ordinary_calo_contrasts.svg');plt.close(fig)
fig,ax=plt.subplots(figsize=(8,4),constrained_layout=True)
strata=['focus_z-3000_-2928','focus_z-2812_-2600','focus_z-2600_-2300','focus_z-2300_-1950','focus_z-1769.65_-1619.65']
for shift,ref,name,label in [(-.1,'local','ordinary_calo','Sensitive S vs X'),(.1,'oracle_z','ordinary_calo_z','Sensitive S + z vs X + z')]:
    v=[next(r for r in rows if r['stratum']==s and r['reference']==ref and r['model']==name) for s in strata]
    g=np.array([float(r['relative_gain']) for r in v])*100;lo=np.array([float(r['CI025']) for r in v])*100;hi=np.array([float(r['CI975']) for r in v])*100
    ax.errorbar(g,np.arange(len(v))+shift,xerr=[g-lo,hi-g],fmt='o',capsize=3,label=label)
ax.axvline(0,color='k',lw=.8);ax.set(yticks=range(5),yticklabels=[s.removeprefix('focus_z').replace('_',' to ')+' mm' for s in strata],xlabel='Relative log-RMSE improvement [%]',title='Truth depth for diagnosis only; reco p 100–1000 GeV')
ax.invert_yaxis();ax.legend();fig.savefig(out/'depth_gain.svg');plt.close(fig)
ids,d,_=load_inputs()
with np.load(REPO/'ntuples/energy_ml_stage47/sensitive.npz') as z:
    np.testing.assert_array_equal(ids,z['cache_row']);sensitive=z['hit_energy_MeV'].sum(axis=1)/1000
names=json.loads((REPO/'workbook/stage42_energy_ml/preparation.json').read_text())['feature_names']
reco=d['x'][:,names.index('ML_calo_total_E_EM_GeV')]
focus=(d['reco_p_GeV']>=100)&(d['reco_p_GeV']<1000)
assert (sensitive[focus]>0).all() and (reco[focus]>0).all()
fig,ax=plt.subplots(figsize=(6.5,4.6),constrained_layout=True)
hexes=ax.hexbin(sensitive[focus],reco[focus],xscale='log',yscale='log',gridsize=35,mincnt=1,bins='log',cmap='viridis')
ax.set(xlabel='Saved sensitive deposit [GeV]',ylabel='Existing reconstructed energy [GeV EM]',title='Ordinary Ecal; reco p 100–1000 GeV, 3024 events')
fig.colorbar(hexes,ax=ax,label='Events per cell');fig.savefig(out/'sensitive_vs_readout.svg');plt.close(fig)
for path in [out/'ordinary_calo_contrasts.svg',out/'depth_gain.svg',out/'sensitive_vs_readout.svg']:
    path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
