#!/usr/bin/env python3
"""Export compact scientific figures for stage42."""
import csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
matplotlib.rcParams['svg.hashsalt']='nu_mu_stage42'
import matplotlib.pyplot as plt
import numpy as np

repo=Path(__file__).resolve().parents[1]; out=repo/'workbook/stage42_energy_ml'
def read(name): return list(csv.DictReader((out/name).open(),delimiter='\t'))
fig,axes=plt.subplots(1,2,figsize=(11,4.4),layout='constrained')
for ax,part in zip(axes,['A','B']):
    rows=[r for r in read(part+'_paired.tsv') if r['stratum']=='focus']
    point=100*np.array([float(r['relative_gain']) for r in rows]); lo=100*np.array([float(r['CI025']) for r in rows]); hi=100*np.array([float(r['CI975']) for r in rows])
    ax.errorbar(point,np.arange(len(rows)),xerr=[point-lo,hi-point],fmt='o',capsize=4)
    ax.axvline(0,color='grey',lw=1); ax.set(yticks=np.arange(len(rows)),yticklabels=[r['reference']+' → '+r['model'] for r in rows],xlabel='Relative log-RMSE gain [%]',title=f'{part}: source-paired development, reco p 100–1000 GeV')
fig.savefig(out/'energy_information.svg');plt.close(fig)
with np.load(repo/'ntuples/energy_ml_stage42/development.npz') as z: d={k:z[k] for k in z.files}
with np.load(repo/'ntuples/energy_ml_stage42/sensitive.npz') as z: rows=z['cache_row']; energy=z['hit_energy_MeV'].sum(1)
focus=(d['reco_p_GeV'][rows]<1000)&(d['reco_p_GeV'][rows]>=100)
fig,axes=plt.subplots(1,2,figsize=(11,4.3),layout='constrained')
h=axes[0].hexbin(d['vertex_z_mm'][rows][focus],np.log10(1+energy[focus]),gridsize=(30,25),mincnt=1,cmap='viridis')
fig.colorbar(h,ax=axes[0],label='Events')
axes[0].set(xlabel='True interaction z [mm]',ylabel='log10(1 + sensitive energy / MeV)',title='Ideal sensitive-layer sampling (oracle)')
base=[r for r in read('B_metrics.tsv') if r['stratum'].startswith('focus_z')]
for model in ['I0','Iz','Is','Isz']:
    vals=[r for r in base if r['model']==model]
    axes[1].plot(np.arange(len(vals)),[float(r['log_RMSE']) for r in vals],marker='o',label=model)
axes[1].set(xticks=np.arange(len(vals)),xticklabels=['upstream','−2812:−2600','−2600:−2300','−2300:−1950','lead region'],xlabel='True-z region [mm]',ylabel='ν log-RMSE',title='Fixed-capacity comparison by true z (development)')
axes[1].tick_params(axis='x',labelsize=8);axes[1].legend()
fig.savefig(out/'sensitive_geometry.svg');plt.close(fig)

if (out/'C_paired.tsv').exists():
    rows=[r for r in read('C_paired.tsv') if r['stratum']=='focus' and r['reference']=='I0']
    point=100*np.array([float(r['relative_gain']) for r in rows]); lo=100*np.array([float(r['CI025']) for r in rows]); hi=100*np.array([float(r['CI975']) for r in rows])
    fig,ax=plt.subplots(figsize=(8,4),layout='constrained')
    ax.errorbar(point,np.arange(len(rows)),xerr=[point-lo,hi-point],fmt='o',capsize=4)
    ax.axvline(0,color='grey',lw=1)
    ax.set(yticks=np.arange(len(rows)),yticklabels=[r['model'] for r in rows],xlabel='Relative log-RMSE gain over I0 [%]',title='Synthetic response only: source-paired development, reco p 100–1000 GeV')
    fig.savefig(out/'synthetic_energy_information.svg');plt.close(fig)

# Matplotlib SVG path lines carry trailing blanks; normalize the exported text.
for artifact in out.glob('*.svg'):
    artifact.write_text(''.join(line.rstrip()+'\n' for line in artifact.read_text().splitlines()))
