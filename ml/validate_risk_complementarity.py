#!/usr/bin/env python3
"""Independent nested row audits, saved base replay and direct statistics."""
import csv
import xgboost as xgb
from report_risk_complementarity import data,logs_for,references
from risk_complementarity import *


def scalar_leaf(x,part):
    out=[]
    for row in x:
        missing=~np.isfinite(row);v=np.r_[np.where(missing,part['median'],row),missing].astype('float32');node=0
        while part['children_left'][node]>=0:
            go=v[part['feature'][node]]<=part['threshold'][node]
            node=(part['children_left'] if go else part['children_right'])[node]
        out.append(part['leaf_ids'].index(node))
    return np.array(out)


def main():
    start=begin();p=json.loads((OUT/'protocol.json').read_text());d=data();tr=d['role']=='train';alltrain=np.flatnonzero(tr)
    fold={str(g):int(v) for g,v in p['fold_by_group'].items()};base_checks=[];head_checks=[];riskdiff=0.;min_eigen=0.;max_slack_violation=0.
    for job in JOBS:
        outer,held,_=training_split(d,p,job);ht=arrays(ART/job/'head_training.npz');head=json.loads((ART/job/'head.json').read_text());a=arrays(ART/job/'predictions.npz')
        np.testing.assert_array_equal(ht['row'],d['row'][outer]);h=ht['h'];yy=np.log(d['truth_E_GeV'][outer]);xx=d['x'][outer]
        if held is not None:
            # Reconstruct both levels independently using source identities and exact raw tuples.
            outfold=int(job[-1]);evalix=np.array([i for i in alltrain if fold[str(d['group'][i])]==outfold],int)
            evalkeys=set(map(tuple,d['incoming'][evalix]));outerix=np.array([i for i in alltrain if fold[str(d['group'][i])]!=outfold and tuple(d['incoming'][i]) not in evalkeys],int)
            np.testing.assert_array_equal(outerix,np.flatnonzero(outer));seen=np.zeros(len(h),int)
            diag=json.loads((OUT/job/'fit.json').read_text())
            for k in sorted({fold[str(g)] for g in d['group'][outerix]}):
                ih=np.array([i for i in outerix if fold[str(d['group'][i])]==k],int);keys=set(map(tuple,d['incoming'][ih]))
                it=np.array([i for i in outerix if fold[str(d['group'][i])]!=k and tuple(d['incoming'][i]) not in keys],int)
                assert not set(d['group'][it])&set(d['group'][ih]) and not set(map(tuple,d['incoming'][it]))&keys
                assert not set(map(tuple,d['incoming'][it]))&evalkeys
                idx=np.searchsorted(ht['row'],d['row'][ih]);seen[idx]+=1
                for j,arm in enumerate(['U','F']):
                    rec=next(v for v in diag['base_records'] if v['inner']==k and v['arm']==arm)
                    assert rec['train_N']==len(it) and rec['held_N']==len(ih)
                    assert rec['base_score']==float(np.log(d['truth_E_GeV'][it]).mean())
                    w,_,counts=weights(d['truth_E_GeV'][it],j);assert rec['bin_counts']==counts.tolist();assert abs(rec['Kish_ESS']-w.sum()**2/(w@w))<1e-8
                    model=xgb.Booster(params={'nthread':1});model.load_model(ART/job/f'inner{k}_{arm}.ubj')
                    assert model.num_boosted_rounds()==400 and model.feature_names==p['features']
                    assert model.attr('stage78_outer')==job and model.attr('stage78_inner')==str(k) and model.attr('stage78_arm')==arm
                    config=json.loads(model.save_config())['learner']['learner_model_param'];assert int(config['boost_from_average'])==0
                    pred=model.predict(xgb.DMatrix(d['x'][ih],feature_names=p['features'],nthread=1)).astype(float)
                    np.testing.assert_array_equal(pred,h[idx,j]);base_checks.append(dict(job=job,inner=k,arm=arm,N=len(ih),model_reload_bitwise=True))
            assert np.all(seen==1)
        else:np.testing.assert_array_equal(h,d['old_oof_h'][outer])
        np.testing.assert_array_equal(h[:,2],np.log(d['pz'][outer]/.8))
        part=head['partition'];med=np.array([float(np.median(c[np.isfinite(c)])) if np.isfinite(c).any() else 0. for c in xx.T])
        np.testing.assert_array_equal(med,part['median'])
        delta=np.column_stack(((h[:,0]-yy)**2-(h[:,1]-yy)**2,(h[:,0]-yy)**2-(h[:,2]-yy)**2))
        np.testing.assert_array_equal(np.sqrt(np.mean(delta*delta,axis=0)),part['target_RMS'])
        assert part['training_N']==len(xx)
        ix=np.unique(np.r_[np.linspace(0,len(xx)-1,64).astype(int),np.flatnonzero(~np.isfinite(xx).all(1))])
        np.testing.assert_array_equal(scalar_leaf(xx[ix],part),route(xx[ix],part))
        for arm in ARMS:
            sol=head['solutions'][arm];assert sol['solved'] and sol['secondary_solved'] and all(v['qualified'] for v in sol['records'])
            leaf=np.zeros(len(xx),int) if arm=='Q0' else route(xx,part);ww=np.array(sol['weights'])
            pred=np.sum(h*ww[leaf],axis=1);np.testing.assert_allclose(pred,a['head_train_'+arm+'_raw_log'],rtol=0,atol=2e-15)
            for key,m in diagnostic_masks(subset(d,outer)).items():
                if key not in LOW+list(COST):continue
                error=h[m]-yy[m,None];C=np.array([error[leaf[m]==l].T@error[leaf[m]==l]/m.sum() for l in range(len(ww))])
                min_eigen=min(min_eigen,float(np.linalg.eigvalsh(C).min()))
                matrix=float(sum(ww[l]@C[l]@ww[l] for l in range(len(ww))));direct=float(np.dot(pred[m]-yy[m],pred[m]-yy[m])/m.sum());riskdiff=max(riskdiff,abs(matrix-direct))
                den=float(np.mean((h[m,2 if key in LOW else 0]-yy[m])**2));actual=direct/den
                riskdiff=max(riskdiff,abs(actual-sol['records'][-1]['normalized_MSE'][key]))
                if key in COST:max_slack_violation=max(max_slack_violation,actual-COST[key]**2)
            assert np.all(ww>=0) and np.max(abs(ww.sum(1)-1))<1e-8
        head_checks.append(dict(job=job,actual_train_N=len(xx),median_and_RMS_exact=True,scalar_routing_checked_N=len(ix),solver_primary_secondary_qualified=True))
    assert riskdiff<1e-10 and min_eigen> -1e-10 and max_slack_violation<1e-7
    final=arrays(ART/'final/predictions.npz');oof=arrays(ART/'oof_predictions.npz');offsets=json.loads((OUT/'calibration.json').read_text())['offset_log']
    records=list(csv.DictReader((OUT/'metrics.tsv').open(),delimiter='\t'));paired=list(csv.DictReader((OUT/'paired.tsv').open(),delimiter='\t'))
    maxdiff=0.;checked=0;offset_diff=[]
    for sample,role in [('train_in_sample','train'),('source_OOF_raw','train'),('cal_development','cal'),('evaluation','eval')]:
        dd=subset(d,d['role']==role);logs=logs_for(sample,role,dd,oof,final,offsets);mm=diagnostic_masks(dd)
        if role=='cal':
            for arm in ARMS:offset_diff.append(abs(np.average(np.log(dd['truth_E_GeV'])-logs[arm+'_raw'])-offsets[arm]))
        for r in [v for v in records if v['sample']==sample]:
            m=mm[r['stratum']];assert int(r['N'])==m.sum()
            if not m.any():assert r['log_RMSE']=='未测量';continue
            pred=logs[r['model']][m];energy=dd['truth_E_GeV'][m];err=pred-np.log(energy);rel=np.exp(pred)/energy-1
            q=dict(log_RMSE=float(np.linalg.norm(err)/np.sqrt(len(err))),mean_bias_pct=float(100*np.average(rel)),median_bias_pct=float(100*np.median(rel)),R68_pct=float(50*(np.percentile(rel,84)-np.percentile(rel,16))))
            for threshold in [50,100]:
                for label,hit in [('tail',abs(rel)>threshold/100),('positive_tail',rel>threshold/100),('negative_tail',rel< -threshold/100)]:
                    key=label+str(threshold);q[key+'_pct']=float(100*np.count_nonzero(hit)/len(hit));q[key+'_loss_fraction']=float(np.dot(err[hit],err[hit])/np.dot(err,err)) if np.dot(err,err) else 0.
            maxdiff=max(maxdiff,max(abs(float(r[k])-v) for k,v in q.items()));checked+=1
    assert maxdiff<1e-9 and max(offset_diff)<1e-12
    dd=subset(d,d['role']=='eval');logs=logs_for('evaluation','eval',dd,oof,final,offsets);y=np.log(dd['truth_E_GeV']);mm=diagnostic_masks(dd)
    names=['Q_local_cal','Q0_cal','mu','F7'];err={k:logs[k]-y for k in names};rel={k:np.exp(logs[k])/dd['truth_E_GeV']-1 for k in names}
    groups,gid=np.unique(dd['group'],return_inverse=True);rng=np.random.default_rng(p['bootstrap_seed']);w=np.zeros((500,len(groups)),int)
    for component in ['pi','k','charm']:
        ix=np.flatnonzero(np.array([str(g).startswith(component+':') for g in groups]));w[:,ix]=rng.multinomial(len(ix),np.ones(len(ix))/len(ix),size=500)
    keys=LOW+list(COST);ratios={(k,r):[] for k in keys+['macro'] for r in ['mu','F7','Q0_cal']};tails={(k,r,t):[] for k in keys for r in ['mu','F7','Q0_cal'] for t in TAILS[:3]}
    for draw in range(500):
        rep=np.repeat(np.arange(len(y)),w[draw,gid])
        for k in keys:
            ix=rep[mm[k][rep]]
            if not len(ix):continue
            for ref in ['mu','F7','Q0_cal']:
                ratios[k,ref].append(float(np.linalg.norm(err['Q_local_cal'][ix])/np.linalg.norm(err[ref][ix])))
                for t in TAILS[:3]:
                    def hit(v):return v>.5 if t.startswith('positive') else v<-.5 if t.startswith('negative') else abs(v)>.5
                    tails[k,ref,t].append(float(100*(np.count_nonzero(hit(rel['Q_local_cal'][ix]))-np.count_nonzero(hit(rel[ref][ix])))/len(ix)))
        bins=[rep[mm[k][rep]] for k in ENERGY]
        if all(len(ix) for ix in bins):
            for ref in ['mu','F7','Q0_cal']:ratios['macro',ref].append(float(np.sqrt(np.mean([np.mean(err['Q_local_cal'][ix]**2) for ix in bins])/np.mean([np.mean(err[ref][ix]**2) for ix in bins]))))
    rd=td=0.
    for (key,ref),v in ratios.items():
        r=next(q for q in paired if q['sample']=='evaluation' and q['model']=='Q_local_cal' and q['reference']==ref and q['stratum']==key)
        a,b=np.quantile(v,[.025,.975]);rd=max(rd,abs(a-float(r['RMSE_ratio_low95'])),abs(b-float(r['RMSE_ratio_high95'])));assert len(v)==int(r['bootstrap_valid'])
    for (key,ref,t),v in tails.items():
        r=next(q for q in paired if q['sample']=='evaluation' and q['model']=='Q_local_cal' and q['reference']==ref and q['stratum']==key)
        a,b=np.quantile(v,[.025,.975]);td=max(td,abs(a-float(r[t+'_low95_pp'])),abs(b-float(r[t+'_high95_pp'])))
    assert rd<1e-10 and td<1e-9
    save(OUT/'independent_validation.json',dict(passed=True,base_model_checks=base_checks,head_checks=head_checks,risk_matrix_direct_max_abs_diff=riskdiff,
        minimum_moment_matrix_eigenvalue=min_eigen,max_training_protection_violation=max_slack_violation,direct_metric_rows_checked=checked,direct_metric_max_abs_diff=maxdiff,
        calibration_max_abs_diff=max(offset_diff),explicit_eval_source_draws=500,bootstrap_RMSE_interval_max_abs_diff=rd,bootstrap_tail_interval_max_abs_diff_pp=td,
        new_fits=0,base_queries='held-only saved12inner models for independent replay; no F7 or new outer/final inference',**resources(start)))
    print((OUT/'independent_validation.json').read_text())


if __name__=='__main__':main()
