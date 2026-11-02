#!/usr/bin/env python3
"""Export low-energy truth/reco diagnostics with independently labeled axes."""
import csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

repo=Path(__file__).resolve().parents[1];out=repo/'workbook/stage55_energy_ml'
rows=list(csv.DictReader((out/'metrics.tsv').open(),delimiter='\t'))
models={'mu_p_over0p8':r'$p_\mu/0.8$','frozen_F6_oldcal':'Frozen F6 (>100 GeV training)','nominal50':'Nominal, >50 GeV training','mixture50':'Nominal + alternative flux','residual50':'Residual to muon baseline','matched_flux50':'Alternative flux, matched training prior'}
fig,axs=plt.subplots(2,2,figsize=(11,7),constrained_layout=True)
for col,(prefix,edges,xlabel) in enumerate([('E',[50,75,100,150,200,400,800,1600,3200,6400],r'True $E_\nu$ [GeV]'),('p',[50,75,100,150,250,1000],r'Reconstructed $p_\mu$ [GeV]')]):
 for name,label in models.items():
  values=[];bias=[];centers=[]
  for lo,hi in zip(edges[:-1],edges[1:]):
   r=next((r for r in rows if r['sample']=='nominal' and r['model']==name and r['stratum']==f'{prefix}{lo}_{hi}'),None)
   if r:
    centers.append(np.sqrt(lo*hi));values.append(float(r['log_RMSE']));bias.append(float(r['mean_bias_pct']))
  axs[0,col].plot(centers,values,'o-',label=label,ms=4)
  axs[1,col].plot(centers,bias,'o-',ms=4)
 for ax in axs[:,col]:
  ax.set_xscale('log');ax.set_xlabel(xlabel);ax.grid(alpha=.2)
  ax.axvspan(50,100,color='grey',alpha=.1)
 axs[1,col].axhline(0,color='black',lw=.6)
axs[0,0].set_ylabel('log-RMSE');axs[0,1].set_ylabel('log-RMSE')
axs[1,0].set_ylabel('Mean relative bias [%]');axs[1,1].set_ylabel('Mean relative bias [%]')
axs[0,0].legend(fontsize=8);fig.suptitle('Nominal development evaluation; unit MC, fixed 15 fits\nGlobal calibration on a separate common nominal cohort; no detector systematic uncertainty')
fig.savefig(out/'low_energy_response.svg');fig.savefig(out/'low_energy_response.png',dpi=130)
svg=out/'low_energy_response.svg'
svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
plt.close(fig)
