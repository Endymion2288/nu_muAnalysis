"""Independent stage80 all-draw event expansions, risks, original NaNs and budgets."""
import csv
import json
import numpy as np
from pulse_ablation import *


def main():
    start=begin();d=data();p=json.loads((OUT/'protocol.json').read_text());old,s,x=load()
    role=np.full(len(s['row']),'unused',dtype='<U6');role[old['train_eligible'][s['row']]]='train';role[old['cal_eligible'][s['row']]]='cal';role[old['partition'][s['row']]=='validation']='eval'
    assert [int((np.isnan(x).any(1)&(role==r)).sum()) for r in ['train','cal','eval','unused']]==[21,3,7,11]
    np.testing.assert_array_equal(d['x'],x[role!='unused']);np.testing.assert_array_equal(d['role'],role[role!='unused'])
    assert p['features_by_arm']['U']==configuration()['features'] and p['features_by_arm']['P']==configuration()['features']+SHAPE
    assert not set(p['features_by_arm']['P'])&{'ML_mu_p_GeV','ML_track_p1_GeV','ML_track_pz1_GeV','ML_track_log_p1_over_p0','localtime','baseline_rms'}
    np.testing.assert_array_equal(np.isnan(d['shape']),np.repeat(~d['shape_valid'],2,axis=1));assert np.all(d['shape'][np.isfinite(d['shape'])]>0)
    for st in ['extract','fit']:
        h=json.loads((OUT/(st+'_history.json')).read_text());assert len(h)==4
        assert all(r['ExitCode']==0 and r['NumJobStarts']==1 and r['RequestCpus']==1 and r['RequestMemory']==3000 and r['MaxRuntime']==1800 for r in h)
    hist=sum([json.loads((OUT/(st+'_history.json')).read_text()) for st in ['extract','fit']],[])
    cpu=sum(r['RemoteUserCpu']+r['RemoteSysCpu'] for r in hist);assert cpu<7200
    requested=sum(json.loads((OUT/f'extract{j}.json').read_text())['requested_bytes'] for j in range(4))
    requested+=json.loads((OUT/'qa.json').read_text())['requested_bytes'];assert requested<10_000_000_000
    sourceaudit=json.loads((OUT/'source_audit.json').read_text());assert sourceaudit['passed'] and sourceaudit['N']==254
    assert all(r['identical_to_d32b0ff3'] for r in sourceaudit['comparisons'])
    paired=list(csv.DictReader((OUT/'paired.tsv').open(),delimiter='\t'));measured=list(csv.DictReader((OUT/'metrics.tsv').open(),delimiter='\t'))
    primary=json.loads((OUT/'bootstrap_primary_draws.json').read_text());final=arrays(ART/'final/predictions.npz');oof=arrays(ART/'oof_predictions.npz')
    offset=json.loads((OUT/'calibration.json').read_text())['offset_log'];max_draw_diff=0.;max_risk_diff=0.;checked=0
    for sample,rr in [('source_OOF_raw','train'),('cal_development','cal'),('evaluation','eval')]:
        take=d['role']==rr;dd={k:v[take] for k,v in d.items()};y=np.log(dd['truth_E_GeV']);prefix='' if rr=='train' else rr+'_';a=oof if rr=='train' else final
        np.testing.assert_array_equal(a[prefix+'row'],dd['row'])
        logs={arm+'_raw':a[prefix+arm+'_raw_log'] for arm in ARMS}
        if rr!='train':
            for arm in ARMS:
                logs[arm+'_cal']=logs[arm+'_raw']+offset[arm]
                if rr=='cal':assert abs(np.mean(y-logs[arm+'_raw'])-offset[arm])<1e-14
        seed=p['bootstrap_seed']+{'train':1,'cal':2,'eval':0}[rr];groups,gid,w=boot_weights(dd,seed,500)
        for key in ['all','pz50_100','E50_100','E100_200']:
            m=diagnostic_masks(dd)[key];indices=np.flatnonzero(m);expected=next(r['draws'] for r in primary if r['sample']==sample and r['stratum']==key)
            actual=[]
            for draw in range(500):
                rep=np.repeat(indices,w[draw,gid[m]])
                # Explicit replicated event arrays, independent of grouped bin sums.
                n=np.linalg.norm(logs['P_raw'][rep]-y[rep]);den=np.linalg.norm(logs['U_raw'][rep]-y[rep]);actual.append(float(n/den))
            difference=float(np.max(np.abs(np.asarray(actual)-expected)));max_draw_diff=max(max_draw_diff,difference);assert difference<1e-12
            match=next(r for r in paired if r['sample']==sample and r['stratum']==key and r['model']=='P_raw' and r['reference']=='U_raw')
            np.testing.assert_allclose(np.quantile(actual,[.025,.975]),[float(match['RMSE_ratio_low95']),float(match['RMSE_ratio_high95'])],rtol=0,atol=1e-12)
        for record in measured:
            if record['sample']!=sample or record['model'] not in logs:continue
            m=diagnostic_masks(dd)[record['stratum']]
            if not m.any():continue
            log=logs[record['model']];value=np.linalg.norm(log[m]-y[m])/np.sqrt(m.sum());delta=abs(float(record['log_RMSE'])-value);max_risk_diff=max(max_risk_diff,float(delta))
            relative=np.exp(log[m]-y[m])-1
            for key,mask in [('tail50',np.abs(relative)>.5),('positive_tail50',relative>.5),('negative_tail50',relative<-.5)]:
                assert abs(float(record[key+'_pct'])-100*np.mean(mask))<1e-12
            checked+=1
    assert max_risk_diff<1e-12
    save(OUT/'independent_validation.json',dict(passed=True,all_original_roles_and_42_missing_exact=True,shape_domain_and_NaN_exact=True,
        all_500_draws_explicitly_expanded=True,bootstrap_draws_checked=6000,bootstrap_max_abs_diff=max_draw_diff,
        metrics_rows_checked=checked,metric_RMSE_max_abs_diff=max_risk_diff,tail50_signs_exact=True,
        eight_Condor_jobs_once_exit0=True,formal_fits=8,pilot_fits=0,remote_CPU_s=cpu,remote_wall_sum_s=sum(r['RemoteWallClockTime'] for r in hist),
        ROOT_requested_bytes_with_QA=requested,physical_EOS_network_IO='未测量',new_F7_inference=0,**resources(start)))
    print((OUT/'independent_validation.json').read_text())


if __name__=='__main__':main()
