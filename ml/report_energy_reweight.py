#!/usr/bin/env python3
"""Full fixed-policy evaluation, source bootstrap and standalone model validation."""
import json
import numpy as np
import xgboost as xgb
from group_risk import training_split
from energy_reweight import *


def references(role, row):
    result={}
    for stage,names in [(68,['C','R']),(69,['C','P'])]:
        a=arrays(REPO/f'ml/artifacts/stage{stage}/final/predictions.npz')
        offsets=json.loads((REPO/f'workbook/stage{stage}_energy_ml/calibration.json').read_text())['offset_log']
        np.testing.assert_array_equal(a[role+'_row'],row)
        for name in names:result[f'stage{stage}_{name}']=a[role+'_'+name+'_raw_log']+offsets[name]
    a=arrays(REPO/'ml/artifacts/stage56/predictions.npz');np.testing.assert_array_equal(a[role+'_row'],row)
    result['F7']=a[role+'_raw_log'].mean(0)+json.loads(str(a['metadata_json']))['offset_log']
    a=arrays(REPO/'ml/artifacts/stage71/comparison.npz');np.testing.assert_array_equal(a[role+'_row'],row)
    result['stage71']=a[role+'_raw_log'].mean(0)+json.loads((REPO/'workbook/stage71_energy_ml/fit.json').read_text())['offset_log']
    return result


def main():
    start=begin();p=json.loads((OUT/'protocol.json').read_text());d=arrays(CACHE/'input.npz')
    tr=d['role']=='train';trainrow=d['row'][tr];seen=np.zeros(len(trainrow),int)
    oof={n:np.full(len(trainrow),np.nan) for n in ARMS};verify=[];fold_metrics=[]
    for job in ['fold0','fold1','fold2','final']:
        use,held,purge=training_split(d,p,job);a=arrays(ART/job/'predictions.npz')
        diag=json.loads((OUT/job/'fit.json').read_text());roles={'held':held} if held is not None else {r:d['role']==r for r in ['train','cal','eval']}
        yy=np.log(d['truth_E_GeV'][use]);base=float(yy.mean())
        for rec in diag['records']:
            n=rec['arm'];w,b,c=weights(d['truth_E_GeV'][use],ARMS[n])
            assert rec['train_N']==int(use.sum()) and rec['purged_N']==int(purge.sum())
            assert rec['base_score']==base and abs(rec['Kish_ESS']-w.sum()**2/(w@w))<1e-8
            model=xgb.Booster(params={'nthread':1});model.load_model(ART/job/(n+'.ubj'))
            assert model.num_boosted_rounds()==400 and model.feature_names==p['features']
            assert json.loads(model.attr('deployment_inputs'))==p['features']
            config=json.loads(model.save_config())['learner']['learner_model_param']
            assert int(config['boost_from_average'])==0
            assert abs(float(config['base_score'])-base)<1e-6
            for role,m in roles.items():
                np.testing.assert_array_equal(a[role+'_row'],d['row'][m])
                restored=model.predict(xgb.DMatrix(d['x'][m],feature_names=p['features'],nthread=1)).astype(float)
                np.testing.assert_array_equal(restored,a[role+'_'+n+'_raw_log'])
            # Independent actual-training risk calculation for every arm and split.
            pred=model.predict(xgb.DMatrix(d['x'][use],feature_names=p['features'],nthread=1)).astype(float)
            dd={k:v[use] for k,v in d.items()}
            for k,m in masks(dd).items():
                value=metrics(yy[m],pred[m])['log_RMSE'];expected=rec['train_log_RMSE'][k]
                if isinstance(value,float):assert abs(value-expected)<1e-12
                else:assert value==expected
            verify.append(dict(job=job,arm=n,trees=400,features=62,prediction_max_abs_diff=0.,
                training_risks_exact=True,weight_ESS_exact=True,unweighted_initial_mean=True,
                train_N=int(use.sum()),held_N=int(held.sum()) if held is not None else 0,purged_N=int(purge.sum()),
                group_overlap=0,known_incoming_overlap=0))
        if held is not None:
            idx=np.searchsorted(trainrow,d['row'][held]);np.testing.assert_array_equal(trainrow[idx],d['row'][held]);seen[idx]+=1
            dd={k:v[held] for k,v in d.items()};yy=np.log(dd['truth_E_GeV'])
            for n in ARMS:
                oof[n][idx]=a['held_'+n+'_raw_log']
                for k,m in masks(dd).items():fold_metrics.append(dict(job=job,arm=n,stratum=k,**support(dd,m),**metrics(yy[m],oof[n][idx][m])))
    assert np.all(seen==1) and all(np.isfinite(v).all() for v in oof.values())
    np.savez_compressed(ART/'oof_predictions.npz',row=trainrow,**{n+'_raw_log':v for n,v in oof.items()})
    a=arrays(ART/'final/predictions.npz');cal=d['role']=='cal'
    offsets={n:float(np.mean(np.log(d['truth_E_GeV'][cal])-a['cal_'+n+'_raw_log'])) for n in ARMS}
    save(OUT/'calibration.json',dict(offset_log=offsets,main_candidate='S_cal',cal_N=8440,unit_global=True))
    records=[];paired=[];source_rows=[];macro_rows=[];replication=[]
    for sample,role in [('train_in_sample','train'),('source_OOF_raw','train'),('cal_development','cal'),('evaluation','eval')]:
        take=d['role']==role;dd={k:v[take] for k,v in d.items()};y=np.log(dd['truth_E_GeV']);mm=masks(dd)
        logs={'mu':np.log(dd['pz']/.8)}
        if sample=='source_OOF_raw':logs.update({n+'_raw':v for n,v in oof.items()})
        else:
            for n in ARMS:
                logs[n+'_raw']=a[role+'_'+n+'_raw_log']
                if role!='train':logs[n+'_cal']=logs[n+'_raw']+offsets[n]
        if role!='train':logs.update(references(role,dd['row']))
        for k,m in mm.items():
            for name,pred in logs.items():records.append(dict(sample=sample,stratum=k,model=name,**support(dd,m),**metrics(y[m],pred[m])))
        for name,pred in logs.items():
            mse=[float(np.mean((pred[mm[k]]-y[mm[k]])**2)) for k in ENERGY if mm[k].any()]
            macro_rows.append(dict(sample=sample,model=name,nonempty_bins=len(mse),macro_log_RMSE=float(np.sqrt(np.mean(mse))),
                                   unit_log_RMSE=float(np.sqrt(np.mean((pred-y)**2)))))
        for g in np.unique(dd['group']):
            for k in LOW+list(COST)+['E3200_6400','input_missing']:
                m=mm[k]&(dd['group']==g)
                if m.any():
                    for n in ['mu','U_raw','S_raw','F_raw']+(['U_cal','S_cal','F_cal','F7'] if role!='train' else []):
                        source_rows.append(dict(sample=sample,group=str(g),stratum=k,model=n,**support(dd,m),**metrics(y[m],logs[n][m])))
        if sample=='train_in_sample':continue
        groups,gid,w=boot_weights(dd,p['bootstrap_seed']+{'train':2,'cal':1,'eval':0}[role],500)
        comparisons=[('S_raw','U_raw'),('F_raw','U_raw'),('S_raw','mu'),('F_raw','mu')]
        if role!='train':
            comparisons += [('S_cal','U_cal'),('F_cal','U_cal')]
            comparisons += [(n,r) for n in ['U_raw','U_cal','S_raw','S_cal','F_raw','F_cal'] for r in ['mu','F7','stage68_C','stage68_R','stage69_C','stage69_P','stage71']]
        squared={n:(pred-y)**2 for n,pred in logs.items()}
        binsums={k:{n:w@np.bincount(gid[m],weights=v[m],minlength=len(groups)) for n,v in squared.items()} for k,m in mm.items()}
        bincounts={k:w@np.bincount(gid[m],minlength=len(groups)) for k,m in mm.items()}
        for k,m in mm.items():
            if not m.any():continue
            den=bincounts[k];sums=binsums[k]
            tailsums={n:{t:w@np.bincount(gid[m],weights=indicator(logs[n][m]-y[m],t).astype(float),minlength=len(groups)) for t in TAILS} for n in logs}
            for n,ref in comparisons:
                good=(den>0)&(sums[ref]>0);valid=int(good.sum()) if len(np.unique(dd['group'][m]))>=3 else 0
                ratio=float(np.sqrt(squared[n][m].mean()/squared[ref][m].mean()))
                rr=np.sqrt(sums[n][good]/sums[ref][good]);lo,hi=np.quantile(rr,[.025,.975]) if valid else [np.nan,np.nan]
                z=dict(sample=sample,stratum=k,model=n,reference=ref,**support(dd,m),RMSE_ratio=ratio,
                       RMSE_ratio_low95=float(lo),RMSE_ratio_high95=float(hi),gain_pct=100*(1-ratio),
                       gain_low95_pct=100*(1-float(hi)),bootstrap_valid=valid,bootstrap_invalid=500-valid)
                for t in TAILS:
                    value=100*(tailsums[n][t][good]-tailsums[ref][t][good])/den[good]
                    low,high=np.quantile(value,[.025,.975]) if valid else [np.nan,np.nan]
                    z[t+'_delta_pp']=float(100*(indicator(logs[n][m]-y[m],t).mean()-indicator(logs[ref][m]-y[m],t).mean()))
                    z[t+'_low95_pp']=float(low);z[t+'_high95_pp']=float(high)
                paired.append(finite(z))
            rep=np.repeat(np.flatnonzero(m),w[0,gid[m]])
            if len(rep):
                direct=np.sqrt(squared['S_raw'][rep].mean()/squared['U_raw'][rep].mean())
                replication.append(abs(float(direct-np.sqrt(sums['S_raw'][0]/sums['U_raw'][0]))))
        # Macro bootstraps use the exact same seven fixed energy bins, no favorable subset.
        nonempty=[k for k in ENERGY if mm[k].any()]
        good=np.logical_and.reduce([bincounts[k]>0 for k in nonempty])
        for n,ref in comparisons:
            bn=sum(binsums[k][n][good]/bincounts[k][good] for k in nonempty)/len(nonempty)
            br=sum(binsums[k][ref][good]/bincounts[k][good] for k in nonempty)/len(nonempty)
            rr=np.sqrt(bn/br);lo,hi=np.quantile(rr,[.025,.975]) if len(rr) else [np.nan,np.nan]
            central=np.sqrt(np.mean([squared[n][mm[k]].mean() for k in nonempty])/np.mean([squared[ref][mm[k]].mean() for k in nonempty]))
            paired.append(dict(sample=sample,stratum='macro',model=n,reference=ref,N=len(y),groups=len(groups),
                sources=len(np.unique(dd['source'])),unique_incoming=len(np.unique(dd['incoming'],axis=0)),RMSE_ratio=float(central),
                RMSE_ratio_low95=float(lo),RMSE_ratio_high95=float(hi),gain_pct=float(100*(1-central)),gain_low95_pct=float(100*(1-hi)),
                bootstrap_valid=int(good.sum()),bootstrap_invalid=int(500-good.sum()),
                **{t+s:'不适用' for t in TAILS for s in ['_delta_pp','_low95_pp','_high95_pp']}))
    for name,data in [('metrics',records),('paired',paired),('macro',macro_rows),('fold_metrics',fold_metrics),('source_metrics',source_rows)]:table(OUT/(name+'.tsv'),data)
    decisions={}
    for n in ['U_raw','U_cal','S_raw','S_cal','F_raw','F_cal']:
        def get(k,ref):return next(z for z in paired if z['sample']=='evaluation' and z['stratum']==k and z['model']==n and z['reference']==ref)
        recovery={k:get(k,'mu')['RMSE_ratio_high95']<=1.05 for k in LOW}
        breakthrough={k:get(k,'mu')['gain_low95_pct']>0 for k in LOW}
        protection={k:get(k,'F7')['RMSE_ratio_high95']<=v for k,v in COST.items()}
        tails={k:{t:get(k,'F7')[t+'_high95_pp']<=2 for t in TAILS[:3]} for k in LOW+list(COST)}
        decisions[n]=dict(recovery=recovery,breakthrough=breakthrough,protection=protection,tail50=tails,
            pass_all=all(recovery.values()) and all(protection.values()) and all(all(v.values()) for v in tails.values()))
    save(OUT/'decisions.json',dict(main_candidate='S_cal',deployment='retain F7',versions=decisions))
    save(OUT/'validation.json',dict(models=verify,OOF_exactly_once_N=int(seen.sum()),OOF_missing=0,
        bootstrap_replication_max_abs_diff=max(replication),eligible_missing_N=[int(d['missing'][d['role']==r].sum()) for r in ['train','cal','eval']],
        formal_fits=12,additional_scientific_fits=0,bootstrap_repeats=500,bootstrap_scope='paired component-stratified conservative source, fixed predictions/offsets; excludes retraining, full genealogy, detector/interaction and research selection; development cal/eval',
        truth_free_standalone_inputs=True,**resources(start)))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    for ax,sample in zip(axes,['source_OOF_raw','evaluation']):
        for name in (['mu','U_raw','S_raw','F_raw'] if sample=='source_OOF_raw' else ['mu','F7','U_cal','S_cal','F_cal']):
            vals=[next(r['log_RMSE'] for r in records if r['sample']==sample and r['stratum']==k and r['model']==name) for k in ENERGY]
            ax.plot(np.arange(7),vals,'o-',label=name,ms=3)
        ax.set_xticks(np.arange(7),[k[1:] for k in ENERGY],rotation=40);ax.set_ylabel('log-RMSE');ax.set_title(sample);ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.tight_layout();fig.savefig(OUT/'energy_policies.png',dpi=150);plt.close(fig)
    print(json.dumps(dict(offsets=offsets,decisions=decisions,**resources(start)),indent=2))


if __name__=='__main__':main()
