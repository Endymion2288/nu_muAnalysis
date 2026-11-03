#!/usr/bin/env python3
"""All-event point risks, proper density scores and fixed source bootstrap."""
import csv
from group_risk import inputs, training_split
from support_augmentation import metrics, indicator, boot_weights, LOW, COST, TAILS, masks
from energy_reweight import ENERGY, support, finite
from report_energy_reweight import references
from exact_conditional_decision import *


def diagnostic_masks(d, q):
    result=masks(d);result['zero_q']=q==0
    for key in ['E50_100','E100_200','E200_inf']:
        result['pz50_100_'+key]=result['pz50_100']&result[key]
    return result


def extra_references(role, row, oof=False):
    result={}
    if oof:
        for stage,names in [(68,['C','R']),(69,['C','P']),(73,['U','S','F'])]:
            a=arrays(REPO/f'ml/artifacts/stage{stage}/oof_predictions.npz')
            np.testing.assert_array_equal(a['row'],row)
            for n in names:result[f'stage{stage}_{n}_raw']=a[n+'_raw_log']
    else:
        a=arrays(REPO/'ml/artifacts/stage73/final/predictions.npz')
        np.testing.assert_array_equal(a[role+'_row'],row)
        offsets=json.loads((REPO/'workbook/stage73_energy_ml/calibration.json').read_text())['offset_log']
        for n in ['U','S','F']:
            result['stage73_'+n+'_raw']=a[role+'_'+n+'_raw_log']
            if role!='train':result['stage73_'+n+'_cal']=a[role+'_'+n+'_raw_log']+offsets[n]
        if role!='train':result.update(references(role,row))
    return result


def merged_held(job, d, p):
    """Reconstruct a fold view after verified, lossless removal of duplicate files."""
    _,held,_=training_split(d,p,job);a=arrays(ART/'oof_predictions.npz')
    idx=np.searchsorted(a['row'],d['row'][held]);np.testing.assert_array_equal(a['row'][idx],d['row'][held])
    result={'held_row':a['row'][idx],'held_true_q_density':a['true_q_density'][idx]}
    for arm in ARMS:
        for key in KEYS+['true_logdensity']:result['held_'+arm+'_'+key]=a[arm+'_'+key][idx]
    return result


def write_interpretation(d, oof, source_rows):
    error=oof['X_raw_log']-np.log(d['truth_E_GeV'][d['role']=='train']);zero=oof['true_q_density']==0
    result=[]
    for key in ['all','E50_100','E100_200','pz50_100','high_y','unconfirmed','E3200_6400']:
        by={}
        for v in source_rows:
            if v['sample']=='evaluation' and v['stratum']==key:
                by.setdefault(str(v['group']),{})[v['model']]=float(v['log_RMSE'])
        result.append(dict(stratum=key,groups=len(by),
            X_cal_worse_than_F7_N=sum(v['X_cal']>v['F7'] for v in by.values()),
            X_cal_worse_than_mu_N=sum(v['X_cal']>v['mu'] for v in by.values())))
    save(OUT/'interpretation.json',dict(zero_q_OOF_N=int(zero.sum()),
        zero_q_X_OOF_squared_loss_fraction=float(np.sum(error[zero]**2)/np.sum(error**2)),
        source_central_risk=result,no_events_removed=True,no_new_models_or_queries=True))


def main():
    start=begin();p=json.loads((OUT/'protocol.json').read_text())
    d=arrays(CACHE/'input.npz') if (CACHE/'input.npz').exists() else inputs()
    take=d['role']=='train';trainrow=d['row'][take];seen=np.zeros(len(trainrow),int)
    oof={'row':trainrow,'true_q_density':np.full(len(trainrow),np.nan)}
    for arm in ARMS:
        for key in KEYS+['true_logdensity']:oof[arm+'_'+key]=np.full(len(trainrow),np.nan)
    verification=[];fold_metrics=[];pilot=list(csv.DictReader((OUT/'numerical_QA.tsv').open(),delimiter='\t'))
    proposals=json.loads((OUT/'proposals.json').read_text());pilot_diff=[]
    for job in JOBS:
        tr,held,purge=training_split(d,p,job);path=ART/job/'predictions.npz'
        a=arrays(path) if path.exists() else merged_held(job,d,p)
        old=arrays(MODEL_ART/job/'predictions.npz');mass=np.array(proposals[job]['mass'])
        count,expected_mass=proposal(d['pz'][tr],d['truth_E_GeV'][tr]);np.testing.assert_array_equal(mass,expected_mass)
        np.testing.assert_array_equal(count,np.array(proposals[job]['count']))
        roles={'held':held} if held is not None else {r:d['role']==r for r in ['train','cal','eval']}
        for role,m in roles.items():
            np.testing.assert_array_equal(a[role+'_row'],d['row'][m])
            q=proposal_density(d['pz'][m],np.log(d['truth_E_GeV'][m]),mass)
            np.testing.assert_array_equal(q,a[role+'_true_q_density']);np.testing.assert_array_equal(q,old[role+'_true_q_density'])
            for arm in ARMS:
                name=role+'_'+arm+'_';raw=a[name+'raw_log']
                assert np.isfinite(raw).all() and np.all((raw>=LOG_EDGES[0])&(raw<=LOG_EDGES[-1]))
                assert a[name+'normalization_error'].max()<=p['numeric_normalization_tolerance']
                # Reuse stage74 independent original true-query margins, no new full inference.
                with np.errstate(divide='ignore'):
                    density=np.log(q)+old[role+'_'+arm+'_logits'][:,0]-a[name+'logZ']
                np.testing.assert_array_equal(density,a[name+'true_logdensity'])
                assert np.array_equal(np.isneginf(density),q==0)
                fixed=[v for v in pilot if v['job']==job and v['arm']==arm and v['role']==role]
                if fixed:
                    idx=np.searchsorted(a[role+'_row'],[int(v['row']) for v in fixed])
                    delta=abs(raw[idx]-np.array([float(v['exact_log_mean']) for v in fixed]))
                    pilot_diff.extend(delta);assert delta.max()<1e-12
                verification.append(dict(job=job,role=role,arm=arm,N=len(raw),zero_q_N=int((q==0).sum()),
                    original_proposal_and_rows_exact=True,stage74_true_margin_density_exact=True,
                    normalization_error_max=float(a[name+'normalization_error'].max()),new_fits=0))
            if held is not None:
                idx=np.searchsorted(trainrow,a['held_row']);np.testing.assert_array_equal(trainrow[idx],a['held_row']);seen[idx]+=1
                oof['true_q_density'][idx]=q
                dd={k:v[m] for k,v in d.items()};yy=np.log(dd['truth_E_GeV'])
                for arm in ARMS:
                    for key in KEYS+['true_logdensity']:oof[arm+'_'+key][idx]=a['held_'+arm+'_'+key]
                    for key,mask in diagnostic_masks(dd,q).items():
                        fold_metrics.append(dict(job=job,arm=arm,stratum=key,**support(dd,mask),**metrics(yy[mask],a['held_'+arm+'_raw_log'][mask])))
    assert np.all(seen==1) and all(np.isfinite(oof[arm+'_raw_log']).all() for arm in ARMS)
    np.savez_compressed(ART/'oof_predictions.npz',**oof)
    final=arrays(ART/'final/predictions.npz');cal=d['role']=='cal'
    offsets={arm:float(np.mean(np.log(d['truth_E_GeV'][cal])-final['cal_'+arm+'_raw_log'])) for arm in ARMS}
    save(OUT/'calibration.json',dict(offset_log=offsets,main_candidate='X_cal',cal_N=8440,unit_global=True,
        density_not_recalibrated=True))
    records=[];paired=[];macro=[];sources=[];density_rows=[];replication=[];tail_replication=[]
    for sample,role in [('train_in_sample','train'),('source_OOF_raw','train'),('cal_development','cal'),('evaluation','eval')]:
        take=d['role']==role;dd={k:v[take] for k,v in d.items()};y=np.log(dd['truth_E_GeV']);is_oof=sample=='source_OOF_raw'
        current=oof if is_oof else final;prefix='' if is_oof else role+'_'
        q=current[prefix+'true_q_density'];mm=diagnostic_masks(dd,q)
        logs={'mu':np.log(dd['pz']/.8)}
        for arm in ARMS:
            logs[arm+'_raw']=current[prefix+arm+'_raw_log']
            if role!='train':logs[arm+'_cal']=logs[arm+'_raw']+offsets[arm]
        logs.update(extra_references(role,dd['row'],is_oof))
        for k,m in mm.items():
            for name,pred in logs.items():records.append(dict(sample=sample,stratum=k,model=name,**support(dd,m),**metrics(y[m],pred[m])))
            for arm in ARMS:
                ld=current[prefix+arm+'_true_logdensity'];ok=m&(q>0)
                density_rows.append(dict(sample=sample,stratum=k,model=arm,**support(dd,m),zero_q_N=int((m&(q==0)).sum()),
                    mean_NLL_all='未测量' if not m.any() else '无穷(+inf)' if np.any(m&(q==0)) else float(-ld[m].mean()),
                    supported_only_N=int(ok.sum()),supported_only_mean_NLL=float(-ld[ok].mean()) if ok.any() else '未测量',
                    mean_low_bin_mass=float(current[prefix+arm+'_low_bin_mass'][m].mean()) if m.any() else '未测量',
                    mean_high_bin_mass=float(current[prefix+arm+'_high_bin_mass'][m].mean()) if m.any() else '未测量',
                    normalization_error_max=float(current[prefix+arm+'_normalization_error'][m].max()) if m.any() else '未测量'))
        for name,pred in logs.items():
            mse=[float(np.mean((pred[mm[k]]-y[mm[k]])**2)) for k in ENERGY if mm[k].any()]
            macro.append(dict(sample=sample,model=name,nonempty_bins=len(mse),macro_log_RMSE=float(np.sqrt(np.mean(mse))),
                unit_log_RMSE=float(np.sqrt(np.mean((pred-y)**2)))))
        source_models=['mu','M_raw','X_raw']+(['M_cal','X_cal','F7','stage73_S_cal','stage73_F_cal'] if role!='train' else [])
        for group in np.unique(dd['group']):
            for k in LOW+list(COST)+['E3200_6400','input_missing','zero_q','pz50_100_E50_100','pz50_100_E100_200','pz50_100_E200_inf']:
                m=mm[k]&(dd['group']==group)
                if m.any():
                    for n in source_models:sources.append(dict(sample=sample,group=str(group),stratum=k,model=n,**support(dd,m),**metrics(y[m],logs[n][m])))
        if sample=='train_in_sample':continue
        groups,gid,w=boot_weights(dd,p['bootstrap_seed']+{'train':2,'cal':1,'eval':0}[role],500)
        versions=['M_raw','X_raw']+(['M_cal','X_cal'] if role!='train' else [])
        refs=['mu']+[n for n in logs if n.startswith('stage') or n=='F7']
        comparisons=[(n,r) for n in versions for r in refs]+[('X_raw','M_raw')]+([('X_cal','M_cal')] if role!='train' else [])
        squared={n:(pred-y)**2 for n,pred in logs.items()}
        sums={k:{n:w@np.bincount(gid[m],weights=v[m],minlength=len(groups)) for n,v in squared.items()} for k,m in mm.items()}
        counts={k:w@np.bincount(gid[m],minlength=len(groups)) for k,m in mm.items()}
        for k,m in mm.items():
            if not m.any():continue
            den=counts[k];n_groups=len(np.unique(dd['group'][m]))
            ts={n:{t:w@np.bincount(gid[m],weights=indicator(logs[n][m]-y[m],t).astype(float),minlength=len(groups)) for t in TAILS} for n in logs}
            for n,ref in comparisons:
                good=(den>0)&(sums[k][ref]>0);valid=good if n_groups>=3 else np.zeros(500,bool)
                rr=np.sqrt(sums[k][n][valid]/sums[k][ref][valid]);lo,hi=np.quantile(rr,[.025,.975]) if len(rr) else [np.nan,np.nan]
                ratio=float(np.sqrt(squared[n][m].mean()/squared[ref][m].mean()))
                row=dict(sample=sample,stratum=k,model=n,reference=ref,**support(dd,m),RMSE_ratio=ratio,
                    RMSE_ratio_low95=float(lo),RMSE_ratio_high95=float(hi),gain_pct=100*(1-ratio),gain_low95_pct=100*(1-float(hi)),
                    bootstrap_valid=int(valid.sum()),bootstrap_invalid=500-int(valid.sum()))
                for t in TAILS:
                    delta=100*(ts[n][t][valid]-ts[ref][t][valid])/den[valid]
                    a,b=np.quantile(delta,[.025,.975]) if len(delta) else [np.nan,np.nan]
                    row[t+'_delta_pp']=float(100*(indicator(logs[n][m]-y[m],t).mean()-indicator(logs[ref][m]-y[m],t).mean()))
                    row[t+'_low95_pp']=float(a);row[t+'_high95_pp']=float(b)
                paired.append(finite(row))
            for draw in [0,173,499]:
                rep=np.repeat(np.flatnonzero(m),w[draw,gid[m]])
                if len(rep):
                    direct=np.sqrt(squared['X_raw'][rep].mean()/squared['M_raw'][rep].mean())
                    replication.append(abs(float(direct-np.sqrt(sums[k]['X_raw'][draw]/sums[k]['M_raw'][draw]))))
                    for t in TAILS:
                        direct=100*(indicator(logs['X_raw'][rep]-y[rep],t).mean()-indicator(logs['M_raw'][rep]-y[rep],t).mean())
                        tail_replication.append(abs(float(direct-100*(ts['X_raw'][t][draw]-ts['M_raw'][t][draw])/den[draw])))
        nonempty=[k for k in ENERGY if mm[k].any()];good=np.logical_and.reduce([counts[k]>0 for k in nonempty])
        for n,ref in comparisons:
            nr=sum(sums[k][n][good]/counts[k][good] for k in nonempty)/len(nonempty)
            dr=sum(sums[k][ref][good]/counts[k][good] for k in nonempty)/len(nonempty)
            rr=np.sqrt(nr/dr);lo,hi=np.quantile(rr,[.025,.975]) if len(rr) else [np.nan,np.nan]
            ratio=float(np.sqrt(np.mean([squared[n][mm[k]].mean() for k in nonempty])/np.mean([squared[ref][mm[k]].mean() for k in nonempty])))
            paired.append(finite(dict(sample=sample,stratum='macro',model=n,reference=ref,**support(dd,np.ones(len(y),bool)),
                RMSE_ratio=ratio,RMSE_ratio_low95=float(lo),RMSE_ratio_high95=float(hi),gain_pct=100*(1-ratio),gain_low95_pct=100*(1-hi),
                bootstrap_valid=int(good.sum()),bootstrap_invalid=500-int(good.sum()),
                **{t+s:'不适用' for t in TAILS for s in ['_delta_pp','_low95_pp','_high95_pp']})))
    for name,value in [('metrics',records),('paired',paired),('macro',macro),('source_metrics',sources),('fold_metrics',fold_metrics),('density',density_rows)]:table(OUT/(name+'.tsv'),value)
    write_interpretation(d,oof,sources)
    decisions={}
    for n in ['M_raw','M_cal','X_raw','X_cal']:
        def result(k,ref):return next(v for v in paired if v['sample']=='evaluation' and v['model']==n and v['stratum']==k and v['reference']==ref)
        recovery={k:result(k,'mu')['RMSE_ratio_high95']<=1.05 for k in LOW}
        breakthrough={k:result(k,'mu')['gain_low95_pct']>0 for k in LOW}
        protection={k:result(k,'F7')['RMSE_ratio_high95']<=limit for k,limit in COST.items()}
        tails={k:{t:result(k,'F7')[t+'_high95_pp']<=2 for t in TAILS[:3]} for k in LOW+list(COST)}
        decisions[n]=dict(recovery=recovery,breakthrough=breakthrough,protection=protection,tail50=tails,
            pass_all=all(recovery.values()) and all(protection.values()) and all(all(v.values()) for v in tails.values()))
    save(OUT/'decisions.json',dict(main_candidate='X_cal',deployment='retain F7',numerical_gate_passed=True,versions=decisions,
        energy_point_risk_measured=True,full_posterior_calibration_claimed=False))
    save(OUT/'validation.json',dict(passed=True,output_checks=verification,OOF_exactly_once_N=int(seen.sum()),OOF_zero_q_N=int((oof['true_q_density']==0).sum()),
        original256_pilot_readback_max_abs_diff=max(pilot_diff),bootstrap_repeats=500,
        bootstrap_event_expansion_draws=[0,173,499],bootstrap_RMSE_ratio_max_abs_diff=max(replication),
        bootstrap_tail_delta_max_abs_diff_pp=max(tail_replication),new_fits=0,new_full_model_inference_in_report=0,
        eligible_missing_N=[int(d['missing'][d['role']==r].sum()) for r in ['train','cal','eval']],**resources(start)))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    for ax,sample in zip(axes,['source_OOF_raw','evaluation']):
        names=['mu','M_raw','X_raw','stage73_S_raw'] if sample=='source_OOF_raw' else ['mu','F7','M_cal','X_cal','stage73_S_cal']
        for name in names:
            vals=[next(v['log_RMSE'] for v in records if v['sample']==sample and v['stratum']==k and v['model']==name) for k in ENERGY]
            ax.plot(np.arange(7),vals,'o-',ms=3,label=name)
        ax.set_xticks(np.arange(7),[k[1:] for k in ENERGY],rotation=40);ax.set_ylabel('log-RMSE');ax.set_title(sample);ax.legend(fontsize=8);ax.grid(alpha=.2)
    fig.tight_layout();fig.savefig(OUT/'fixed_energy_risk.png',dpi=150);plt.close(fig)
    save(OUT/'report_resources.json',dict(**resources(start),scope='output QA, full point/density metrics,source bootstrap and figure',physical_EOS_IO='未测量'))
    print(json.dumps(dict(offsets=offsets,decisions=decisions,**resources(start)),indent=2))


if __name__=='__main__':main()
