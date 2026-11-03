#!/usr/bin/env python3
"""Fixed stage69 point and auxiliary-transfer comparisons, no model fitting."""
import csv
import json
import numpy as np
from transfer_supervision import OUT, ART, REPO, LOW, COST, Network, inputs, masks, labels, training_split, transform_state, predict, restore, begin, resources, save
import torch
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
    torch.set_num_threads(1)
    arrays={};verification=[];folds=[];history=[];oof_prob=np.zeros((41447,3),np.float32);oof_prior=np.zeros((41447,3))
    tr=d['role']=='train';train_rows=d['row'][tr];oof={n:np.full(tr.sum(),np.nan) for n in ['C','P']};seen=np.zeros(tr.sum(),int)
    for job in ['fold0','fold1','fold2','final']:
        with np.load(ART/job/'predictions.npz') as z:arrays[job]={k:z[k] for k in z.files}
        a=arrays[job];diag=json.loads((OUT/job/'fit.json').read_text());assert diag['status']=='completed'
        use,held,purged=training_split(d,p,job);assert diag['train_N']==int(use.sum()) and diag['purged_N']==int(purged.sum())
        expected_state=transform_state(d['x'][use]);names=['held'] if held is not None else ['train','cal','eval']
        for name in names:
            take=held if name=='held' else d['role']==name
            np.testing.assert_array_equal(a[name+'_row'],d['row'][take])
        for n in ['C','P']:
            model,meta=restore(ART/job/(n+'.pt'));assert meta['epochs']==120 and meta['seed']==p['seed'] and meta['input_dim']==124 and meta['features']==p['features']
            for key in ['features','kind','pz_index']:assert meta['feature_state'][key]==expected_state[key]
            state_difference=0.
            for key in ['signed_scale','center','scale']:
                np.testing.assert_allclose(meta['feature_state'][key],expected_state[key],rtol=0,atol=1e-12)
                state_difference=max(state_difference,float(np.max(abs(np.asarray(meta['feature_state'][key])-expected_state[key]))))
            assert sum(v.numel() for v in model.parameters())==12420
            torch.manual_seed(p['seed']);initial_aux=Network(124).auxiliary.state_dict()
            for key,value in model.auxiliary.state_dict().items():
                if n=='C':torch.testing.assert_close(value,initial_aux[key],rtol=0,atol=0)
            if n=='P':assert any(not torch.equal(value,initial_aux[key]) for key,value in model.auxiliary.state_dict().items())
            yy=np.log(d['truth_E_GeV'][use]);assert meta['target_center']==float(yy.mean())
            maxdiff=0.
            for name in names:
                take=held if name=='held' else d['role']==name
                pred,prob=predict(model,d['x'][take],meta['feature_state'],meta['target_center'])
                diff=float(np.max(abs(pred-a[name+'_'+n+'_raw_log'])));assert diff==0.;maxdiff=max(maxdiff,diff)
                if n=='P':np.testing.assert_array_equal(prob,a[name+'_P_prob'])
            pred,prob=predict(model,d['x'][use],meta['feature_state'],meta['target_center'])
            np.testing.assert_allclose(np.mean((pred-yy)**2),diag['families'][n]['terminal_train_MSE'],rtol=1e-12)
            verification.append(dict(job=job,model=n,epochs=120,parameters=12420,features=62,missing_indicators=62,standalone_prediction_max_abs_diff=maxdiff,train_only_transform_max_abs_difference=state_difference,train_only_transform_matches_atol_1e_minus12=True,training_MSE_recomputed=True,train_N=int(use.sum()),purged_N=int(purged.sum()),held_N=int(held.sum()) if held is not None else 0,group_overlap=0,exact_incoming_overlap=0))
        with (OUT/job/'history.tsv').open() as f:
            for row in csv.DictReader(f,delimiter='\t'):history.append(dict(job=job,**{k:v if k=='family' else float(v) for k,v in row.items()}))
        if held is not None:
            idx=np.searchsorted(train_rows,d['row'][held]);np.testing.assert_array_equal(train_rows[idx],d['row'][held]);seen[idx]+=1
            for n in ['C','P']:oof[n][idx]=a['held_'+n+'_raw_log']
            oof_prob[idx]=a['held_P_prob'];oof_prior[idx]=diag['train_class_prior']
            dd={k:v[held] for k,v in d.items()};yy=np.log(dd['truth_E_GeV']);mm=masks(dd)
            for k,m in mm.items():
                for n,pred in [('C',a['held_C_raw_log']),('P',a['held_P_raw_log']),('mu',np.log(dd['pz']/.8))]:
                    folds.append(dict(fold=job,stratum=k,model=n,**support(dd,m),**full_metrics(yy[m],pred[m])))
    assert np.all(seen==1) and all(np.isfinite(v).all() for v in oof.values())
    final=arrays['final'];offsets={n:float(np.mean(np.log(d['truth_E_GeV'][d['role']=='cal'])-final['cal_'+n+'_raw_log'])) for n in ['C','P']}
    save(OUT/'calibration.json',dict(offset_log=offsets,cal_N=8440,policy='one global mean log offset per final model; fixed predictions bootstrap does not refit it',main_candidate='P_cal'))
    np.savez_compressed(ART/'oof_predictions.npz',row=train_rows,C_raw_log=oof['C'],P_raw_log=oof['P'],P_prob=oof_prob)
    refs={}
    for stage,path in [('F7','ml/artifacts/stage56/predictions.npz'),('stage60','ml/artifacts/stage60/predictions.npz'),('stage62','ml/artifacts/stage62/A_full_unit/predictions.npz'),('stage68','ml/artifacts/stage68/final/predictions.npz')]:
        with np.load(REPO/path) as z:refs[stage]={k:z[k] for k in z.files if k!='metadata_json'}
    f7offset=float(json.loads((REPO/'workbook/stage60_energy_ml/models.json').read_text())['final']['offset_log'])
    old_offsets=json.loads((REPO/'workbook/stage68_energy_ml/calibration.json').read_text())['offset_log']
    records=[];paired=[];sources=[];replication_errors=[];sample_logs={}
    for sample,role in [('train_in_sample','train'),('source_OOF_raw','train'),('cal_development','cal'),('evaluation','eval')]:
        dd={k:v[d['role']==role] for k,v in d.items()};y=np.log(dd['truth_E_GeV']);mm=masks(dd)
        logs={'mu':np.log(dd['pz']/.8)}
        if sample=='source_OOF_raw':logs.update({n+'_raw':oof[n] for n in ['C','P']})
        else:
            for n in ['C','P']:
                logs[n+'_raw']=final[role+'_'+n+'_raw_log']
                if role!='train':logs[n+'_cal']=logs[n+'_raw']+offsets[n]
        if role!='train':
            for a in refs.values():np.testing.assert_array_equal(a[role+'_row'],dd['row'])
            logs.update(F7=refs['F7'][role+'_raw_log'].mean(axis=0)+f7offset,stage60=refs['stage60']['cal_final_gate' if role=='cal' else 'eval_gate'],stage62=refs['stage62'][role+'_point_cal_log'],stage68_C=refs['stage68'][role+'_C_raw_log']+old_offsets['C'],stage68_R=refs['stage68'][role+'_R_raw_log']+old_offsets['R'])
        sample_logs[sample]=(dd,logs)
        for k,m in mm.items():
            for n,pred in logs.items():records.append(dict(sample=sample,stratum=k,model=n,**support(dd,m),**full_metrics(y[m],pred[m])))
        for g in np.unique(dd['group']):
            for k in KEYS+['input_missing','E3200_6400']:
                m=mm[k]&(dd['group']==g)
                if not m.any():continue
                for n in ['mu','C_raw','P_raw']+(['C_cal','P_cal','F7'] if role!='train' else []):
                    sources.append(dict(sample=sample,group=str(g),stratum=k,model=n,**support(dd,m),**full_metrics(y[m],logs[n][m])))
        if sample=='train_in_sample':continue
        groups,gid,w=boot_weights(dd,p['bootstrap_seed']+{'train':2,'cal':1,'eval':0}[role],500)
        for k,m in mm.items():
            if not m.any():continue
            sp=support(dd,m);ng=sp['groups'];count=np.bincount(gid[m],minlength=len(groups));den=w@count
            sums={n:w@np.bincount(gid[m],weights=(pred[m]-y[m])**2,minlength=len(groups)) for n,pred in logs.items()}
            comparisons=[('P_raw','C_raw'),('P_raw','mu'),('C_raw','mu')]
            if role!='train':comparisons += [('P_cal','C_cal')]+[(n,r) for n in ['P_raw','P_cal','C_raw','C_cal'] for r in ['F7']]+[('P_cal','mu')]+[('P_cal',r) for r in ['stage60','stage62','stage68_C','stage68_R']]
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
                direct=np.sqrt(np.mean((logs['P_raw'][rep]-y[rep])**2)/np.mean((logs['C_raw'][rep]-y[rep])**2))
                replication_errors.append(abs(float(direct-np.sqrt(sums['P_raw'][0]/sums['C_raw'][0]))))
    for name,data in [('metrics',records),('paired',paired),('fold_metrics',folds),('source_metrics',sources),('history',history)]:table(OUT/(name+'.tsv'),data)
    auxiliary_report(d,arrays,oof_prob,oof_prior,p)
    decisions={}
    for variant in ['raw','cal']:
        name='P_'+variant
        def row(k,ref):return next(v for v in paired if v['sample']=='evaluation' and v['stratum']==k and v['model']==name and v['reference']==ref)
        recovery={k:row(k,'mu')['RMSE_ratio_high95']<=1.05 for k in LOW}
        breakthrough={k:row(k,'mu')['gain_low95_pct']>0 for k in LOW}
        protection={k:row(k,'F7')['RMSE_ratio_high95']<=v for k,v in COST.items()}
        tails={k:{tail:row(k,'F7')[tail+'_high95_pp']<=2 for tail in TAILS[:3]} for k in KEYS}
        decisions[name]=dict(recovery=recovery,breakthrough=breakthrough,protection=protection,tail50=tails,pass_all=all(recovery.values()) and all(protection.values()) and all(all(v.values()) for v in tails.values()))
    save(OUT/'decisions.json',finite(dict(main_candidate='P_cal',deployment='retain F7',versions=decisions,policy='original traditional/F7 thresholds, no selection of favorable raw/cal variant')))
    save(OUT/'validation.json',dict(models=verification,OOF_exactly_once_N=int(seen.sum()),OOF_missing=0,bootstrap_replication_max_abs_diff=max(replication_errors),original_eligible_missing_counts=[int(d['missing'][d['role']==r].sum()) for r in ['train','cal','eval']],protocol_stage=69,formal_fits=8,additional_fits=0,locked_test=False,truth_free_standalone_inputs=True))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size':9})
    fig,axes=plt.subplots(1,3,figsize=(13,3.7))
    for ax,sample in zip(axes,['train_in_sample','source_OOF_raw','evaluation']):
        kk=['E50_100','E100_200','all','pz50_100','high_y','unconfirmed','E3200_6400'];xx=np.arange(len(kk))
        models=['mu','C_raw','P_raw'] if sample!='evaluation' else ['mu','F7','C_cal','P_cal']
        for n in models:
            yy=[next(r['log_RMSE'] for r in records if r['sample']==sample and r['stratum']==k and r['model']==n) for k in kk];ax.plot(xx,yy,'o-',label=n,ms=3)
        ax.set_xticks(xx,kk,rotation=55,ha='right');ax.set_title(sample);ax.set_ylabel('log-RMSE');ax.grid(alpha=.25);ax.legend(fontsize=8)
    fig.suptitle('Stage69: matched regression and transfer auxiliary supervision; terminal120')
    fig.tight_layout();fig.savefig(OUT/'risk_comparison.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(10,3.6))
    for job in ['fold0','fold1','fold2','final']:
        for family in ['C','P']:
            hh=[t for t in history if t['job']==job and t['family']==family]
            axes[0].plot([t['epoch'] for t in hh],[t['online_main_MSE'] for t in hh],label=job+' '+family,ls='-' if family=='P' else '--')
            if family=='P':axes[1].plot([t['epoch'] for t in hh],[t['online_aux_CE'] for t in hh],label=job)
    axes[0].set_yscale('log');axes[0].set_ylabel('online training main MSE');axes[1].set_ylabel('online valid-label auxiliary CE (P)')
    for ax in axes:ax.set_xlabel('epoch');ax.legend(fontsize=7);ax.grid(alpha=.25)
    fig.tight_layout();fig.savefig(OUT/'training_losses.png',dpi=150);plt.close(fig)
    save(OUT/'report_resources.json',dict(**resources(start),bootstrap_replicates=500,bootstrap_scope='component-stratified conservative source groups, paired fixed predictions; excludes retraining, calibration refit, full genealogy, response/interaction and research selection uncertainty; development cal/eval',new_fits=0))
    print(json.dumps(decisions,indent=2))



def auxiliary_report(d,arrays,oof_prob,oof_prior,p):
    records=[];confusion=[];paired=[];class_rows=[]
    for sample,role in [('train_in_sample','train'),('source_OOF_raw','train'),('cal_development','cal'),('evaluation','eval')]:
        dd={k:v[d['role']==role] for k,v in d.items()};target,valid=labels(dd);mm=masks(dd);nn=len(target)
        if sample=='source_OOF_raw':prob=oof_prob.astype(float);prior=oof_prior
        else:
            prob=arrays['final'][role+'_P_prob'].astype(float);prior=np.broadcast_to(json.loads((OUT/'final/fit.json').read_text())['train_class_prior'],prob.shape)
        assert np.max(abs(prob.sum(1)-1))<2e-7 and np.all(prob>=0)
        actual=np.maximum(target,0);onehot=np.eye(3)[actual]
        ce=-np.log(np.maximum(prob[np.arange(nn),actual],np.finfo(float).tiny));basece=-np.log(prior[np.arange(nn),actual])
        bs=np.sum((prob-onehot)**2,axis=1);basebs=np.sum((prior-onehot)**2,axis=1);chosen=prob.argmax(1)
        groups,gid,w=boot_weights(dd,p['bootstrap_seed']+{'train':2,'cal':1,'eval':0}[role],500)
        for key,mask in mm.items():
            use=mask&valid;sp=support(dd,use)
            for name,ll,bb,pp in [('P',ce,bs,prob),('train_prior',basece,basebs,prior)]:
                records.append(dict(sample=sample,stratum=key,model=name,**sp,NLL=float(ll[use].mean()) if use.any() else np.nan,Brier=float(bb[use].mean()) if use.any() else np.nan,accuracy=float((pp.argmax(1)[use]==target[use]).mean()) if use.any() else np.nan))
            if not use.any():continue
            den=w@np.bincount(gid[use],minlength=len(groups));good=den>0
            for score,value in [('NLL_gain',basece-ce),('Brier_gain',basebs-bs)]:
                v=w@np.bincount(gid[use],weights=value[use],minlength=len(groups));ng=sp['groups'];lo,hi=np.quantile(v[good]/den[good],[.025,.975]) if ng>=3 and sample!='train_in_sample' else [np.nan,np.nan]
                paired.append(dict(sample=sample,stratum=key,score=score,**sp,gain=float(value[use].mean()),low95=float(lo),high95=float(hi),bootstrap_valid=int(good.sum()) if ng>=3 and sample!='train_in_sample' else 0))
            for c in range(3):
                take=use&(target==c);predicted=use&(chosen==c);hit=take&(chosen==c)
                class_rows.append(dict(sample=sample,stratum=key,truth_class=c,**support(dd,take),predicted_N=int(predicted.sum()),true_positive_N=int(hit.sum()),recall=float(hit.sum()/take.sum()) if take.any() else np.nan,precision=float(hit.sum()/predicted.sum()) if predicted.any() else np.nan,mean_probability_true_class=float(prob[take,c].mean()) if take.any() else np.nan))
                for j in range(3):
                    cell=take&(chosen==j);confusion.append(dict(sample=sample,stratum=key,truth_class=c,predicted_class=j,N=int(cell.sum()),groups=len(np.unique(dd['group'][cell]))))
    table(OUT/'auxiliary_metrics.tsv',records);table(OUT/'auxiliary_paired.tsv',paired);table(OUT/'auxiliary_classes.tsv',class_rows);table(OUT/'auxiliary_confusion.tsv',confusion)


if __name__=='__main__':main()
