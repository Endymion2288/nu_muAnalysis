"""Standalone scientific figures from fixed paired scalar tables, batch only."""
import csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def main():
    out=Path('workbook/stage191_energy_ml')
    rows=list(csv.DictReader((out/'ift_paired.tsv').open(),delimiter='\t'))
    fig,axes=plt.subplots(2,2,figsize=(10,7),sharex=True)
    layers=['E50_100','E100_200'];labels=['50–100','100–200']
    for col,role in enumerate([2,3]):
        for panel,refs in enumerate([['X','A','V','S'],['traditional']]):
            ax=axes[panel,col]
            for j,ref in enumerate(refs):
                rr=[next(r for r in rows if int(r['role'])==role and r['stratum']==layer and r['candidate']=='C' and r['reference']==ref) for layer in layers]
                center=np.asarray([float(r['RMSE_ratio']) for r in rr])
                low=np.asarray([float(r['low95']) for r in rr]);high=np.asarray([float(r['high95']) for r in rr])
                xpos=np.arange(2)+(j-(len(refs)-1)/2)*.12
                line,=ax.plot(xpos,center,'o',label=f'C/{ref}')
                ax.vlines(xpos,low,high,color=line.get_color())
            ax.axhline(1,color='black',lw=.8)
            ax.axhline(.95 if panel==0 else 1.05,color='gray',lw=.8,ls='--')
            ax.set_xticks([0,1],labels);ax.grid(alpha=.2);ax.legend(fontsize=9)
            if panel==0:ax.set_title('Calibration' if role==2 else 'Developed test')
            if panel==1:ax.set_xlabel('True neutrino energy [GeV]')
            if col==0:ax.set_ylabel('Log-energy RMSE ratio')
    fig.suptitle('Fixed unused-IFT content: paired conditional 95% intervals')
    fig.tight_layout()
    for suffix in ['svg','pdf']:fig.savefig(out/f'low_energy_comparison.{suffix}')
    plt.close(fig)


if __name__=='__main__':main()
