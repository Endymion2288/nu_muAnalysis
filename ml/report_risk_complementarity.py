#!/usr/bin/env python3
"""Frozen outer OOF, original cal offsets and full source-paired risk assessment."""
import csv
import gzip
from group_risk import inputs
from risk_complementarity import *


def data():
    if (CACHE/'input.npz').exists():return arrays(CACHE/'input.npz')
    d=inputs();tr=d['role']=='train';a=arrays(REPO/'ml/artifacts/stage73/oof_predictions.npz')
    np.testing.assert_array_equal(a['row'],d['row'][tr]);d['old_oof_h']=np.full((len(tr),3),np.nan)
    d['old_oof_h'][tr]=np.c_[a['U_raw_log'],a['F_raw_log'],np.log(d['pz'][tr]/.8)]
    a=arrays(REPO/'ml/artifacts/stage73/final/predictions.npz');d['old_final_h']=np.full((len(tr),3),np.nan)
    for role in ['train','cal','eval']:
        m=d['role']==role;np.testing.assert_array_equal(a[role+'_row'],d['row'][m])
        d['old_final_h'][m]=np.c_[a[role+'_U_raw_log'],a[role+'_F_raw_log'],np.log(d['pz'][m]/.8)]
    return d


def references(role,row,oof):
    result={};prefix='' if oof else role+'_'
    a=arrays(REPO/'ml/artifacts/stage73'/('oof_predictions.npz' if oof else 'final/predictions.npz'))
    np.testing.assert_array_equal(a[prefix+'row'],row)
    cal=json.loads((REPO/'workbook/stage73_energy_ml/calibration.json').read_text())['offset_log']
    for n in ['U','S','F']:
        result['stage73_'+n+'_raw']=a[prefix+n+'_raw_log']
        if role!='train':result['stage73_'+n+'_cal']=result['stage73_'+n+'_raw']+cal[n]
    a=arrays(REPO/'ml/artifacts/stage76'/('oof_predictions.npz' if oof else 'final/predictions.npz'))
    np.testing.assert_array_equal(a[prefix+'row'],row);result['stage76_X_raw']=a[prefix+'X_raw_log']
    if role!='train':
        result['stage76_X_cal']=result['stage76_X_raw']+json.loads((REPO/'workbook/stage76_energy_ml/calibration.json').read_text())['offset_log']['X']
        a=arrays(REPO/'ml/artifacts/stage56/predictions.npz');np.testing.assert_array_equal(a[role+'_row'],row)
        result['F7']=a[role+'_raw_log'].mean(0)+json.loads(str(a['metadata_json']))['offset_log']
    return result


def logs_for(sample,role,d,oof,final,offsets):
    a=oof if sample=='source_OOF_raw' else final;prefix='' if sample=='source_OOF_raw' else role+'_'
    logs={'mu':np.log(d['pz']/.8)}
    for arm in ARMS:
        logs[arm+'_raw']=a[prefix+arm+'_raw_log']
        if role!='train':logs[arm+'_cal']=logs[arm+'_raw']+offsets[arm]
    logs.update(references(role,d['row'],sample=='source_OOF_raw'))
    return logs



def write_interpretation(sources):
    rows=[]
    for key in LOW+list(COST)+['E3200_6400','pz50_100_E200_inf']:
        by={}
        for r in sources:
            if r['sample']=='evaluation' and r['stratum']==key:
                by.setdefault(str(r['group']),{})[r['model']]=float(r['log_RMSE'])
        rows.append(dict(stratum=key,groups=len(by),Q_local_cal_better_than_F7_N=sum(v['Q_local_cal']<v['F7'] for v in by.values()),
            Q_local_raw_better_than_Q0_raw_N=sum(v['Q_local_raw']<v['Q0_raw'] for v in by.values())))
    save(OUT/'interpretation.json',dict(source_central_directions=rows,not_per_source_significance=True,no_events_removed=True))


def main():
    start=begin();p=json.loads((OUT/'protocol.json').read_text());d=data();tr=d['role']=='train';trainrow=d['row'][tr]
    seen=np.zeros(len(trainrow),int);oof={'row':trainrow,**{n+'_raw_log':np.full(len(trainrow),np.nan) for n in ARMS}}
    verification=[];fold_rows=[];training_rows=[];leaf_rows=[]
    for job in JOBS:
        outer,held,purge=training_split(d,p,job);a=arrays(ART/job/'predictions.npz');head=json.loads((ART/job/'head.json').read_text())
        ht=arrays(ART/job/'head_training.npz');np.testing.assert_array_equal(ht['row'],d['row'][outer])
        dd=subset(d,outer);y=np.log(dd['truth_E_GeV']);np.testing.assert_array_equal(a['head_train_row'],ht['row'])
        for arm in ARMS:
            pred=predict_head(dd['x'],ht['h'],head,arm);np.testing.assert_array_equal(pred,a['head_train_'+arm+'_raw_log'])
            sol=head['solutions'][arm];assert sol['solved'] and sol['secondary_solved'] and sol['solver_calls']==2
            for key,m in diagnostic_masks(dd).items():
                training_rows.append(dict(job=job,model=arm,stratum=key,**support(dd,m),**metrics(y[m],pred[m])))
        leaf=route(dd['x'],head['partition'])
        for l in range(len(head['partition']['leaf_ids'])):
            for key,m in diagnostic_masks(dd).items():
                mm=m&(leaf==l)
                row=dict(job=job,leaf=l,stratum=key,**support(dd,mm))
                for j,n in enumerate(['U','F','mu']):row['weight_'+n]=head['solutions']['Q_local']['weights'][l][j]
                leaf_rows.append(row)
        roles={'held':held} if held is not None else {r:d['role']==r for r in ['train','cal','eval']}
        for role,m in roles.items():
            np.testing.assert_array_equal(a[role+'_row'],d['row'][m]);h=d['old_oof_h'][m] if role=='held' else d['old_final_h'][m]
            for arm in ARMS:
                pred=predict_head(d['x'][m],h,head,arm);np.testing.assert_array_equal(pred,a[role+'_'+arm+'_raw_log']);assert np.isfinite(pred).all()
                if held is not None:
                    idx=np.searchsorted(trainrow,d['row'][m]);oof[arm+'_raw_log'][idx]=pred
                    dd=subset(d,m);yy=np.log(dd['truth_E_GeV'])
                    for key,mask in diagnostic_masks(dd).items():fold_rows.append(dict(job=job,model=arm,stratum=key,**support(dd,mask),**metrics(yy[mask],pred[mask])))
            if held is not None:seen[np.searchsorted(trainrow,d['row'][m])]+=1
        verification.append(dict(job=job,head_training_rows=int(outer.sum()),held_N=int(held.sum()) if held is not None else 0,
            deployment_replay_exact=True,all_primary_secondary_solved=True,base_X_unmodified=True))
    assert np.all(seen==1);np.savez_compressed(ART/'oof_predictions.npz',**oof)
    final=arrays(ART/'final/predictions.npz');cal=d['role']=='cal';offsets={n:float(np.mean(np.log(d['truth_E_GeV'][cal])-final['cal_'+n+'_raw_log'])) for n in ARMS}
    save(OUT/'calibration.json',dict(offset_log=offsets,cal_N=8440,unit_global=True,main_candidate='Q_local_cal'))
    records=[];paired=[];macro=[];sources=[];replication=[];tailrep=[]
    for sample,role in [('train_in_sample','train'),('source_OOF_raw','train'),('cal_development','cal'),('evaluation','eval')]:
        dd=subset(d,d['role']==role);y=np.log(dd['truth_E_GeV']);mm=diagnostic_masks(dd)
        logs=logs_for(sample,role,dd,oof,final,offsets)
        for key,m in mm.items():
            for n,pred in logs.items():records.append(dict(sample=sample,stratum=key,model=n,**support(dd,m),**metrics(y[m],pred[m])))
        for n,pred in logs.items():
            mse=[float(np.mean((pred[mm[k]]-y[mm[k]])**2)) for k in ENERGY if mm[k].any()]
            macro.append(dict(sample=sample,model=n,nonempty_bins=len(mse),macro_log_RMSE=float(np.sqrt(np.mean(mse))),unit_log_RMSE=float(np.sqrt(np.mean((pred-y)**2)))))
        sn=['mu','Q0_raw','Q_local_raw']+(['Q_local_cal','F7','stage73_F_cal'] if role!='train' else ['stage73_U_raw','stage73_F_raw'])
        for group in np.unique(dd['group']):
            for key in LOW+list(COST)+['E3200_6400','input_missing','pz50_100_E50_100','pz50_100_E100_200','pz50_100_E200_inf']:
                m=mm[key]&(dd['group']==group)
                if m.any():
                    for n in sn:sources.append(dict(sample=sample,group=str(group),stratum=key,model=n,**support(dd,m),**metrics(y[m],logs[n][m])))
        if sample=='train_in_sample':continue
        groups,gid,w=boot_weights(dd,p['bootstrap_seed']+{'train':2,'cal':1,'eval':0}[role],500)
        versions=[n+'_raw' for n in ARMS]+([n+'_cal' for n in ARMS] if role!='train' else [])
        refs=['mu']+[n for n in logs if n.startswith('stage') or n=='F7']
        comparisons=[(n,r) for n in versions for r in refs if not (role!='train' and ((n.endswith('_raw') and r.endswith('_cal')) or (n.endswith('_cal') and r.endswith('_raw'))))]
        comparisons += [('Q_local_raw','Q0_raw')]+([('Q_local_cal','Q0_cal')] if role!='train' else [])
        squared={n:(v-y)**2 for n,v in logs.items()}
        sums={k:{n:w@np.bincount(gid[m],weights=v[m],minlength=len(groups)) for n,v in squared.items()} for k,m in mm.items()}
        counts={k:w@np.bincount(gid[m],minlength=len(groups)) for k,m in mm.items()}
        for key,m in mm.items():
            if not m.any():continue
            den=counts[key];n_groups=len(np.unique(dd['group'][m]))
            ts={n:{t:w@np.bincount(gid[m],weights=indicator(v[m]-y[m],t).astype(float),minlength=len(groups)) for t in TAILS} for n,v in logs.items()}
            for n,ref in comparisons:
                good=(den>0)&(sums[key][ref]>0);valid=good if n_groups>=3 else np.zeros(500,bool)
                rr=np.sqrt(sums[key][n][valid]/sums[key][ref][valid]);lo,hi=np.quantile(rr,[.025,.975]) if len(rr) else [np.nan,np.nan]
                ratio=float(np.sqrt(squared[n][m].mean()/squared[ref][m].mean()))
                row=dict(sample=sample,stratum=key,model=n,reference=ref,**support(dd,m),RMSE_ratio=ratio,RMSE_ratio_low95=float(lo),RMSE_ratio_high95=float(hi),
                    gain_pct=100*(1-ratio),gain_low95_pct=100*(1-float(hi)),bootstrap_valid=int(valid.sum()),bootstrap_invalid=500-int(valid.sum()))
                for t in TAILS:
                    delta=100*(ts[n][t][valid]-ts[ref][t][valid])/den[valid];a,b=np.quantile(delta,[.025,.975]) if len(delta) else [np.nan,np.nan]
                    row[t+'_delta_pp']=float(100*(indicator(logs[n][m]-y[m],t).mean()-indicator(logs[ref][m]-y[m],t).mean()))
                    row[t+'_low95_pp']=float(a);row[t+'_high95_pp']=float(b)
                paired.append(finite(row))
            for draw in [0,173,499]:
                rep=np.repeat(np.flatnonzero(m),w[draw,gid[m]])
                if not len(rep):continue
                direct=np.sqrt(squared['Q_local_raw'][rep].mean()/squared['Q0_raw'][rep].mean())
                replication.append(abs(float(direct-np.sqrt(sums[key]['Q_local_raw'][draw]/sums[key]['Q0_raw'][draw]))))
                for t in TAILS:
                    direct=100*(indicator(logs['Q_local_raw'][rep]-y[rep],t).mean()-indicator(logs['Q0_raw'][rep]-y[rep],t).mean())
                    tailrep.append(abs(float(direct-100*(ts['Q_local_raw'][t][draw]-ts['Q0_raw'][t][draw])/den[draw])))
        nonempty=[k for k in ENERGY if mm[k].any()];good=np.logical_and.reduce([counts[k]>0 for k in nonempty])
        for n,ref in comparisons:
            nr=sum(sums[k][n][good]/counts[k][good] for k in nonempty)/len(nonempty);dr=sum(sums[k][ref][good]/counts[k][good] for k in nonempty)/len(nonempty)
            rr=np.sqrt(nr/dr);lo,hi=np.quantile(rr,[.025,.975])
            ratio=float(np.sqrt(np.mean([squared[n][mm[k]].mean() for k in nonempty])/np.mean([squared[ref][mm[k]].mean() for k in nonempty])))
            paired.append(finite(dict(sample=sample,stratum='macro',model=n,reference=ref,**support(dd,np.ones(len(y),bool)),RMSE_ratio=ratio,RMSE_ratio_low95=float(lo),RMSE_ratio_high95=float(hi),
                gain_pct=100*(1-ratio),gain_low95_pct=100*(1-hi),bootstrap_valid=int(good.sum()),bootstrap_invalid=500-int(good.sum()),
                **{t+s:'不适用' for t in TAILS for s in ['_delta_pp','_low95_pp','_high95_pp']})))
    for name,rows in [('metrics',records),('paired',paired),('macro',macro),('fold_metrics',fold_rows),('head_training_metrics',training_rows),('leaf_support',leaf_rows)]:table(OUT/(name+'.tsv'),rows)
    with gzip.open(OUT/'source_metrics.tsv.gz','wt',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(sources[0]),delimiter='\t',lineterminator='\n')
        writer.writeheader();writer.writerows(sources)
    write_interpretation(sources)
    decisions={}
    for n in [a+s for a in ARMS for s in ['_raw','_cal']]:
        def result(k,ref):return next(v for v in paired if v['sample']=='evaluation' and v['model']==n and v['stratum']==k and v['reference']==ref)
        rec={k:result(k,'mu')['RMSE_ratio_high95']<=1.05 for k in LOW}
        pro={k:result(k,'F7')['RMSE_ratio_high95']<=v for k,v in COST.items()}
        tail={k:{t:result(k,'F7')[t+'_high95_pp']<=2 for t in TAILS[:3]} for k in LOW+list(COST)}
        decisions[n]=dict(recovery=rec,breakthrough={k:result(k,'mu')['gain_low95_pct']>0 for k in LOW},protection=pro,tail50=tail,
            pass_all=all(rec.values()) and all(pro.values()) and all(all(v.values()) for v in tail.values()))
    passed=decisions['Q_local_cal']['pass_all']
    save(OUT/'decisions.json',dict(main_candidate='Q_local_cal',deployment='freeze research candidate; independent confirmation required' if passed else 'retain F7',versions=decisions))
    save(OUT/'validation.json',dict(passed=True,output_checks=verification,OOF_exactly_once_N=int(seen.sum()),bootstrap_event_expansion_draws=[0,173,499],
        bootstrap_RMSE_ratio_max_abs_diff=max(replication),bootstrap_tail_delta_max_abs_diff_pp=max(tailrep),eligible_missing_N=[21,3,7],
        new_fits_in_report=0,new_base_model_queries_in_report=0,**resources(start)))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    for ax,sample in zip(axes,['source_OOF_raw','evaluation']):
        names=['mu','stage73_U_raw','stage73_F_raw','Q0_raw','Q_local_raw'] if sample=='source_OOF_raw' else ['mu','F7','stage73_F_cal','Q0_cal','Q_local_cal']
        for n in names:
            vals=[next(v['log_RMSE'] for v in records if v['sample']==sample and v['stratum']==k and v['model']==n) for k in ENERGY]
            ax.plot(np.arange(7),vals,'o-',ms=3,label=n)
        ax.set_xticks(np.arange(7),[k[1:] for k in ENERGY],rotation=40);ax.set_ylabel('log-RMSE');ax.set_title(sample);ax.legend(fontsize=8);ax.grid(alpha=.2)
    fig.tight_layout();fig.savefig(OUT/'risk_complementarity.png',dpi=150);plt.close(fig)
    save(OUT/'report_resources.json',dict(**resources(start),scope='full QA, all metrics and paired source bootstrap,figure',physical_EOS_IO='未测量'))
    print(json.dumps(dict(offsets=offsets,decisions=decisions,**resources(start)),indent=2))


if __name__=='__main__':main()
