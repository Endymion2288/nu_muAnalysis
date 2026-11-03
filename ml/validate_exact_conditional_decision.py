#!/usr/bin/env python3
"""Independent point-metric arithmetic and 500 explicit event bootstrap audits."""
import csv
from group_risk import inputs
from report_exact_conditional_decision import diagnostic_masks, extra_references
from exact_conditional_decision import *


def main():
    start=begin();d=arrays(CACHE/'input.npz') if (CACHE/'input.npz').exists() else inputs()
    p=json.loads((OUT/'protocol.json').read_text());calibration=json.loads((OUT/'calibration.json').read_text())
    final=arrays(ART/'final/predictions.npz');oof=arrays(ART/'oof_predictions.npz')
    records=list(csv.DictReader((OUT/'metrics.tsv').open(),delimiter='\t'))
    paired=list(csv.DictReader((OUT/'paired.tsv').open(),delimiter='\t'))
    maxdiff=0.;rows_checked=0;offset_diff=[]
    for sample,role in [('train_in_sample','train'),('source_OOF_raw','train'),('cal_development','cal'),('evaluation','eval')]:
        take=d['role']==role;dd={k:v[take] for k,v in d.items()};a=oof if sample=='source_OOF_raw' else final
        prefix='' if sample=='source_OOF_raw' else role+'_';mm=diagnostic_masks(dd,a[prefix+'true_q_density'])
        logs={'mu':np.log(dd['pz']/.8)}
        for arm in ARMS:
            logs[arm+'_raw']=a[prefix+arm+'_raw_log']
            if role!='train':logs[arm+'_cal']=logs[arm+'_raw']+calibration['offset_log'][arm]
            if role=='cal':offset_diff.append(abs(float(np.average(np.log(dd['truth_E_GeV'])-logs[arm+'_raw']))-calibration['offset_log'][arm]))
        logs.update(extra_references(role,dd['row'],sample=='source_OOF_raw'))
        for r in [v for v in records if v['sample']==sample]:
            mask=mm[r['stratum']];assert int(r['N'])==int(mask.sum())
            if not mask.any():assert r['log_RMSE']=='未测量';continue
            pred=logs[r['model']][mask];energy=dd['truth_E_GeV'][mask]
            error=pred-np.log(energy);relative=np.exp(pred)/energy-1
            measured=dict(log_RMSE=float(np.linalg.norm(error)/np.sqrt(len(error))),
                mean_bias_pct=float(100*np.average(relative)),median_bias_pct=float(100*np.median(relative)),
                R68_pct=float((np.percentile(relative,84)-np.percentile(relative,16))*50))
            for threshold in [50,100]:
                for label,hit in [('tail',abs(relative)>threshold/100),('positive_tail',relative>threshold/100),('negative_tail',relative< -threshold/100)]:
                    key=label+str(threshold)
                    measured[key+'_pct']=float(100*np.count_nonzero(hit)/len(hit))
                    denominator=np.dot(error,error)
                    measured[key+'_loss_fraction']=float(np.dot(error[hit],error[hit])/denominator) if denominator else 0.
            for key,value in measured.items():maxdiff=max(maxdiff,abs(value-float(r[key])))
            rows_checked+=1
    assert maxdiff<1e-9 and max(offset_diff)<1e-12
    # Event expansion for every one of 500 evaluation source draws, independent of aggregate sums.
    dd={k:v[d['role']=='eval'] for k,v in d.items()};n=len(dd['row']);y=np.log(dd['truth_E_GeV'])
    mm=diagnostic_masks(dd,final['eval_true_q_density'])
    logs=dict(X=final['eval_X_raw_log']+calibration['offset_log']['X'],mu=np.log(dd['pz']/.8),F7=extra_references('eval',dd['row'])['F7'])
    errors={k:v-y for k,v in logs.items()};relative={k:np.exp(v)/dd['truth_E_GeV']-1 for k,v in logs.items()}
    groups,gid=np.unique(dd['group'],return_inverse=True);rng=np.random.default_rng(p['bootstrap_seed']);weights=np.zeros((500,len(groups)),int)
    for component in ['pi','k','charm']:
        ix=np.flatnonzero(np.array([str(g).startswith(component+':') for g in groups]))
        weights[:,ix]=rng.multinomial(len(ix),np.ones(len(ix))/len(ix),size=500)
    keys=['E50_100','E100_200','all','E200_inf','pz50_100','high_y','unconfirmed']
    ratios={(key,ref):[] for key in keys+['macro'] for ref in ['mu','F7']}
    tail_deltas={(key,ref,t):[] for key in keys for ref in ['mu','F7'] for t in ['tail50','positive_tail50','negative_tail50']}
    for draw in range(500):
        rep=np.repeat(np.arange(n),weights[draw,gid])
        for key in keys:
            ix=rep[mm[key][rep]]
            if not len(ix):continue
            for ref in ['mu','F7']:
                ratios[key,ref].append(float(np.linalg.norm(errors['X'][ix])/np.linalg.norm(errors[ref][ix])))
                for t in ['tail50','positive_tail50','negative_tail50']:
                    def hit(v):return v>.5 if t.startswith('positive') else v< -.5 if t.startswith('negative') else abs(v)>.5
                    tail_deltas[key,ref,t].append(float(100*(np.count_nonzero(hit(relative['X'][ix]))-np.count_nonzero(hit(relative[ref][ix])))/len(ix)))
        bins=[rep[mm[f'E{lo}_{hi}'][rep]] for lo,hi in zip([50,100,200,400,800,1600,3200],[100,200,400,800,1600,3200,6400])]
        if all(len(ix) for ix in bins):
            for ref in ['mu','F7']:
                ratios['macro',ref].append(float(np.sqrt(np.average([np.average(errors['X'][ix]**2) for ix in bins])/np.average([np.average(errors[ref][ix]**2) for ix in bins]))))
    bootstrap_diff=0.;tail_diff=0.
    for (key,ref),values in ratios.items():
        r=next(v for v in paired if v['sample']=='evaluation' and v['stratum']==key and v['model']=='X_cal' and v['reference']==ref)
        assert len(values)==int(r['bootstrap_valid'])
        lo,hi=np.quantile(values,[.025,.975]);bootstrap_diff=max(bootstrap_diff,abs(lo-float(r['RMSE_ratio_low95'])),abs(hi-float(r['RMSE_ratio_high95'])))
    for (key,ref,t),values in tail_deltas.items():
        r=next(v for v in paired if v['sample']=='evaluation' and v['stratum']==key and v['model']=='X_cal' and v['reference']==ref)
        lo,hi=np.quantile(values,[.025,.975]);tail_diff=max(tail_diff,abs(lo-float(r[t+'_low95_pp'])),abs(hi-float(r[t+'_high95_pp'])))
    assert bootstrap_diff<1e-10 and tail_diff<1e-9
    zero=oof['true_q_density']==0
    assert int(zero.sum())==12 and all(np.isfinite(oof[arm+'_raw_log'][zero]).all() for arm in ARMS)
    save(OUT/'independent_validation.json',dict(passed=True,direct_metric_rows_checked=rows_checked,direct_metric_max_abs_diff=maxdiff,
        calibration_max_abs_diff=max(offset_diff),explicit_evaluation_source_draws=500,
        bootstrap_RMSE_interval_max_abs_diff=bootstrap_diff,bootstrap_tail_interval_max_abs_diff_pp=tail_diff,
        OOF_zero_q_N=int((oof['true_q_density']==0).sum()),all_zero_q_point_predictions_finite=True,
        new_fits=0,new_model_queries=0,**resources(start)))
    print((OUT/'independent_validation.json').read_text())


if __name__=='__main__':main()
