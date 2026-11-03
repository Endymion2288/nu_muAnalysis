"""Stage80 matched-risk evaluation, fixed source intervals and model replay."""
import gzip
import json
import numpy as np
import xgboost as xgb
from pulse_ablation import *

ENERGY=['E50_100','E100_200','E200_400','E400_800','E800_1600','E1600_3200','E3200_6400']


def reference(role,row):
    f=arrays(REPO/'ml/artifacts/stage56/predictions.npz');np.testing.assert_array_equal(f[role+'_row'],row)
    return f[role+'_raw_log'].mean(0)+json.loads(str(f['metadata_json']))['offset_log']


def main():
    start=begin();d=data();p=json.loads((OUT/'protocol.json').read_text());tr=d['role']=='train';trainrow=d['row'][tr]
    seen=np.zeros(len(trainrow),int);oof={arm:np.full(len(trainrow),np.nan) for arm in ARMS};verification=[];foldrows=[]
    for job in JOBS:
        use,held,purge=training_split(d,p,job);a=arrays(ART/job/'predictions.npz');fit=json.loads((OUT/job/'fit.json').read_text())
        roles={'held':held} if held is not None else {r:d['role']==r for r in ['train','cal','eval']};y=np.log(d['truth_E_GeV'][use])
        for rec in fit['records']:
            arm=rec['arm'];features=p['features_by_arm'][arm];xx=matrix(d,arm)
            assert rec['train_N']==int(use.sum()) and rec['purged_N']==int(purge.sum()) and rec['base_score']==float(y.mean())
            assert rec['params']==dict(p['xgboost'],seed=p['seed'],base_score=float(y.mean()),boost_from_average=0)
            model=xgb.Booster(params={'nthread':1});model.load_model(ART/job/(arm+'.ubj'))
            assert model.num_boosted_rounds()==400 and model.feature_names==features
            assert json.loads(model.attr('deployment_inputs'))==features
            config=json.loads(model.save_config())['learner']['learner_model_param'];assert int(config['boost_from_average'])==0
            for role,m in roles.items():
                np.testing.assert_array_equal(a[role+'_row'],d['row'][m]);pred=model.predict(xgb.DMatrix(xx[m],feature_names=features,nthread=1)).astype(float)
                np.testing.assert_array_equal(pred,a[role+'_'+arm+'_raw_log']);assert np.isfinite(pred).all()
                if role=='held':oof[arm][np.searchsorted(trainrow,d['row'][held])]=pred
            pred=model.predict(xgb.DMatrix(xx[use],feature_names=features,nthread=1)).astype(float);dd={k:v[use] for k,v in d.items()}
            for key,m in diagnostic_masks(dd).items():assert metrics(y[m],pred[m])['log_RMSE']==rec['train_log_RMSE'][key]
            verification.append(dict(job=job,arm=arm,features=len(features),trees=400,predictions_exact=True,train_risks_exact=True,
                train_N=int(use.sum()),held_N=int(held.sum()) if held is not None else 0,purged_N=int(purge.sum()),group_overlap=0,incoming_overlap=0))
        if held is not None:
            pos=np.searchsorted(trainrow,d['row'][held]);seen[pos]+=1;dd={k:v[held] for k,v in d.items()};yy=np.log(dd['truth_E_GeV'])
            for arm in ARMS:
                for key,m in diagnostic_masks(dd).items():foldrows.append(dict(job=job,arm=arm,stratum=key,**support(dd,m),**metrics(yy[m],oof[arm][pos][m])))
    assert np.all(seen==1) and all(np.isfinite(v).all() for v in oof.values())
    np.savez_compressed(ART/'oof_predictions.npz',row=trainrow,**{arm+'_raw_log':v for arm,v in oof.items()})
    a=arrays(ART/'final/predictions.npz');cal=d['role']=='cal';offsets={arm:float(np.mean(np.log(d['truth_E_GeV'][cal])-a['cal_'+arm+'_raw_log'])) for arm in ARMS}
    save(OUT/'calibration.json',dict(offset_log=offsets,cal_N=8440,main_candidate='P_cal',unit_global=True))
    records=[];paired=[];sources=[];shape_rows=[];macro=[];replication=[]
    for sample,role in [('train_in_sample','train'),('source_OOF_raw','train'),('cal_development','cal'),('evaluation','eval')]:
        take=d['role']==role;dd={k:v[take] for k,v in d.items()};y=np.log(dd['truth_E_GeV']);mm=diagnostic_masks(dd)
        logs={'mu':np.log(dd['pz']/.8)}
        for arm in ARMS:
            logs[arm+'_raw']=oof[arm] if sample=='source_OOF_raw' else a[role+'_'+arm+'_raw_log']
            if role!='train':logs[arm+'_cal']=logs[arm+'_raw']+offsets[arm]
        if role!='train':logs['F7']=reference(role,dd['row'])
        for key,m in mm.items():
            for name,log in logs.items():records.append(dict(sample=sample,stratum=key,model=name,**support(dd,m),**metrics(y[m],log[m])))
        for name,log in logs.items():
            loss=[np.mean((log[mm[k]]-y[mm[k]])**2) for k in ENERGY if mm[k].any()]
            macro.append(dict(sample=sample,model=name,nonempty_bins=len(loss),macro_log_RMSE=float(np.sqrt(np.mean(loss)))))
        for key,m in mm.items():
            for j,detector in enumerate(SCINTILLATORS):
                shape_rows.append(dict(sample=sample,stratum=key,detector=detector,N=int(m.sum()),valid_N=int(dd['shape_valid'][m,j].sum())))
        for g in np.unique(dd['group']):
            for key in LOW+list(COST)+['pz50_100_E200_inf','E3200_6400','input_missing','scint_overflow','scint_weak']:
                m=mm[key]&(dd['group']==g)
                if not m.any():continue
                for name,log in logs.items():sources.append(dict(sample=sample,group=str(g),stratum=key,model=name,**support(dd,m),**metrics(y[m],log[m])))
        if sample=='train_in_sample':continue
        seed=p['bootstrap_seed']+{'train':1,'cal':2,'eval':0}[role];groups,gid,w=boot_weights(dd,seed,500)
        comparisons=[('P_raw','U_raw'),('P_raw','mu'),('U_raw','mu')]
        if role!='train':comparisons += [('P_cal','U_cal')]+[(name,ref) for name in ['U_raw','U_cal','P_raw','P_cal'] for ref in ['mu','F7']]
        comparisons=list(dict.fromkeys(comparisons))
        squared={name:(log-y)**2 for name,log in logs.items()}
        sums={key:{name:w@np.bincount(gid[m],weights=v[m],minlength=len(groups)) for name,v in squared.items()} for key,m in mm.items()}
        counts={key:w@np.bincount(gid[m],minlength=len(groups)) for key,m in mm.items()}
        for key,m in mm.items():
            if not m.any():continue
            den=counts[key];tails={name:{t:w@np.bincount(gid[m],weights=indicator(log[m]-y[m],t),minlength=len(groups)) for t in TAILS[:3]} for name,log in logs.items()}
            for name,ref in comparisons:
                good=(den>0)&(sums[key][ref]>0);valid=int(good.sum()) if len(np.unique(dd['group'][m]))>=3 else 0
                ratio=np.sqrt(sums[key][name][good]/sums[key][ref][good]);ci=np.quantile(ratio,[.025,.975]) if valid else [np.nan,np.nan]
                r=dict(sample=sample,stratum=key,model=name,reference=ref,**support(dd,m),RMSE_ratio=float(np.sqrt(squared[name][m].mean()/squared[ref][m].mean())),
                    RMSE_ratio_low95=float(ci[0]),RMSE_ratio_high95=float(ci[1]),bootstrap_valid=valid,bootstrap_invalid=500-valid)
                for tail in TAILS[:3]:
                    values=100*(tails[name][tail][good]-tails[ref][tail][good])/den[good];lo,hi=np.quantile(values,[.025,.975]) if valid else [np.nan,np.nan]
                    r[tail+'_delta_pp']=float(100*(indicator(logs[name][m]-y[m],tail).mean()-indicator(logs[ref][m]-y[m],tail).mean()))
                    r[tail+'_low95_pp']=float(lo);r[tail+'_high95_pp']=float(hi)
                paired.append(finite(r))
            if key in ['all','pz50_100','E50_100','E100_200']:
                # Retain primary-control draw vectors for an independent event-expansion check.
                replication.append(dict(sample=sample,stratum=key,seed=seed,draws=np.sqrt(sums[key]['P_raw']/sums[key]['U_raw']).tolist()))
    for name,rows in [('metrics',records),('paired',paired),('fold_metrics',foldrows),('shape_validity',shape_rows),('macro',macro)]:table(OUT/(name+'.tsv'),rows)
    table(OUT/'source_metrics.tsv',sources)
    with (OUT/'source_metrics.tsv').open('rb') as stream,gzip.open(OUT/'source_metrics.tsv.gz','wb') as dest:dest.write(stream.read())
    (OUT/'source_metrics.tsv').unlink()
    save(OUT/'bootstrap_primary_draws.json',replication)
    def find(model,key,ref,sample='evaluation'):return next(r for r in paired if r['sample']==sample and r['model']==model and r['stratum']==key and r['reference']==ref)
    decisions={}
    for name in ['U_raw','U_cal','P_raw','P_cal']:
        recovery={k:find(name,k,'mu')['RMSE_ratio_high95']<=1.05 for k in LOW}
        protection={k:find(name,k,'F7')['RMSE_ratio_high95']<=v for k,v in COST.items()}
        tails={k:{t:find(name,k,'F7')[t+'_high95_pp']<=2 for t in TAILS[:3]} for k in LOW+list(COST)}
        decisions[name]=dict(recovery=recovery,protection=protection,tail50=tails,pass_all=all(recovery.values()) and all(protection.values()) and all(all(v.values()) for v in tails.values()))
    increment={sample:find('P_raw','pz50_100','U_raw',sample) for sample in ['source_OOF_raw','evaluation']}
    save(OUT/'decisions.json',dict(main_candidate='P_cal',deployment='retain F7' if not decisions['P_cal']['pass_all'] else 'research candidate P_cal; independent confirmation required',versions=decisions,primary_increment=increment))
    directions=[]
    for key in LOW+list(COST)+['pz50_100_E200_inf']:
        available=[r for r in sources if r['sample']=='evaluation' and r['stratum']==key];by={}
        for r in available:by.setdefault(r['group'],{})[r['model']]=r['log_RMSE']
        directions.append(dict(stratum=key,groups=len(by),P_cal_better_than_U_cal=sum(v['P_cal']<v['U_cal'] for v in by.values()),P_cal_better_than_F7=sum(v['P_cal']<v['F7'] for v in by.values())))
    save(OUT/'model_validation.json',dict(models=verification,OOF_exactly_once_N=int(seen.sum()),formal_fits=8,extra_pilot_fits=0,source_directions=directions,**resources(start)))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(10.5,4.2))
    for ax,sample in zip(axes,['source_OOF_raw','evaluation']):
        for model in (['mu','U_raw','P_raw'] if sample=='source_OOF_raw' else ['mu','F7','U_cal','P_cal']):
            values=[next(r['log_RMSE'] for r in records if r['sample']==sample and r['stratum']==key and r['model']==model) for key in ENERGY]
            ax.plot(range(7),values,'o-',label=model,ms=3)
        ax.set_xticks(range(7),[k[1:] for k in ENERGY],rotation=35);ax.set_xlabel('True energy (GeV)');ax.set_ylabel('log-RMSE');ax.set_title(sample);ax.legend(fontsize=8);ax.grid(alpha=.2)
    fig.tight_layout();fig.savefig(OUT/'pulse_ablation.png',dpi=150);fig.savefig(OUT/'pulse_ablation.pdf');plt.close(fig)
    print(json.dumps(dict(offsets=offsets,primary_increment=increment,decisions=decisions,**resources(start)),indent=2),flush=True)


if __name__=='__main__':main()
