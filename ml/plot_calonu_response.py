#!/usr/bin/env python3
"""Plot measured timing robustness and the cost of fitting time from noise."""
import csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
repo=Path(__file__).resolve().parents[1];out=repo/'workbook/stage40_energy_ml'
rows=list(csv.DictReader((out/'metrics.tsv').open(),delimiter='\t'))
high=list(csv.DictReader((out/'high_signal_timing.tsv').open(),delimiter='\t'))
plt.rcParams['svg.hashsalt']='stage40'
fig,axs=plt.subplots(1,3,figsize=(13,4),constrained_layout=True)
for prefix,label in [('fixed','Fixed template'),('bounded','Bounded time')]:
    names=([f'fixed_center-2ns','fixed','fixed_center+2ns'] if prefix=='fixed' else ['bounded_center-2ns','bounded_time','bounded_center+2ns'])
    vals=[next(float(r['model_relative_RMSE'])*100 for r in high if r['subset']=='regular' and r['method']==name) for name in names]
    axs[0].plot([-2,0,2],vals,'o-',label=label)
axs[0].set(xlabel='Template centre shift [ns]',ylabel='High-signal model relative RMSE [%]');axs[0].legend(fontsize=8)
for name,label in [('signed','Signed'),('fixed','Fixed template'),('bounded_time','Bounded time')]:
    vals=[next(float(r['rmse_pC']) for r in rows if r['subset']==s and r['method']==name) for s in ['regular_p100_250','regular_p250_1000']]
    axs[1].plot([0,1],vals,'o-',label=label)
axs[1].set(xticks=[0,1],xticklabels=['100–250','250–1000'],xlabel='Reco muon momentum [GeV]',ylabel='Charge RMSE [pC]');axs[1].legend(fontsize=8)
with np.load(repo/'ntuples/energy_ml_stage40/source_noise.npz') as z:
    for name,label in [('fixed','Fixed template'),('bounded','Bounded time')]:
        axs[2].hist(z[name],bins=np.linspace(-.6,.6,40),histtype='step',label=label)
axs[2].set(xlabel='Synthetic noise total charge [pC]',ylabel='Events / bin');axs[2].legend(fontsize=8)
fig.suptitle('Stage40: frozen CC waveform confirmation and separate synthetic source controls')
fig.savefig(out/'response_controls.svg',metadata={'Date':None});fig.savefig('/tmp/stage40_response_controls.png',dpi=130)
p=out/'response_controls.svg';p.write_text('\n'.join(line.rstrip() for line in p.read_text().splitlines())+'\n')
plt.close(fig)
