#!/usr/bin/env python3
"""Evaluate frozen stage58 candidates, OOF stability, paired costs and oracle bounds."""
import csv
import json
import numpy as np

from expert_combination import (OUT, ART, REPO, CELLS, LOW, COST, begin, resources,
                                inputs, subset, route, masks, experts, save)


def table(path, records):
    with path.open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(records[0]),delimiter='\t',lineterminator='\n')
        writer.writeheader();writer.writerows(records)


def metrics(y, pred):
    if not len(y):
        return {k:float('nan') for k in ['log_RMSE','mean_bias_pct','median_bias_pct','R68_pct',
                                        'tail50_pct','positive_tail50_pct','negative_tail50_pct',
                                        'tail100_pct','positive_tail100_pct','negative_tail100_pct']}
    err=pred-y;relative=np.expm1(err);q=np.quantile(relative,[.16,.5,.84])
    return dict(log_RMSE=float(np.sqrt(np.mean(err**2))),mean_bias_pct=float(100*relative.mean()),
                median_bias_pct=float(100*q[1]),R68_pct=float(50*(q[2]-q[0])),
                tail50_pct=float(100*np.mean(abs(relative)>.5)),
                positive_tail50_pct=float(100*np.mean(relative>.5)),negative_tail50_pct=float(100*np.mean(relative<-.5)),
                tail100_pct=float(100*np.mean(abs(relative)>1)),
                positive_tail100_pct=float(100*np.mean(relative>1)),negative_tail100_pct=float(100*np.mean(relative<-1)))


def support(d, m):
    return dict(N=int(m.sum()),groups=len(np.unique(d['group'][m])),sources=len(np.unique(d['source'][m])))


def boot_weights(d, seed, repeats):
    groups, gid=np.unique(d['group'],return_inverse=True);rng=np.random.default_rng(seed)
    w=np.zeros((repeats,len(groups)),int)
    for component in ['pi','k','charm']:
        idx=np.flatnonzero(np.char.startswith(groups,component+':'))
        if len(idx):w[:,idx]=rng.multinomial(len(idx),np.full(len(idx),1/len(idx)),size=repeats)
    return groups,gid,w


def main():
    start=begin();protocol=json.loads((OUT/'protocol.json').read_text());models=json.loads((OUT/'models.json').read_text())
    d=inputs()
    with np.load(ART/'predictions.npz') as z:arr={k:z[k] for k in z.files}
    records=[];paired=[];fold_records=[];source_records=[];cell_records=[];diagnostics=[];oracle_records=[]
    for role in ['train','cal','eval']:
        dd=subset(d,d['role']==role);cell=route(dd['pz'],dd['timing'],protocol['timing_medians_pC']);mm=masks(dd)
        for c in range(-1,4):
            for energy,m in [('all',mm['all']),('E50_100',mm['E50_100']),('E100_200',mm['E100_200']),
                             ('E200_inf',mm['E200_inf']),('high_y',mm['high_y']),('unconfirmed',mm['unconfirmed'])]:
                use=(cell==c)&m
                def median(key):
                    v=dd[key][use];v=v[np.isfinite(v)]
                    return float(np.median(v)) if len(v) else float('nan')
                diagnostics.append(dict(role=role,cell='default_F7' if c<0 else CELLS[c],stratum=energy,
                    **support(dd,use),confirmed_N=int(dd['confirmed'][use].sum()),high_y_N=int((dd['y_lepton'][use]>=.8).sum()),
                    missing_N=int(dd['missing'][use].sum()),median_y=median('y_lepton'),median_Timing_pC=median('timing'),
                    median_clusters=median('clusters'),median_calo_EM_GeV=median('calo')))
        if role=='train':continue
        sample='cal_OOF' if role=='cal' else 'evaluation';y=np.log(dd['truth_E_GeV'])
        logs=dict(pz0=np.log(dd['pz']),pz0_over0p8=np.log(dd['pz']/.8),F7=arr['cal_oof_F7'] if role=='cal' else arr['eval_F7'],
                  two=arr['cal_oof_two'] if role=='cal' else arr['eval_two'],three=arr['cal_oof_three'] if role=='cal' else arr['eval_three'])
        # Truth projection is diagnostic only: cannot be deployed or selected as a candidate.
        for name,columns in [('oracle_two',[1,2]),('oracle_three',[0,1,2])]:
            t=np.column_stack([logs['pz0'],logs['pz0_over0p8'],logs['F7']])[:,columns]
            ideal=np.clip(y,t.min(axis=1),t.max(axis=1))
            for stratum,m in mm.items():
                oracle_records.append(dict(sample=sample,stratum=stratum,diagnostic=name,**support(dd,m),**metrics(y[m],ideal[m])))
            if role=='eval':logs[name]=ideal
        groups,gid,w=boot_weights(dd,protocol['bootstrap_seed']+(0 if role=='eval' else 1),protocol['bootstrap_replicates'])
        for stratum,m in mm.items():
            for name,pred in logs.items():
                if not name.startswith('oracle'):records.append(dict(sample=sample,stratum=stratum,model=name,**support(dd,m),**metrics(y[m],pred[m])))
            ng=len(np.unique(dd['group'][m]));n=int(m.sum())
            comparisons=[(name,ref) for name in ['two','three','pz0'] for ref in ['pz0_over0p8','F7']]+[('three','two')]
            if role=='eval':comparisons += [(name,'pz0_over0p8') for name in ['oracle_two','oracle_three']]
            for name,ref in comparisons:
                if n==0:continue
                point=metrics(y[m],logs[name][m]);reference=metrics(y[m],logs[ref][m]);ratio=point['log_RMSE']/reference['log_RMSE']
                row=dict(sample=sample,stratum=stratum,model=name,reference=ref,**support(dd,m),RMSE_ratio=ratio,gain_pct=100*(1-ratio),
                         RMSE_ratio_low95=float('nan'),RMSE_ratio_high95=float('nan'),gain_low95_pct=float('nan'),gain_high95_pct=float('nan'),bootstrap_valid=0)
                if ng>=3:
                    sums=[]
                    for pred in [logs[name],logs[ref]]:
                        sums.append(w@np.bincount(gid[m],weights=(pred[m]-y[m])**2,minlength=len(groups)))
                    den=w@np.bincount(gid[m],minlength=len(groups));good=(den>0)&(sums[1]>0)
                    rr=np.sqrt(sums[0][good]/sums[1][good]);lo,hi=np.quantile(rr,[.025,.975])
                    row.update(RMSE_ratio_low95=float(lo),RMSE_ratio_high95=float(hi),gain_low95_pct=float(100*(1-hi)),gain_high95_pct=float(100*(1-lo)),bootstrap_valid=int(good.sum()))
                for tail in ['tail50_pct','positive_tail50_pct','negative_tail50_pct','tail100_pct','positive_tail100_pct','negative_tail100_pct']:
                    delta=point[tail]-reference[tail];row[tail+'_delta_pp']=delta
                    row[tail+'_delta_low95_pp']=float('nan');row[tail+'_delta_high95_pp']=float('nan')
                    if ng>=3:
                        threshold=.5 if '50' in tail else 1.
                        def indicator(pred):
                            r=np.expm1(pred[m]-y[m])
                            return r>threshold if tail.startswith('positive') else r< -threshold if tail.startswith('negative') else abs(r)>threshold
                        diff=indicator(logs[name]).astype(float)-indicator(logs[ref]).astype(float)
                        vals=100*(w@np.bincount(gid[m],weights=diff,minlength=len(groups)))[good]/den[good]
                        lo,hi=np.quantile(vals,[.025,.975]);row[tail+'_delta_low95_pp']=float(lo);row[tail+'_delta_high95_pp']=float(hi)
                paired.append(row)
        for fold in (range(3) if role=='cal' else []):
            for stratum in ['all']+LOW+list(COST)[1:]:
                m=mm[stratum]&(arr['cal_fold']==fold)
                for name,pred in logs.items():fold_records.append(dict(fold=fold,stratum=stratum,model=name,**support(dd,m),**metrics(y[m],pred[m])))
        for group in groups:
            for stratum in ['all']+LOW+list(COST)[1:]:
                m=mm[stratum]&(dd['group']==group)
                for name in ['pz0','pz0_over0p8','F7','two','three']:
                    source_records.append(dict(sample=sample,group=group,stratum=stratum,model=name,**support(dd,m),**metrics(y[m],logs[name][m])))
        for c in range(-1,4):
            for stratum in ['all']+LOW+list(COST)[1:]:
                m=(cell==c)&mm[stratum]
                for name in ['pz0','pz0_over0p8','F7','two','three']:
                    cell_records.append(dict(sample=sample,cell='default_F7' if c<0 else CELLS[c],stratum=stratum,model=name,**support(dd,m),**metrics(y[m],logs[name][m])))
    table(OUT/'metrics.tsv',records);table(OUT/'paired.tsv',paired);table(OUT/'cal_oof_folds.tsv',fold_records)
    table(OUT/'source_metrics.tsv',source_records);table(OUT/'cell_metrics.tsv',cell_records)
    table(OUT/'cell_composition.tsv',diagnostics);table(OUT/'oracle_diagnostic.tsv',oracle_records)
    acceptance=[]
    for family in ['two','three']:
        for stratum,limit,reference,criterion in [(s,1.05,'pz0_over0p8','recovery') for s in LOW]+[(s,v,'F7','cost') for s,v in COST.items()]:
            r=next(r for r in paired if r['sample']=='evaluation' and r['stratum']==stratum and r['model']==family and r['reference']==reference)
            acceptance.append(dict(model=family,criterion=criterion,stratum=stratum,reference=reference,limit=limit,
                                   point_ratio=r['RMSE_ratio'],upper95_ratio=r['RMSE_ratio_high95'],
                                   point_pass=bool(r['RMSE_ratio']<=limit),interval_pass=bool(r['RMSE_ratio_high95']<=limit),
                                   breakthrough_low95_gain_pct=r['gain_low95_pct'] if criterion=='recovery' else None,
                                   tail50_delta_pp=r['tail50_pct_delta_pp'],tail50_delta_upper95_pp=r['tail50_pct_delta_high95_pp'],
                                   tail50_point_pass=bool(r['tail50_pct_delta_pp']<=2),tail50_interval_pass=bool(r['tail50_pct_delta_high95_pp']<=2)))
    save(OUT/'acceptance.json',acceptance)
    # Standalone scientific figures; no extra model fitting.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    for name,label in [('pz0','pz0'),('pz0_over0p8','pz0 / 0.8'),('F7','F7'),('two','Two experts'),('three','Three experts')]:
        edges=[50,75,100,150,200,400,800,1600,3200,6400]
        rr=[next(r for r in records if r['sample']=='evaluation' and r['model']==name and r['stratum']==f'E{lo}_{hi}') for lo,hi in zip(edges[:-1],edges[1:])]
        for ax,key in zip(axes,['log_RMSE','mean_bias_pct']):ax.plot(np.sqrt(np.array(edges[:-1])*edges[1:]),[r[key] for r in rr],'o-',label=label,ms=3)
    for ax in axes:ax.set_xscale('log');ax.set_xlabel('True neutrino energy [GeV]');ax.grid(alpha=.2);ax.axvspan(50,100,color='grey',alpha=.1)
    axes[0].set_ylabel('log-RMSE');axes[1].set_ylabel('Mean relative bias [%]');axes[0].legend(fontsize=8);axes[1].axhline(0,color='black',lw=.6)
    fig.suptitle('Frozen four-cell combinations: nominal development evaluation\nUnit MC; 8 cal optimizations, no new energy-model fit')
    def figure(fig,name):
        path=OUT/(name+'.svg');fig.savefig(path);fig.savefig(OUT/(name+'.png'),dpi=140);plt.close(fig)
        path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
    figure(fig,'expert_response')
    fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    for ax,strata,ref in [(axes[0],LOW,'pz0_over0p8'),(axes[1],list(COST),'F7')]:
        for shift,family in [(-.07,'two'),(.07,'three')]:
            rr=[next(r for r in paired if r['sample']=='evaluation' and r['stratum']==s and r['model']==family and r['reference']==ref) for s in strata]
            centers=np.array([r['RMSE_ratio'] for r in rr]);lo=np.array([r['RMSE_ratio_low95'] for r in rr]);hi=np.array([r['RMSE_ratio_high95'] for r in rr])
            ax.errorbar(np.arange(len(strata))+shift,centers,yerr=[centers-lo,hi-centers],fmt='o',label=family,capsize=3)
        ax.set_xticks(range(len(strata)),strata,rotation=20);ax.set_ylabel('log-RMSE ratio to '+ref);ax.grid(alpha=.2)
    axes[0].axhline(1.05,color='red',ls='--',label='recovery limit');axes[0].legend(fontsize=8)
    axes[1].plot(range(len(COST)),list(COST.values()),'r_',ms=14,label='cost limit');axes[1].legend(fontsize=8)
    fig.suptitle('Source-paired 95% intervals, conditional on frozen combinations\nNo refitting, calibration, detector or research-selection uncertainty included')
    figure(fig,'expert_tradeoff')
    save(OUT/'report_resources.json',dict(**resources(start),bootstrap_replicates=500,
         interval_scope='component-stratified source paired, fixed final/OOF predictions; no refits, no energy/calibration/detector/flux/research-selection uncertainty',
         generated_tables=7))
    print(json.dumps(acceptance,indent=2))


if __name__=='__main__':main()
