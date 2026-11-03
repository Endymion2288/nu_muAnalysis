#!/usr/bin/env python3
"""Fixed stage68 comparisons and independent deployment checks, no model fitting."""
import csv
import json
import numpy as np
from group_risk import OUT, ART, REPO, LOW, COST, inputs, masks, training_split, begin, resources, save
from report_expert_combination import table, metrics, support, boot_weights

TAILS=['tail50','positive_tail50','negative_tail50','tail100','positive_tail100','negative_tail100']
KEYS=LOW+list(COST)


def indicator(error,key):
    relative=np.expm1(error);limit=.5 if '50' in key else 1.
    return relative>limit if key.startswith('positive') else relative< -limit if key.startswith('negative') else abs(relative)>limit


def full_metrics(y,pred):
    result=metrics(y,pred)
    loss=(pred-y)**2
    for key in TAILS:
        result[key+'_loss_fraction']=float(loss[indicator(pred-y,key)].sum()/loss.sum()) if len(y) and loss.sum()>0 else np.nan
    return result


def finite(value):
    if isinstance(value,dict):return {k:finite(v) for k,v in value.items()}
    if isinstance(value,list):return [finite(v) for v in value]
    if isinstance(value,(float,np.floating)) and not np.isfinite(value):return None
    return value


def main():
    start=begin();p=json.loads((OUT/'protocol.json').read_text());d=inputs()
    import xgboost as xgb
    arrays={};verification=[];folds=[];trajectory=[]
    cached_trace=[]
    if (OUT/'trajectory.tsv').exists():
        integer_columns={'iteration','capped_cost_updates','clipped_dual_increments'}
        for row in csv.DictReader((OUT/'trajectory.tsv').open(),delimiter='\t'):
            cached_trace.append({k:v if k=='job' else int(v) if k in integer_columns else float(v) for k,v in row.items()})
    tr=d['role']=='train';train_rows=d['row'][tr];oof={n:np.full(tr.sum(),np.nan) for n in ['C','R']};seen=np.zeros(tr.sum(),int)
    for job in ['fold0','fold1','fold2','final']:
        with np.load(ART/job/'predictions.npz') as z:arrays[job]={k:z[k] for k in z.files}
        a=arrays[job];diag=json.loads((OUT/job/'fit.json').read_text());use,held,purged=training_split(d,p,job)
        assert diag['train_N']==int(use.sum()) and diag['purged_train_N']==int(purged.sum())
        names=['held'] if held is not None else ['train','cal','eval']
        for name in names:
            take=held if name=='held' else d['role']==name
            np.testing.assert_array_equal(a[name+'_row'],d['row'][take])
        train_dm=xgb.DMatrix(d['x'][use],feature_names=p['features'],nthread=1)
        for n in ['C','R']:
            model=xgb.Booster(params={'nthread':1});model.load_model(ART/job/(n+'.ubj'))
            assert model.num_boosted_rounds()==400 and model.feature_names==p['features']
            assert json.loads(model.attr('deployment_inputs'))==p['features']
            maxdiff=0.
            for name in names:
                take=held if name=='held' else d['role']==name
                pred=model.predict(xgb.DMatrix(d['x'][take],feature_names=p['features'],nthread=1)).astype(float)
                diff=float(np.max(abs(pred-a[name+'_'+n+'_raw_log'])));assert diff==0.;maxdiff=max(maxdiff,diff)
            # Independent recomputation of saved training-risk denominators and terminal risks.
            pred=model.predict(train_dm).astype(float);yy=np.log(d['truth_E_GeV'][use]);dd={k:v[use] for k,v in d.items()}
            np.testing.assert_allclose([np.mean((pred[masks(dd)[k]]-yy[masks(dd)[k]])**2) for k in KEYS],diag[n+'_risks'],rtol=1e-12)
            verification.append(dict(job=job,model=n,trees=400,features=62,standalone_prediction_max_abs_diff=maxdiff,training_risks_recomputed=True,train_N=int(use.sum()),purged_N=int(purged.sum()),held_N=int(held.sum()) if held is not None else 0,group_overlap=0,exact_incoming_overlap=0))
        if 'trajectory' in diag:
            for t in diag['trajectory']:
                trajectory.append(dict(job=job,**{k:v for k,v in t.items() if not isinstance(v,list)},
                    **{'lambda_'+k:v for k,v in zip(COST,t['cost_dual'])},**{'q_'+k:v for k,v in zip(LOW,t['low_dual'])},
                    **{'MSE_ratio_'+k:v for k,v in zip(KEYS,t['low_MSE_ratios']+t['cost_MSE_ratios'])}))
        else:
            trace=[t for t in cached_trace if t['job']==job]
            assert len(trace)==400 and all('MSE_ratio_'+k in trace[-1] for k in KEYS)
            trajectory.extend(trace)
        if held is not None:
            idx=np.searchsorted(train_rows,d['row'][held]);np.testing.assert_array_equal(train_rows[idx],d['row'][held]);seen[idx]+=1
            for n in ['C','R']:oof[n][idx]=a['held_'+n+'_raw_log']
            dd={k:v[held] for k,v in d.items()};yy=np.log(dd['truth_E_GeV']);mm=masks(dd)
            for k,m in mm.items():
                for n,pred in [('C',a['held_C_raw_log']),('R',a['held_R_raw_log']),('mu',np.log(dd['pz']/.8))]:
                    folds.append(dict(fold=job,stratum=k,model=n,**support(dd,m),**full_metrics(yy[m],pred[m])))
    assert np.all(seen==1) and all(np.isfinite(v).all() for v in oof.values())
    final=arrays['final'];offsets={n:float(np.mean(np.log(d['truth_E_GeV'][d['role']=='cal'])-final['cal_'+n+'_raw_log'])) for n in ['C','R']}
    save(OUT/'calibration.json',dict(offset_log=offsets,cal_N=8440,policy='one global mean log offset per final model; fixed predictions bootstrap does not refit it',main_candidate='R_cal'))
    np.savez_compressed(ART/'oof_predictions.npz',row=train_rows,C_raw_log=oof['C'],R_raw_log=oof['R'])
    refs={}
    for stage,path in [('F7','ml/artifacts/stage56/predictions.npz'),('stage60','ml/artifacts/stage60/predictions.npz'),('stage62','ml/artifacts/stage62/A_full_unit/predictions.npz')]:
        with np.load(REPO/path) as z:refs[stage]={k:z[k] for k in z.files if k!='metadata_json'}
    f7offset=float(json.loads((REPO/'workbook/stage60_energy_ml/models.json').read_text())['final']['offset_log'])
    records=[];paired=[];sources=[];replication_errors=[];sample_logs={}
    for sample,role in [('train_in_sample','train'),('source_OOF_raw','train'),('cal_development','cal'),('evaluation','eval')]:
        dd={k:v[d['role']==role] for k,v in d.items()};y=np.log(dd['truth_E_GeV']);mm=masks(dd)
        logs={'mu':np.log(dd['pz']/.8)}
        if sample=='source_OOF_raw':logs.update({n+'_raw':oof[n] for n in ['C','R']})
        else:
            for n in ['C','R']:
                logs[n+'_raw']=final[role+'_'+n+'_raw_log']
                if role!='train':logs[n+'_cal']=logs[n+'_raw']+offsets[n]
        if role!='train':
            for a in refs.values():np.testing.assert_array_equal(a[role+'_row'],dd['row'])
            logs.update(F7=refs['F7'][role+'_raw_log'].mean(axis=0)+f7offset,stage60=refs['stage60']['cal_final_gate' if role=='cal' else 'eval_gate'],stage62=refs['stage62'][role+'_point_cal_log'])
        sample_logs[sample]=(dd,logs)
        for k,m in mm.items():
            for n,pred in logs.items():records.append(dict(sample=sample,stratum=k,model=n,**support(dd,m),**full_metrics(y[m],pred[m])))
        for g in np.unique(dd['group']):
            for k in KEYS+['input_missing','E3200_6400']:
                m=mm[k]&(dd['group']==g)
                if not m.any():continue
                for n in ['mu','C_raw','R_raw']+(['C_cal','R_cal','F7'] if role!='train' else []):
                    sources.append(dict(sample=sample,group=str(g),stratum=k,model=n,**support(dd,m),**full_metrics(y[m],logs[n][m])))
        if sample=='train_in_sample':continue
        groups,gid,w=boot_weights(dd,p['bootstrap_seed']+{'train':2,'cal':1,'eval':0}[role],500)
        for k,m in mm.items():
            if not m.any():continue
            sp=support(dd,m);ng=sp['groups'];count=np.bincount(gid[m],minlength=len(groups));den=w@count
            sums={n:w@np.bincount(gid[m],weights=(pred[m]-y[m])**2,minlength=len(groups)) for n,pred in logs.items()}
            comparisons=[('R_raw','C_raw'),('R_raw','mu'),('C_raw','mu')]
            if role!='train':comparisons += [('R_cal','C_cal')]+[(n,r) for n in ['R_raw','R_cal','C_raw','C_cal'] for r in ['F7']]+[('R_cal','mu')]+[('R_cal',r) for r in ['stage60','stage62']]
            for n,ref in comparisons:
                err=logs[n]-y;er=logs[ref]-y;ratio=float(np.sqrt(np.mean(err[m]**2)/np.mean(er[m]**2)));good=(den>0)&(sums[ref]>0)
                valid=int(good.sum()) if ng>=3 else 0
                rr=np.sqrt(sums[n][good]/sums[ref][good]);lo,hi=np.quantile(rr,[.025,.975]) if valid else [np.nan,np.nan]
                row=dict(sample=sample,stratum=k,model=n,reference=ref,**sp,RMSE_ratio=ratio,RMSE_ratio_low95=float(lo),RMSE_ratio_high95=float(hi),gain_pct=100*(1-ratio),gain_low95_pct=float(100*(1-hi)),gain_high95_pct=float(100*(1-lo)),bootstrap_valid=valid,bootstrap_invalid=500-valid)
                for key in TAILS:
                    diff=100*(indicator(err,key).astype(float)-indicator(er,key).astype(float))
                    vals=w@np.bincount(gid[m],weights=diff[m],minlength=len(groups))
                    low,high=np.quantile(vals[good]/den[good],[.025,.975]) if valid else [np.nan,np.nan]
                    row[key+'_delta_pp']=float(diff[m].mean());row[key+'_low95_pp']=float(low);row[key+'_high95_pp']=float(high)
                paired.append(row)
            # Independent event replication of one source bootstrap draw per nonempty stratum.
            rep=np.repeat(np.flatnonzero(m),w[0,gid[m]])
            if len(rep):
                direct=np.sqrt(np.mean((logs['R_raw'][rep]-y[rep])**2)/np.mean((logs['C_raw'][rep]-y[rep])**2))
                replication_errors.append(abs(float(direct-np.sqrt(sums['R_raw'][0]/sums['C_raw'][0]))))
    for name,data in [('metrics',records),('paired',paired),('fold_metrics',folds),('source_metrics',sources),('trajectory',trajectory)]:table(OUT/(name+'.tsv'),data)
    # Retain every per-group risk/dual once in the common TSV, not four repeated JSON arrays.
    for job in arrays:
        path=OUT/job/'fit.json';diag=json.loads(path.read_text())
        if 'trajectory' in diag:
            del diag['trajectory'];diag['trajectory_table']='../trajectory.tsv (filter job column)';save(path,diag)
    decisions={}
    for variant in ['raw','cal']:
        name='R_'+variant
        def row(k,ref):return next(v for v in paired if v['sample']=='evaluation' and v['stratum']==k and v['model']==name and v['reference']==ref)
        recovery={k:row(k,'mu')['RMSE_ratio_high95']<=1.05 for k in LOW}
        breakthrough={k:row(k,'mu')['gain_low95_pct']>0 for k in LOW}
        protection={k:row(k,'F7')['RMSE_ratio_high95']<=v for k,v in COST.items()}
        tails={k:{tail:row(k,'F7')[tail+'_high95_pp']<=2 for tail in TAILS[:3]} for k in KEYS}
        decisions[name]=dict(recovery=recovery,breakthrough=breakthrough,protection=protection,tail50=tails,pass_all=all(recovery.values()) and all(protection.values()) and all(all(v.values()) for v in tails.values()))
    save(OUT/'decisions.json',finite(dict(main_candidate='R_cal',deployment='retain F7',versions=decisions,policy='original traditional/F7 thresholds, no selection of favorable raw/cal variant')))
    save(OUT/'validation.json',dict(models=verification,OOF_exactly_once_N=int(seen.sum()),OOF_missing=0,bootstrap_replication_max_abs_diff=max(replication_errors),original_eligible_missing_counts=[int(d['missing'][d['role']==r].sum()) for r in ['train','cal','eval']],protocol_version=p['protocol_version'],formal_fits=8,additional_fits=0,locked_test=False,truth_free_standalone_inputs=True))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size':9})
    fig,axes=plt.subplots(1,3,figsize=(13,3.7))
    for ax,sample in zip(axes,['train_in_sample','source_OOF_raw','evaluation']):
        kk=['E50_100','E100_200','all','pz50_100','high_y','unconfirmed','E3200_6400'];xx=np.arange(len(kk))
        models=['mu','C_raw','R_raw'] if sample!='evaluation' else ['mu','F7','C_cal','R_cal']
        for n in models:
            yy=[next(r['log_RMSE'] for r in records if r['sample']==sample and r['stratum']==k and r['model']==n) for k in kk];ax.plot(xx,yy,'o-',label=n,ms=3)
        ax.set_xticks(xx,kk,rotation=55,ha='right');ax.set_title(sample);ax.set_ylabel('log-RMSE');ax.grid(alpha=.25);ax.legend(fontsize=8)
    fig.suptitle('Stage68: full readout direct risk training; fixed 400-tree outputs')
    fig.tight_layout();fig.savefig(OUT/'risk_comparison.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(10,3.6))
    for job in ['fold0','fold1','fold2','final']:
        tt=[t for t in trajectory if t['job']==job];axes[0].plot([t['iteration'] for t in tt],[t['worst_low_MSE_ratio'] for t in tt],label=job)
        axes[1].plot([t['iteration'] for t in tt],[t['max_cost_violation'] for t in tt],label=job)
    axes[0].set_yscale('log');axes[0].set_ylabel('worst low-E MSE / traditional MSE');axes[1].set_ylabel('max training constraint violation (MSE ratio)')
    for ax in axes:ax.set_xlabel('tree iteration');ax.legend();ax.grid(alpha=.25)
    fig.tight_layout();fig.savefig(OUT/'training_risks.png',dpi=150);plt.close(fig)
    save(OUT/'report_resources.json',dict(**resources(start),bootstrap_replicates=500,bootstrap_scope='component-stratified conservative source groups, paired fixed predictions; excludes retraining, calibration refit, full genealogy, response/interaction and research selection uncertainty; development cal/eval',new_fits=0))
    print(json.dumps(decisions,indent=2))


if __name__=='__main__':main()
