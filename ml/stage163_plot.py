"""Render existing validated TSV values only; no event inputs, fits or statistics."""
import csv
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT=Path(__file__).resolve().parents[1]/'workbook/stage163_energy_ml'


def main():
    point=list(csv.DictReader((OUT/'metrics.tsv').open(),delimiter='\t'))
    pairs=list(csv.DictReader((OUT/'paired.tsv').open(),delimiter='\t'))
    chosen=['E50_100','E100_200','all','pz50_100_trueE200','high_y']
    labels=['50–100 GeV','100–200 GeV','All','Low pz, high E','High y']
    fig,axes=plt.subplots(1,2,figsize=(10,3.7),constrained_layout=True)
    for model in ['traditional','direct_cal','X62_M12','X62_M12_Q4']:
        values=[float(next(r for r in point if r['role']=='3' and r['stratum']==s and r['model']==model)['log_RMSE']) for s in chosen]
        axes[0].plot(range(5),values,'o-',label=model)
    axes[0].set_xticks(range(5));axes[0].set_xticklabels(labels,rotation=25,ha='right')
    axes[0].set_ylabel('log-energy RMSE');axes[0].set_yscale('log');axes[0].legend(fontsize=8)
    for role,offset in [('2',-.07),('3',.07)]:
        rows=[next(r for r in pairs if r['role']==role and r['stratum']==s and r['candidate']=='X62_M12_Q4' and r['reference']=='X62_M12') for s in chosen]
        values=[float(r['RMSE_ratio']) for r in rows]
        errors=[[v-float(r['low95']) for v,r in zip(values,rows)],
                [float(r['high95'])-v for v,r in zip(values,rows)]]
        axes[1].errorbar([i+offset for i in range(5)],values,yerr=errors,fmt='o',label='cal' if role=='2' else 'developed test')
    axes[1].axhline(1,color='gray',lw=1);axes[1].set_xticks(range(5));axes[1].set_xticklabels(labels,rotation=25,ha='right')
    axes[1].set_ylabel('Calo raw / status control RMSE ratio\nConditional 95% CI');axes[1].legend(fontsize=8)
    fig.savefig(OUT/'calo_raw_energy_comparison.png',dpi=160);plt.close(fig)


if __name__=='__main__':main()
