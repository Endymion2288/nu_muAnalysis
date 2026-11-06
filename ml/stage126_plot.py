"""Export scientific figures for the frozen radius-cut scan."""
import csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'workbook/stage126_energy_ml'


def export(fig, stem):
    for ext in ['png','svg','pdf']:
        path=OUT/f'{stem}.{ext}'
        fig.savefig(path,dpi=170)
        if ext=='svg':
            path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')


rows=list(csv.DictReader((OUT/'scan.tsv').open(),delimiter='\t'))
fig,axes=plt.subplots(2,3,figsize=(14,8),layout='constrained')
for selection,color,label in [('pz50','#185fa0','p(z) > 50 GeV'),('pz100','#d25b27','p(z) > 100 GeV (original)')]:
    rr=[r for r in rows if r['role']=='test' and r['selection']==selection]
    x=np.array([float(r['radius_mm']) for r in rr]);show=x<=200
    x=x[show]
    val=lambda k: np.array([float(r[k]) for r in rr])[show]
    for ax,key,scale,title in [(axes[0,0],'record_gain_pct',1,'Selected event gain (%)'),
           (axes[0,1],'log_RMSE_ratio',1,'Log-energy RMSE / baseline'),
           (axes[0,2],'fractional_R68',100,'Fractional R68 (%)'),
           (axes[1,0],'fractional_bias',100,'Mean fractional bias (%)'),
           (axes[1,1],'tail50',100,'Absolute fractional error > 50% (%)'),
           (axes[1,2],'log_bias',1,'Mean log-energy bias')]:
        ax.plot(x,val(key)*scale,'o-',color=color,label=label,markersize=4)
        ax.set(xlabel='Truth vertex radius ceiling (mm)',ylabel=title)
        ax.grid(alpha=.25)
    axes[0,1].fill_between(x,val('log_RMSE_ratio_low95'),val('log_RMSE_ratio_high95'),color=color,alpha=.15)
axes[0,1].axhline(1,color='k',lw=.7)
axes[0,1].axhline(1.03,color='gray',lw=.7,ls=':')
axes[0,0].legend(fontsize=9)
fig.suptitle('Stage87 direct62 frozen ensemble: radius-cut scan on held-out source groups\nIncoming-weighted errors; shaded band: paired incoming conditional 95% interval')
export(fig,'radius_tradeoff')
plt.close(fig)
rr=list(csv.DictReader((OUT/'annuli.tsv').open(),delimiter='\t'))
fig,axes=plt.subplots(1,3,figsize=(13,4),layout='constrained')
for selection,color in [('pz50','#185fa0'),('pz100','#d25b27')]:
    part=[r for r in rr if r['role']=='test' and r['selection']==selection and float(r['upper_mm'])<=200]
    x=np.arange(len(part));labels=[f"{r['lower_mm']}-{r['upper_mm']}" for r in part]
    for ax,key,scale,title in [(axes[0],'N',1,'Number of events'),(axes[1],'log_RMSE',1,'Log-energy RMSE'),(axes[2],'tail50',100,'Fractional-error tail >50% (%)')]:
        ax.plot(x,[float(r[key])*scale for r in part],'o-',color=color,label=selection)
        ax.set(xticks=x,xticklabels=labels,ylabel=title,xlabel='Truth radius annulus (mm)')
        ax.tick_params(axis='x',rotation=65);ax.grid(alpha=.25)
axes[0].legend();fig.suptitle('Incremental annuli, held-out source groups (sparse annuli shown without precision claims)')
export(fig,'annulus_response')
