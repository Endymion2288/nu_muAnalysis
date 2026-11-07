"""Standalone review figures from compact Stage129 tables."""
import csv

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from stage129_energy import OUT


def read(name):return list(csv.DictReader((OUT/name).open(),delimiter='\t'))


def main():
    fig,axs=plt.subplots(1,3,figsize=(13,4.5),sharey=True)
    arms=[('depth','Z','Truth depth oracle'),('trackmaterial','G','IFT geometry'),('timing','T','Strict calibrated time'),('saturation','Q','Recovered charge')]
    for ax,layer in zip(axs,['E50_100','E100_200','all']):
        for i,(experiment,arm,label) in enumerate(arms):
            r=next(r for r in read(experiment+'_paired.tsv') if r['role']=='3' and r['stratum']==layer and r['candidate']==arm and r['reference']=='X')
            x,lo,hi=[float(r[k]) for k in ['RMSE_ratio','low95','high95']]
            ax.errorbar(x,i,xerr=[[x-lo],[hi-x]],fmt='o',capsize=3,color='C'+str(i))
        ax.axvline(1,color='k',ls='--',lw=1);ax.set(title=layer,xlabel='log-energy RMSE / direct62');ax.grid(axis='x',alpha=.2)
    axs[0].set_yticks(range(4),[a[2] for a in arms]);axs[0].invert_yaxis()
    fig.suptitle('Same original support and fixed learning policy · development test\n95% intervals conditional on incoming groups; truth oracle is not deployable',fontsize=11)
    fig.tight_layout();fig.savefig(OUT/'observable_energy_comparison.svg');plt.close(fig)
    rows=read('chargecov_comparison.tsv');fig,axs=plt.subplots(1,3,figsize=(12,4))
    for ax,ch,label in zip(axs,['14','6','7'],['Veto10','Veto20','Veto21']):
        for method in ['clipped_raw','official_CB','constrained']:
            rr=[r for r in rows if r['role']=='3' and r['channel']==ch and r['shape']=='all' and r['subset']=='common_available' and r['method']==method];rr.sort(key=lambda r:float(r['fraction']))
            ax.plot([float(r['fraction']) for r in rr],[100*float(r['relative_RMSE']) for r in rr],'o-',label=method)
        ax.set(title=label,xlabel='Artificial rail / original peak',ylabel='Relative charge RMSE (%)');ax.grid(alpha=.2)
    axs[-1].legend(fontsize=8);fig.suptitle('Source-held uncut controls · same available denominator\nDigital truncation test; not validation of PMT nonlinearity',fontsize=11)
    fig.tight_layout();fig.savefig(OUT/'charge_recovery_validation.svg');plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,4.5))
    for i,(experiment,arm,label) in enumerate(arms):
        rr=[r for r in read(experiment+'_paired.tsv') if r['role']=='3' and r['candidate']==arm and r['reference']=='direct_cal' and r['stratum'] in ['E50_100','E100_200','all','lowpz50_100_highE','high_y']]
        if not rr:continue
        values=[max(float(r[s+'_tail_high95_pp']) for s in ['total','positive','negative']) for r in rr]
        ax.plot(range(len(rr)),values,'o-',label=label)
    ax.axhline(2,color='k',ls='--',label='Original +2 pp limit');ax.set_xticks(range(len(rr)),[r['stratum'] for r in rr],rotation=15,ha='right');ax.set_ylabel('Maximum upper95 tail-rate change (pp)');ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.tight_layout();fig.savefig(OUT/'tail_risk_comparison.svg');plt.close(fig)

    # Matplotlib SVG path formatting includes trailing blanks; normalize text only.
    for path in OUT.glob('*.svg'):
        path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines()).rstrip()+'\n')


if __name__=='__main__':main()
