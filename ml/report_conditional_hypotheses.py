#!/usr/bin/env python3
"""Source-paired proper scores, query calibration and independent stage74 readback."""
import json
import numpy as np
import xgboost as xgb
from group_risk import training_split, inputs as original_inputs
from conditional_hypotheses import *


def main():
    start=begin();p=json.loads((OUT/'protocol.json').read_text())
    d=arrays(CACHE/'input.npz') if (CACHE/'input.npz').exists() else original_inputs()
    train=d['role']=='train';trainrow=d['row'][train];seen=np.zeros(len(trainrow),int)
    oof={n:np.full((len(trainrow),2),np.nan) for n in ARMS}
    negative=np.full(len(trainrow),np.nan);true_q=np.full(len(trainrow),np.nan)
    verification=[];fold_metrics=[];qdraw_rows=[];zero_events=[]
    for job in JOBS:
        tr,held,purge=training_split(d,p,job);a=arrays(ART/job/'predictions.npz')
        diag=json.loads((OUT/job/'fit.json').read_text());count,mass=proposal(d['pz'][tr],d['truth_E_GeV'][tr]);j=JOBS.index(job)
        np.testing.assert_array_equal(a['proposal_counts'],count);np.testing.assert_array_equal(a['proposal_mass'],mass)
        train_neg=draw(d['pz'][tr],mass,np.random.default_rng(p['seed']+j))
        roles={'held':held} if held is not None else {r:d['role']==r for r in ['train','cal','eval']}
        rng=np.random.default_rng(p['seed']+j+100)
        for r,m in roles.items():
            expected=train_neg if r=='train' else draw(d['pz'][m],mass,rng)
            np.testing.assert_array_equal(a[r+'_row'],d['row'][m]);np.testing.assert_array_equal(a[r+'_negative_log_E'],expected)
            density=proposal_density(d['pz'][m],np.log(d['truth_E_GeV'][m]),mass)
            np.testing.assert_array_equal(a[r+'_true_q_density'],density)
            for ii in np.flatnonzero(m)[density==0]:
                zero_events.append(dict(job=job,role=r,row=int(d['row'][ii]),group=str(d['group'][ii]),source=int(d['source'][ii]),
                    E_GeV=float(d['truth_E_GeV'][ii]),pz_GeV=float(d['pz'][ii]),confirmed=bool(d['confirmed'][ii])))
            pb=np.searchsorted(PZ_EDGES,d['pz'][m],side='right')-1
            eb=np.searchsorted(LOG_EDGES,expected,side='right')-1
            for b in range(7):
                for e in range(7):qdraw_rows.append(dict(job=job,role=r,pz_bin=b,energy_bin=e,
                    negative_N=int(((pb==b)&(eb==e)).sum()),expected_mass=float(mass[b,e]),
                    mean_negative_logE=float(expected[(pb==b)&(eb==e)].mean()) if ((pb==b)&(eb==e)).any() else '未测量'))
        for rec in diag['records']:
            n=rec['arm'];names=([p['features'][0]] if n=='M' else p['features'])+[QUERY]
            assert rec['train_N']==int(tr.sum()) and rec['purged_N']==int(purge.sum())
            model=xgb.Booster(params={'nthread':1});model.load_model(ART/job/(n+'.ubj'))
            assert model.num_boosted_rounds()==400 and model.feature_names==names
            assert json.loads(model.attr('reco_inputs'))==names[:-1] and model.attr('query_input')==QUERY
            config=json.loads(model.save_config())['learner']['learner_model_param']
            assert int(config['boost_from_average'])==0 and float(config['base_score'])==.5
            for r,m in roles.items():
                xx,_=paired_matrix(d['x'][m],np.log(d['truth_E_GeV'][m]),a[r+'_negative_log_E'],n)
                value=model.predict(xgb.DMatrix(xx,feature_names=names,nthread=1),output_margin=True).reshape(-1,2).astype(float)
                np.testing.assert_array_equal(value,a[r+'_'+n+'_logits'])
            xx,_=paired_matrix(d['x'][tr],np.log(d['truth_E_GeV'][tr]),train_neg,n)
            value=model.predict(xgb.DMatrix(xx,feature_names=names,nthread=1),output_margin=True).reshape(-1,2).astype(float)
            for key,v in rec['train_scores'].items():assert abs(float(losses(value)[key].mean())-v)<1e-12
            # Negative candidate inference cannot depend on any true-energy label.
            first=np.flatnonzero(tr)[:32];candidate=train_neg[:32]
            query=query_matrix(d['x'][first],candidate,n)
            result=model.predict(xgb.DMatrix(query,feature_names=names,nthread=1),output_margin=True)
            np.testing.assert_array_equal(result,value[:32,1].astype('float32'))
            verification.append(dict(job=job,arm=n,trees=400,reco_features=len(names)-1,query_features=1,
                standalone_prediction_max_abs_diff=0.,proposal_and_pairing_exact=True,train_risks_exact=True,
                implicit_unit_weights=True,train_N=int(tr.sum()),purged_N=int(purge.sum()),
                group_overlap=0,known_incoming_overlap=0,query_path_reads_no_true_label=True))
        if held is not None:
            idx=np.searchsorted(trainrow,d['row'][held]);np.testing.assert_array_equal(trainrow[idx],d['row'][held]);seen[idx]+=1
            negative[idx]=a['held_negative_log_E'];true_q[idx]=a['held_true_q_density']
            dd={k:v[held] for k,v in d.items()}
            for n in ARMS:
                oof[n][idx]=a['held_'+n+'_logits'];v=losses(oof[n][idx])
                for k,m in strata(dd,p['Timing_quartiles_pC']).items():
                    fold_metrics.append(dict(job=job,arm=n,stratum=k,**support(dd,m),zero_q_N=int((m&(a['held_true_q_density']==0)).sum()),
                        **{key:float(v[key][m].mean()) if m.any() else '未测量' for key in ['BCE','positive_BCE','negative_BCE','Brier']}))
    assert np.all(seen==1) and all(np.isfinite(v).all() for v in oof.values())
    np.savez_compressed(ART/'oof_predictions.npz',row=trainrow,negative_log_E=negative,true_q_density=true_q,
                        **{n+'_logits':v for n,v in oof.items()})
    final=arrays(ART/'final/predictions.npz');metrics=[];paired=[];sources=[];reliability=[];checks=[]
    for sample,role in [('train_in_sample','train'),('source_OOF','train'),('cal_development','cal'),('evaluation','eval')]:
        take=d['role']==role;dd={k:v[take] for k,v in d.items()};mm=strata(dd,p['Timing_quartiles_pC'])
        logits=oof if sample=='source_OOF' else {n:final[role+'_'+n+'_logits'] for n in ARMS}
        density=true_q if sample=='source_OOF' else final[role+'_true_q_density']
        scores={n:losses(v) for n,v in logits.items()}
        for k,m in mm.items():
            for n in ARMS:
                metrics.append(dict(sample=sample,stratum=k,model=n,**support(dd,m),
                    synthetic_negative_N=int(m.sum()),zero_q_N=int((m&(density==0)).sum()),
                    **{key:float(scores[n][key][m].mean()) if m.any() else '未测量' for key in ['BCE','positive_BCE','negative_BCE','Brier']}))
                probability=scores[n]['probability'][m].ravel();target=np.tile([1.,0.],int(m.sum()))
                digit=np.minimum((10*probability).astype(int),9)
                assert np.isfinite(probability).all() and len(probability)==2*m.sum()
                for b in range(10):
                    mask=digit==b;reliability.append(dict(sample=sample,stratum=k,model=n,bin=b,
                        lower=b/10,upper=(b+1)/10,pair_rows=int(mask.sum()),real_X_stratum_N=int(m.sum()),
                        contributing_real_X_N=len(np.unique(np.flatnonzero(mask)//2)),
                        predicted_probability=float(probability[mask].mean()) if mask.any() else '未测量',
                        observed_positive_fraction=float(target[mask].mean()) if mask.any() else '未测量'))
        for g in np.unique(dd['group']):
            for k in ['all','pz50_100']+CRITICAL+['E3200_6400','input_missing']:
                m=mm[k]&(dd['group']==g)
                if not m.any():continue
                for n in ARMS:sources.append(dict(sample=sample,group=str(g),stratum=k,model=n,**support(dd,m),zero_q_N=int((m&(density==0)).sum()),
                    **{key:float(scores[n][key][m].mean()) for key in ['BCE','positive_BCE','negative_BCE','Brier']}))
        if sample=='train_in_sample':continue
        groups,gid,w=boot_weights(dd,p['bootstrap_seed']+{'train':2,'cal':1,'eval':0}[role],500)
        for k,m in mm.items():
            if not m.any():continue
            count=np.bincount(gid[m],minlength=len(groups));den=w@count
            valid=(den>0) if len(np.unique(dd['group'][m]))>=3 else np.zeros(500,bool)
            for key in ['BCE','positive_BCE','negative_BCE','Brier']:
                delta=scores['M'][key]-scores['X'][key]
                total=w@np.bincount(gid[m],weights=delta[m],minlength=len(groups))
                vals=total[valid]/den[valid]
                lo,hi=np.quantile(vals,[.025,.975]) if len(vals) else [np.nan,np.nan]
                paired.append(finite(dict(sample=sample,stratum=k,score=key,model='X',reference='M',**support(dd,m),
                    zero_q_N=int((m&(density==0)).sum()),gain=float(delta[m].mean()),low95=float(lo),high95=float(hi),
                    bootstrap_valid=int(valid.sum()),bootstrap_invalid=int(500-valid.sum()))))
                for draw_index in [0,173,499]:
                    rep=np.repeat(np.flatnonzero(m),w[draw_index,gid[m]])
                    if len(rep):checks.append(abs(float(delta[rep].mean()-total[draw_index]/den[draw_index])))
    for name,value in [('metrics',metrics),('paired',paired),('source_metrics',sources),('reliability',reliability),('fold_metrics',fold_metrics),('negative_draws',qdraw_rows)]:table(OUT/(name+'.tsv'),value)
    table(OUT/'zero_q_events.tsv',zero_events)
    def result(sample,k):return next(v for v in paired if v['sample']==sample and v['stratum']==k and v['score']=='BCE')
    primary={sample:result(sample,'pz50_100')['low95']>0 for sample in ['source_OOF','evaluation']}
    critical=[]
    for sample in ['source_OOF','evaluation']:
        for k in CRITICAL:
            v=result(sample,k);critical.append(dict(sample=sample,stratum=k,N=v['N'],zero_q_N=v['zero_q_N'],
                wholly_negative_gain=isinstance(v['high95'],float) and v['high95']<0,
                inconclusive=isinstance(v['low95'],float) and v['low95']<=0<=v['high95']))
    coverage=all(v['zero_q_N']==0 and v['N']>0 for v in critical)
    harm=any(v['wholly_negative_gain'] for v in critical)
    decision=dict(deployment='retain F7',energy_point_or_posterior_recovery_measured=False,primary_lower95_positive=primary,
        critical=critical,critical_support_covered=coverage,any_critical_wholly_negative_gain=harm,
        pass_frozen_information_contract=all(primary.values()) and coverage and not harm,
        interpretation='pair-experiment discrimination only; no energy-predictor success or information-limit claim')
    save(OUT/'decisions.json',decision)
    save(OUT/'validation.json',dict(passed=True,models=verification,OOF_exactly_once_N=int(seen.sum()),
        eligible_missing_N=[int(d['missing'][d['role']==r].sum()) for r in ['train','cal','eval']],
        zero_q_OOF_N=int((true_q==0).sum()),bootstrap_event_replication_draws=[0,173,499],
        bootstrap_replication_max_abs_diff=max(checks),formal_fits=8,additional_scientific_fits=0,
        query_only_reco_and_hypothesis=True,bootstrap_repeats=500,**resources(start)))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    keys=['pz50_100','E50_100','E100_200','pz50_100_E200_inf','high_y','unconfirmed','all']
    for ax,sample in zip(axes,['source_OOF','evaluation']):
        rr=[result(sample,k) for k in keys];gain=np.array([v['gain'] for v in rr])
        ax.errorbar(np.arange(len(keys)),gain,yerr=[gain-np.array([v['low95'] for v in rr]),np.array([v['high95'] for v in rr])-gain],fmt='o',capsize=3)
        ax.axhline(0,color='gray',lw=.8);ax.set_xticks(np.arange(len(keys)),keys,rotation=40,ha='right')
        ax.set_ylabel('BCE gain M - X [nat / real X]');ax.set_title(sample);ax.grid(alpha=.2)
    fig.tight_layout();fig.savefig(OUT/'conditional_information.png',dpi=150);plt.close(fig)
    save(OUT/'report_resources.json',dict(**resources(start),scope='complete report including standalone readback,bootstrap and figure',physical_EOS_network_bytes='未测量'))
    print(json.dumps(dict(decision=decision,**resources(start)),indent=2))


if __name__=='__main__':main()
