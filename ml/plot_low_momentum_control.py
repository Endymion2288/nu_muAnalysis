#!/usr/bin/env python3
"""Contrast low-momentum mu precision with the remaining neutrino energy gap."""
import argparse,csv
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main():
    p=argparse.ArgumentParser();p.add_argument('--png-preview',type=Path);args=p.parse_args()
    out=Path(__file__).resolve().parents[1]/'workbook/stage33_energy_ml'
    rows=list(csv.DictReader((out/'cached_validation_metrics.tsv').open(),delimiter='\t'))
    def find(model,stratum,value,metric):
        return next(r for r in rows if r['model']==model and r['stratum']==stratum and r['value']==value and r['metric']==metric)
    plt.rcParams.update({'svg.fonttype':'none','font.size':10})
    fig,axes=plt.subplots(1,3,figsize=(14,4.4),layout='constrained')
    regions=['100_175','175_250','250_1000','1000_inf'];models=[('mu_reco','Raw mu vs production p','tab:blue'),('nu_F5','Neutrino F5','tab:orange'),('nu_F6','Neutrino F6','tab:green')]
    for j,(model,label,color) in enumerate(models):
        rs=[find(model,'primary_p_confirmed',v,'R68') for v in regions]
        yy=np.array([float(r['point']) for r in rs])*100
        ci=np.array([[float(r['CI025']),float(r['CI975'])] for r in rs]).T*100
        axes[0].errorbar(np.arange(4)+(j-1)*.13,yy,yerr=[yy-ci[0],ci[1]-yy],marker='o',ls='none',color=color,label=label,capsize=3)
    axes[0].set(xticks=np.arange(4),xticklabels=['100–175','175–250','250–1000','≥1000'],xlabel='Primary production p [GeV]',ylabel='Relative-error R68 [%]',title='Same confirmed validation events')
    axes[0].legend(fontsize=8)
    ys=['0_0.2','0.2_0.6','0.6_0.8','0.8_1']
    for model,label,color in models:
        rs=[find(model,'focus_y_confirmed',v,'log_RMSE') for v in ys]
        yy=np.array([float(r['point']) for r in rs]);ci=np.array([[float(r['CI025']),float(r['CI975'])] for r in rs]).T
        axes[1].errorbar(np.arange(4),yy,yerr=[yy-ci[0],ci[1]-yy],marker='o',color=color,label=label,capsize=3)
    axes[1].set(xticks=np.arange(4),xticklabels=['0–0.2','0.2–0.6','0.6–0.8','0.8–1'],xlabel='Leptonic y (truth diagnostic)',ylabel='log-RMSE',title='Primary p = 100–250 GeV')
    native=list(csv.DictReader((out/'reference_events.tsv').open(),delimiter='\t'))
    low=[r for r in native if r['confirmed']=='True' and r['bound_available']=='True' and 100<=float(r['primary_p_GeV'])<250]
    for r in low:
        x=float(r['primary_p_GeV']);ll=float(r['relative_momentum_residual_low'])*100;hh=float(r['relative_momentum_residual_high'])*100
        axes[2].plot([x,x],[ll,hh],color='tab:blue',lw=1.5)
        axes[2].scatter(x,(float(r['reco_p_GeV'])/x-1)*100,color='tab:orange',s=12)
    axes[2].plot([],[],color='tab:blue',label='Same-plane response bounds')
    axes[2].scatter([],[],color='tab:orange',s=12,label='Response vs production p')
    axes[2].axhline(0,color='.6',lw=.8)
    axes[2].set(xlabel='Primary production p [GeV]',ylabel='Relative mu momentum error [%]',title=f'{len(low)} bounded confirmed low-p cases')
    axes[2].legend(fontsize=8)
    path=out/'low_momentum_diagnostics.svg';fig.savefig(path)
    path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
    if args.png_preview:fig.savefig(args.png_preview,dpi=130)
    plt.close(fig)

if __name__=='__main__':main()
