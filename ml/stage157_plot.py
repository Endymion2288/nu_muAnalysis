"""Batch-render the fixed heldout control and its measured uncertainty."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def run():
    out=Path('workbook/stage157_energy_ml');summary=json.loads((out/'response_summary.json').read_text())
    rows=summary['heldout'];groups=[('all','All selected'),('pz50_100',r'$50\leq p_{z0}<100$ GeV'),
        ('overflow','Any raw15 hardware overflow'),('high_activity','Above fit raw-charge 99th percentile')]
    fig,axes=plt.subplots(2,2,figsize=(9,6.4),sharey=True,constrained_layout=True)
    for ax,(group,title) in zip(axes.flat,groups):
        for x,(policy,label,color) in enumerate([('Q15','Raw15','#386cb0'),('Q15G6','Raw15 + spatial6','#e68124')]):
            row=next((r for r in rows if r['group']==group and r['policy']==policy),None)
            if row is None or not row['scored_N']:
                ax.text(x,6,'unscored',ha='center',fontsize=8);continue
            value=100*row['alert_fraction'];lo=100*row['Wilson95_low'];hi=100*row['Wilson95_high']
            ax.errorbar(x,value,yerr=[[value-lo],[hi-value]],fmt='o',color=color,capsize=4,markersize=6)
            ax.text(x,min(105,hi+3),f"{row['alerts']}/{row['scored_N']}",ha='center',fontsize=9)
            missing=row['original_heldout_N']-row['scored_N']
            ax.text(x,-13,f'{missing} unscored',ha='center',fontsize=8)
        ax.axhline(5,color='0.6',ls='--',lw=.9)
        ax.set_title(title,fontsize=10);ax.set_xticks([0,1],['Raw15','Raw15 + spatial6'])
        ax.set_xlim(-.6,1.6);ax.set_ylim(-18,110);ax.set_yticks([0,20,40,60,80,100]);ax.grid(axis='y',alpha=.2)
    for ax in axes[:,0]:ax.set_ylabel('Heldout false alarms (%)')
    fig.suptitle('Known muon-root control: fixed rules, 95% Wilson intervals\nDashed line: nominal marginal calibration target; one source, no data certification',fontsize=10)
    fig.savefig(out/'heldout_false_alarms.png',dpi=170)
    fig.savefig(out/'heldout_false_alarms.pdf')
    plt.close(fig)
