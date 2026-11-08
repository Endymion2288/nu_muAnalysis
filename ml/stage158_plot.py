"""Render already validated tables with labels contained within the figure."""
import csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

OUT=Path('workbook/stage158_energy_ml')


def main():
    point=list(csv.DictReader((OUT/'metrics.tsv').open(),delimiter='\t'))
    pair=list(csv.DictReader((OUT/'paired.tsv').open(),delimiter='\t'))
    chosen=['E50_100','E100_200','all','pz50_100_trueE200','high_y']
    labels=['50–100 GeV','100–200 GeV','All','Low pz, high E','High y']
    models=['traditional','direct_cal','X62_A3','X62_A3_G6']
    fig,axes=plt.subplots(1,2,figsize=(10,4.2),layout='constrained')
    for name in models:
        values=[float(next(r for r in point if r['role']=='3' and r['stratum']==k and r['model']==name)['log_RMSE']) for k in chosen]
        axes[0].plot(range(5),values,'o-',label=name)
    axes[0].set_ylabel('log-energy RMSE');axes[0].set_yscale('log');axes[0].legend(fontsize=8)
    for role,offset in [(2,-.07),(3,.07)]:
        rows=[next(r for r in pair if r['role']==str(role) and r['stratum']==k and r['candidate']=='X62_A3_G6' and r['reference']=='X62_A3') for k in chosen]
        value=np.array([float(r['RMSE_ratio']) for r in rows])
        low=np.array([float(r['low95']) for r in rows]);high=np.array([float(r['high95']) for r in rows])
        axes[1].errorbar(np.arange(5)+offset,value,yerr=[value-low,high-value],fmt='o',label='cal' if role==2 else 'developed test')
    axes[1].axhline(1,color='gray',lw=1)
    axes[1].set_ylabel('Content / availability RMSE ratio\nConditional 95% interval')
    axes[1].legend(fontsize=8)
    for axis in axes:axis.set_xticks(range(5),labels,rotation=25,ha='right')
    fig.savefig(OUT/'native_energy_comparison.png',dpi=160)
    fig.savefig(OUT/'native_energy_comparison.pdf')
    plt.close(fig)


if __name__=='__main__':main()
