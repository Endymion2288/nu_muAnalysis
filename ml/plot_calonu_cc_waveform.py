#!/usr/bin/env python3
"""Visualise frozen CC support, charge residuals and fixed timing sensitivity."""
import csv
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

repo=Path(__file__).resolve().parents[1];out=repo/'workbook/stage39_energy_ml'
events=list(csv.DictReader((out/'events.tsv').open(),delimiter='\t'))
regular=[r for r in events if r['role']=='regular']
valid=[r for r in regular if r['common_waveform']=='True']
metrics=list(csv.DictReader((out/'readout_metrics.tsv').open(),delimiter='\t'))
plt.rcParams['svg.hashsalt']='stage39'
fig,axs=plt.subplots(1,3,figsize=(14,4),constrained_layout=True)
for common,label in [('True','Saved waveform'),('False','Absent waveform')]:
    vals=[float(r['vertex_z_mm']) for r in regular if r['common_waveform']==common]
    axs[0].hist(vals,bins=np.linspace(-3000,-1600,22),histtype='step',label=label)
axs[0].axvline(-2605.68,color='grey',ls='--',lw=1)
axs[0].set(xlabel='Truth interaction z [mm]',ylabel='Regular CC controls / bin');axs[0].legend(fontsize=8)
for name,label in [('positive_raw','Positive raw'),('signed_saved','Signed'),('template_plus_constant','Template + constant')]:
    vals=[next(float(r['rmse_pC']) for r in metrics if r['subset']==s and r['method']==name)
          for s in ['regular_p100_250','regular_p250_1000']]
    axs[1].plot([0,1],vals,'o-',label=label)
axs[1].set(xticks=[0,1],xticklabels=['100–250','250–1000'],xlabel='Reco muon momentum [GeV]',ylabel='Charge RMSE [pC]',yscale='log')
axs[1].legend(fontsize=8)
for name,label in [('template_time_-2ns','Template −2 ns'),('template_time_+2ns','Template +2 ns')]:
    q=np.array([float(r['nominal_signal_pC']) for r in valid])
    delta=np.array([float(r[name+'_pC'])-float(r['template_plus_constant_pC']) for r in valid])
    axs[2].scatter(q,delta,s=12,alpha=.7,label=label)
axs[2].set(xlabel='Nominal window signal [pC]',ylabel='Readout change from 820 ns [pC]');axs[2].legend(fontsize=8)
fig.suptitle('Stage39: six CC fit sources; fixed waveform readouts; no neutrino-energy fit or data closure')
fig.savefig(out/'cc_waveform.svg',metadata={'Date':None});fig.savefig('/tmp/stage39_cc_waveform.png',dpi=130)
p=out/'cc_waveform.svg';p.write_text('\n'.join(s.rstrip() for s in p.read_text().splitlines())+'\n')
plt.close(fig)
