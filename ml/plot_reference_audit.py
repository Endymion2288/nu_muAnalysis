#!/usr/bin/env python3
"""Plot measured interval endpoints, without estimating unobserved plane truth."""
import csv
import argparse
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--png-preview',type=Path)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]/'workbook/stage32_energy_ml'
    rows=list(csv.DictReader((root/'reference_events.tsv').open(),delimiter='\t'))
    bounded=[r for r in rows if r['bound_available']=='True']
    bounded.sort(key=lambda r:float(r['primary_p_GeV']))
    plt.rcParams.update({'svg.fonttype':'none','font.size':10})
    fig,axes=plt.subplots(1,3,figsize=(14,4.5),layout='constrained')
    for r in bounded:
        p=float(r['primary_p_GeV']);lo=float(r['p_low_GeV']);hi=float(r['p_high_GeV'])
        axes[0].plot([p,p],[100*(1-hi/p),100*(1-lo/p)],color='tab:blue',lw=2)
        axes[0].scatter(p,100*(1-float(r['reco_p_GeV'])/p),s=25,
                        marker='x' if r['sign_disagreement']=='True' else 'o',color='tab:orange')
    axes[0].plot([],[],color='tab:blue',lw=2,label='Transport loss bounds')
    axes[0].scatter([],[],color='tab:orange',s=25,label='Reco deficit vs production')
    axes[0].set(xscale='log',xlabel='Primary production momentum [GeV]',ylabel='Fractional deficit [%]',
                title='15 bounded cases; no interpolation')
    axes[0].axhline(0,color='.7',lw=.8);axes[0].legend(fontsize=8)
    for i,r in enumerate(bounded):
        lo=float(r['aligned_residual_low']);hi=float(r['aligned_residual_high'])
        axes[1].plot([lo,hi],[i,i],color='tab:blue',lw=2)
        axes[1].scatter(float(r['production_aligned_residual']),i,color='tab:orange',s=12)
    axes[1].axvline(0,color='.7',lw=.8)
    for x in [-3,3]:axes[1].axvline(x,color='.7',ls='--',lw=.8)
    axes[1].set(xlabel=r'$q_{true}(\kappa_{reco}-\kappa_{truth})/\sigma_{fit}$',
                ylabel='Case (increasing primary momentum)',title='Blue: same-plane intervals; orange: production')
    axes[1].set_xlim(-3.2,3.2)
    p=np.array([float(r['primary_p_GeV']) for r in rows]);sig=np.array([float(r['abs_kappa_over_sigma']) for r in rows])
    for label,color,mask,marker in [
        ('Confirmed, same sign','tab:blue',np.array([r['confirmed']=='True' and r['sign_disagreement']=='False' for r in rows]),'o'),
        ('Confirmed, opposite sign','tab:red',np.array([r['confirmed']=='True' and r['sign_disagreement']=='True' for r in rows]),'x'),
        ('Unconfirmed','tab:gray',np.array([r['confirmed']=='False' for r in rows]),'s')]:
        axes[2].scatter(p[mask],sig[mask],color=color,marker=marker,s=30,label=label)
    axes[2].axhline(2,color='.7',ls='--',lw=.8)
    axes[2].set(xscale='log',yscale='log',xlabel='Primary production momentum [GeV]',
                ylabel=r'$|\kappa_{reco}|/\sigma_{fit}$',title='All 24 covariance cases')
    axes[2].legend(fontsize=8)
    path=root/'reference_diagnostics.svg';fig.savefig(path)
    path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
    if args.png_preview:fig.savefig(args.png_preview,dpi=130)
    plt.close(fig)

if __name__=='__main__':main()
