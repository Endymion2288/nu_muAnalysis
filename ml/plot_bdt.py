#!/usr/bin/env python3
"""Make publication-exportable SVG diagnostic figures from validation only."""
import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import numpy as np


def save_svg(fig,path):
    fig.savefig(path)
    path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report-dir',type=Path,required=True)
    p.add_argument('--model-dir',type=Path,required=True)
    args=p.parse_args()
    rows=list(csv.DictReader((args.report_dir/'validation_energy_bins.tsv').open(),delimiter='\t'))
    models=['mu_p_over_0p8','F0_direct','F2_direct','F4_direct','F5_direct']
    labels=['p / 0.8','p-only BDT','+ station counts','+ scintillator and Calo','+ global SpacePoint moments']
    fig,axes=plt.subplots(1,3,figsize=(14,4),layout='constrained')
    for model,label in zip(models,labels):
        selected=[r for r in rows if r['model']==model and r['primary_bin']=='1']
        x=[np.sqrt(float(r['energy_low_GeV'])*float(r['energy_high_GeV'])) for r in selected]
        for ax,metric in zip(axes,['median_bias','R68','tail_0p5']):
            ax.plot(x,[float(r[metric]) for r in selected],'.-',label=label)
    for ax,title in zip(axes,['Median relative bias','R68 of relative residual','Fraction with |relative residual| > 0.5']):
        ax.set(xscale='log',xlabel='True neutrino energy [GeV]',ylabel=title)
        ax.grid(alpha=.2)
    axes[0].axhline(0,color='gray',lw=.8);axes[2].legend(fontsize=8)
    fig.suptitle('Validation development sample; unit weights; N >= 100 per bin')
    save_svg(fig,args.report_dir/'validation_energy_metrics.svg');plt.close(fig)
    with np.load(args.model_dir/'validation_predictions.npz') as d:
        truth=d['truth_E_GeV']
        models=['mu_p_over_0p8','F0_direct','F5_direct']
        fig,axes=plt.subplots(1,3,figsize=(13,4),layout='constrained')
        bins=np.geomspace(100,20000,45)
        for ax,model in zip(axes,models):
            counts,_,_=np.histogram2d(truth,d[model],bins=(bins,bins))
            mesh=ax.pcolormesh(bins,bins,counts.T,norm=LogNorm(vmin=1),cmap='viridis',rasterized=True)
            ax.plot([100,20000],[100,20000],'w--',lw=.7)
            ax.set(xscale='log',yscale='log',xlabel='True energy [GeV]',ylabel='Predicted energy [GeV]',title=model)
            fig.colorbar(mesh,ax=ax,label='Events')
        fig.suptitle('Validation; unit weights; display range 100-20,000 GeV (metrics include all events)')
        save_svg(fig,args.report_dir/'validation_response.svg');plt.close(fig)


if __name__=='__main__':
    main()
