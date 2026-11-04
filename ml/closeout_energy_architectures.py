"""Stage94 saved-table closeout and scientific figures, no fit/inference."""
import csv
import json
from pathlib import Path

import numpy as np

from support_augmentation import save,table,begin,resources
from audited_features import REPO

OUT=REPO/'workbook/stage94_energy_ml'
SEED=2026110494


def read(name):return list(csv.DictReader((OUT/(name+'.tsv')).open(),delimiter='\t'))


def main():
    start=begin();assert json.loads((OUT/'report_complete.json').read_text())['passed']
    metrics=read('metrics');paired=read('paired');gates=read('gates');select=[]
    layers=['E50_100','E100_200','all','E200_inf','pz50_100','pz50_100_trueE200','high_y','unconfirmed','E3200_6400','input_missing']
    for r in metrics:
        if r['weighting']=='incoming' and r['stratum'] in layers:select.append(r)
        for k in ['log_RMSE','median_bias_pct','mean_bias_pct','R68_pct','tail50_pct','positive_tail50_pct','negative_tail50_pct']:assert np.isfinite(float(r[k])),(k,r)
    for r in paired:
        assert r['valid_draws']!='0'
        for k in ['RMSE_ratio','conditional_low95','conditional_high95','total_tail_delta_pp','positive_tail_delta_pp','negative_tail_delta_pp']:assert np.isfinite(float(r[k]))
    table(OUT/'selected_metrics.tsv',select)
    learning=[]
    for path in sorted(OUT.glob('fit_*.json')):
        f=json.loads(path.read_text());history=read(f"learning_{f['cell']}_{f['seed']}")
        epoch=min(history,key=lambda r:float(r['cal_select_point_MSE']))['epoch'];assert int(epoch)==f['best_epoch']
        assert len(history)*5==f['epochs'] and f['epochs']<=300 and f['optimizer_steps']==f['epochs']*46
        learning.append(f)
    assert len(learning)==9 and len({(r['cell'],r['seed']) for r in learning})==9
    table(OUT/'fit_summary.tsv',learning)
    selection=json.loads((OUT/'selection.json').read_text());order=sorted(selection['ranking'],key=lambda r:(r['worst_normalized_ratio'],r['mean_normalized_ratio'],r['all_MSE'],r['cell']))
    assert [r['cell'] for r in order[:2]]==selection['selected_for_two_extra_seeds']==['E','B']
    assert selection['new_test_forward_before_selection']==0
    for code,n in [(1,46575),(2,11612),(3,13189)]:assert json.loads((OUT/'report_complete.json').read_text())['roles'][str(code)]==n
    plot(metrics,paired)
    save(OUT/'closeout_validation.json',dict(passed=True,new_integrations=0,new_fits=0,unique_fits=9,epochs_and_best_checkpoint_checked=True,all_table_metrics_finite=True,selection_rule_reproduced=True,metrics_rows=len(metrics),paired_rows=len(paired),gate_rows=len(gates),source95=False,model_promotion=False,**resources(start)))


def plot(metrics,paired):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(1,3,figsize=(15,4.4),layout='constrained')
    layers=['E50_100','E100_200','all','pz50_100_trueE200','high_y','unconfirmed']
    labels=['50–100 GeV','100–200 GeV','all','low pz, E≥200','high-y','unconfirmed'];x=np.arange(len(layers))
    policies=[('traditional','Traditional'),('direct_cal','Direct BDT'),('posterior92','Posterior92')]+[(f'{c}_{SEED}_cal',c) for c in 'ABCDE']+[('B_ensemble_cal','B ensemble'),('E_ensemble_cal','E ensemble')]
    for name,label in policies:
        vals=[float(next(r for r in metrics if r['role']=='test' and r['stratum']==s and r['weighting']=='incoming' and r['policy']==name)['log_RMSE']) for s in layers]
        refs=[float(next(r for r in metrics if r['role']=='test' and r['stratum']==s and r['weighting']=='incoming' and r['policy']==('traditional' if j<2 else 'direct_cal'))['log_RMSE']) for j,s in enumerate(layers)]
        if name=='traditional':continue
        ax[0].plot(x,np.array(vals)/refs,'o-',label=label,ms=3,alpha=.8)
    ax[0].axhline(1,color='grey',ls='--');ax[0].set(xticks=x,xticklabels=labels,ylabel='Log-RMSE / fixed reference',title='Low E: traditional; others: original direct BDT')
    contrasts=[('B','A'),('C','B'),('D','C'),('E','C')]
    for j,(a,b) in enumerate(contrasts):
        rr=[next(r for r in paired if r['role']=='test' and r['stratum']==s and r['candidate']==f'{a}_{SEED}_cal' and r['reference']==f'{b}_{SEED}_cal') for s in layers]
        yy=np.array([float(r['RMSE_ratio']) for r in rr]);lo=np.array([float(r['conditional_low95']) for r in rr]);hi=np.array([float(r['conditional_high95']) for r in rr])
        xx=x+(j-1.5)*.12;ax[1].errorbar(xx,yy,yerr=np.maximum(0,np.vstack([yy-lo,hi-yy])),fmt='o',capsize=2,label=a+'/'+b,ms=3)
    ax[1].axhline(1,color='grey',ls='--');ax[1].set(xticks=x,xticklabels=labels,ylabel='Paired log-RMSE ratio',title='500 incoming draws: conditional 95% intervals')
    for cell in 'ABCDE':
        rr=read(f'learning_{cell}_{SEED}');ax[2].plot([int(r['epoch']) for r in rr],[float(r['cal_select_point_MSE'])**.5 for r in rr],label=cell)
    ax[2].set(xlabel='Epoch',ylabel='cal_select log-RMSE',title='Checkpoint selection uses cal_select only')
    for a in ax:a.grid(axis='y',alpha=.15);a.legend(fontsize=7)
    for a in ax[:2]:a.tick_params(axis='x',rotation=35)
    fig.suptitle('Stage94: input / representation / architecture / energy-output comparison; developed test',fontsize=12)
    path=OUT/'architecture_comparison.svg';fig.savefig(path);path.write_text('\n'.join(l.rstrip() for l in path.read_text().splitlines())+'\n');fig.savefig('/tmp/stage94_comparison.png',dpi=140);plt.close(fig)
    fig,aa=plt.subplots(1,2,figsize=(10,4),layout='constrained')
    for cell in ['B','E']:
        for seed in [SEED,SEED+1,SEED+2]:
            rr=read(f'learning_{cell}_{seed}');a=aa[0 if cell=='B' else 1]
            if cell=='B':a.plot([int(r['epoch']) for r in rr],[float(r['train_objective'])**.5 for r in rr],label=f'{seed} train')
            else:a.plot([int(r['epoch']) for r in rr],[float(r['train_objective']) for r in rr],label=f'{seed} train NLL')
        a.set(xlabel='Epoch',ylabel='Train RMSE' if cell=='B' else 'Train NLL',title=cell);a.legend(fontsize=7);a.grid(alpha=.15)
    path=OUT/'seed_learning.svg';fig.savefig(path);path.write_text('\n'.join(l.rstrip() for l in path.read_text().splitlines())+'\n');plt.close(fig)


if __name__=='__main__':main()
