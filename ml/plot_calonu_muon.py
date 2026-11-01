#!/usr/bin/env python3
"""Standalone response-control figures, including unverified positional associations."""
import csv
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def table(root, name):
    return list(csv.DictReader((root/name).open(), delimiter='\t'))


def main():
    out = Path(__file__).resolve().parents[1]/'workbook/stage36_energy_ml'
    totals, noise, metrics, assoc = [table(out, k) for k in ['total_response.tsv', 'noise_aggregate.tsv', 'response_metrics.tsv', 'module_association_posthoc.tsv']]
    fig, axes = plt.subplots(2, 3, figsize=(13, 7.5), constrained_layout=True)
    colors = {'MC':'#0072B2','data':'#D55E00'}
    for j, sample in enumerate(['MC','data']):
        r = next(r for r in noise if r['sample']==sample and r['subset']=='all' and r['observable']=='all_four_threshold_failed_fraction')
        y, lo, hi = [100*float(r[k]) for k in ['mean','mean_lo','mean_hi']]
        axes[0,0].plot(j,y,'o',color=colors[sample]);axes[0,0].vlines(j,lo,hi,color=colors[sample])
        for k, obs in enumerate(['total_E_EM','noise_expected_total']):
            source = totals if k==0 else noise
            r = next(r for r in source if r['sample']==sample and r['subset']=='all' and r['observable']==obs)
            x = j+(k-.5)*.15
            y, lo, hi = [float(r[key]) for key in ['median','median_lo','median_hi']]
            axes[0,1].plot(x,y,['o','s'][k],color=colors[sample],label=obs if j==0 else None)
            axes[0,1].vlines(x,lo,hi,color=colors[sample])
        r = next(r for r in noise if r['sample']==sample and r['subset']=='all_four_threshold_failed' and r['observable']=='total_over_noise_expected')
        y, lo, hi = [float(r[key]) for key in ['median','median_lo','median_hi']]
        axes[0,2].plot(j,y,'o',color=colors[sample]);axes[0,2].vlines(j,lo,hi,color=colors[sample])
    for ax in axes[0]:
        ax.set_xticks([0,1],['Muon MC','Muon candidates in data']);ax.grid(alpha=.15)
    axes[0,0].set(ylabel='All four channels below peak threshold [%]',ylim=(0,100))
    axes[0,1].set(ylabel='Median total [GeV EM scale]',yscale='log');axes[0,1].legend(fontsize=7)
    axes[0,2].axhline(1,color='gray',lw=.7);axes[0,2].set(ylabel='Observed / rectified-noise expectation\nMedian, all four below threshold')
    for j,sample in enumerate(['MC','data']):
        selected = [next(r for r in metrics if r['sample']==sample and r['subset']=='all' and r['role']=='all' and int(r['module'])==i and r['observable']=='effective_charge_per_MIP') for i in range(4)]
        axes[1,0].plot(range(4),[float(r['median']) for r in selected],'o-',label=sample,color=colors[sample])
        a = np.array([[float(next(r for r in assoc if r['sample']==sample and int(r['nominal_region'])==i and int(r['readout_module'])==k)['median']) for k in range(4)] for i in range(4)])
        ax = axes[1,j+1]
        im = ax.imshow(a,cmap='viridis')
        for (i,k),v in np.ndenumerate(a):ax.text(k,i,f'{v:.3f}',ha='center',va='center',color='white' if v<a.mean() else 'black',fontsize=8)
        ax.set(xticks=range(4),yticks=range(4),xlabel='CaloNu readout index',ylabel='Nominal spatial region',title=sample+': median raw charge [pC]')
        fig.colorbar(im,ax=ax,shrink=.8)
    axes[1,0].set(xticks=range(4),xlabel='CaloNu readout index',ylabel='Effective charge per nMIP [pC/MIP]',yscale='log');axes[1,0].legend();axes[1,0].grid(alpha=.15)
    fig.suptitle('CaloNu muon response control: 262,236 MC + 248,323 data candidates\n95% block intervals; EM scale is not deposited energy; hardware mapping / alignment unverified')
    path=out/'muon_response.svg';fig.savefig(path)
    path.write_text('\n'.join(s.rstrip() for s in path.read_text().splitlines())+'\n')
    fig.savefig('/tmp/stage36_muon_response.png',dpi=140)
    plt.close(fig)


if __name__=='__main__':
    main()
