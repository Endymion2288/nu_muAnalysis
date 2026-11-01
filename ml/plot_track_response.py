#!/usr/bin/env python3
"""Standalone stage31 development figure from the measured tables."""
import argparse,csv
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['svg.fonttype']='none'


def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1]);a=p.parse_args()
    folder=a.repo/'workbook/stage31_energy_ml'
    def read(name):return list(csv.DictReader((folder/name).open(),delimiter='\t'))
    metrics=read('metrics.tsv');curvature=read('curvature.tsv')
    fig,axes=plt.subplots(1,3,figsize=(12,3.6),layout='constrained')
    for model,label in [('nu_F5','F5 (46 inputs)'),('nu_F6','F6 (65 inputs)')]:
        rows=[r for r in metrics if r['stratum']=='energy_GeV' and r['model']==model and r['metric']=='log_RMSE']
        x=np.array([np.sqrt(np.prod([float(v) for v in r['value'].split('_')])) for r in rows])
        axes[0].plot(x,[float(r['point']) for r in rows],'o-',label=label)
    axes[0].set(xlabel='True neutrino energy [GeV]',ylabel='log-RMSE',title='Same-event neutrino prediction')
    axes[0].legend(fontsize=8)
    rows=[r for r in curvature if r['stratum']=='primary_p_GeV_confirmed' and r['value']!='0_100']
    x=np.array([np.sqrt(np.prod([float(v) for v in r['value'].split('_')])) for r in rows])
    for ax,key,scale,title,ylabel in [(axes[1],'R68_delta_kappa_GeVinv',1e4,'Primary-confirmed composite response',r'$R_{68}(\kappa_{reco}-\kappa_{vertex})$ [$10^{-4}$ GeV$^{-1}$]'),
                                    (axes[2],'signflip_fraction',100,'Primary-confirmed charge disagreement','Reconstructed vs primary charge [%]')]:
        v=np.array([float(r[key]) for r in rows])*scale
        lo=np.array([float(r[key+'_CI025']) for r in rows])*scale;hi=np.array([float(r[key+'_CI975']) for r in rows])*scale
        ax.errorbar(x,v,yerr=np.stack([v-lo,hi-v]),fmt='o-',capsize=3)
        ax.set(xlabel='Primary production momentum [GeV]',ylabel=ylabel,title=title)
    for ax in axes:ax.set_xscale('log');ax.grid(alpha=.25)
    fig.suptitle('Stage31 development: unit MC, 3 seeds; source bootstrap 95% intervals; no same-surface truth',fontsize=10)
    path=folder/'track_response.svg'
    fig.savefig(path)
    path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
    plt.close(fig)

if __name__=='__main__':main()
