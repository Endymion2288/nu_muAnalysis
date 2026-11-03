#!/usr/bin/env python3
"""Freeze stage78, audit nested role isolation, and measure OOF complementarity."""
from datetime import datetime,timezone
from audited_features import configuration,clean
from group_risk import inputs
from risk_complementarity import *


def complementarity(d,h):
    y=np.log(d['truth_E_GeV']);e=h-y[:,None]
    oracle=np.clip(y,h.min(1),h.max(1));oe=oracle-y
    assert np.all(oe**2<=np.min(e**2,axis=1)+1e-14)
    rows=[];moments=[]
    for key,m in diagnostic_masks(d).items():
        selections={'all':m}
        if key in LOW:
            for j,n in enumerate(['U','F','mu']):
                tail=indicator(e[:,j],'tail50');selections[n+'_tail50']=m&tail;selections[n+'_non_tail50']=m&~tail
        for label,mm in selections.items():
            if not mm.any():continue
            C=e[mm].T@e[mm]/mm.sum();r=dict(stratum=key,subset=label,**support(d,mm))
            for i,n in enumerate(['U','F','mu']):
                r[n+'_mean_error']=float(e[mm,i].mean())
                for j,n2 in enumerate(['U','F','mu']):r['C_'+n+'_'+n2]=float(C[i,j])
            r.update(common_overestimate_pct=float(100*np.all(e[mm]>0,axis=1).mean()),
                common_underestimate_pct=float(100*np.all(e[mm]<0,axis=1).mean()),
                common_positive_tail50_pct=float(100*np.all(np.expm1(e[mm])>.5,axis=1).mean()),
                common_negative_tail50_pct=float(100*np.all(np.expm1(e[mm])<-.5,axis=1).mean()),
                truth_inside_hull_pct=float(100*((y[mm]>=h[mm].min(1))&(y[mm]<=h[mm].max(1))).mean()),
                oracle_log_RMSE=float(np.sqrt(np.mean(oe[mm]**2))))
            for i,n in enumerate(['U','F','mu']):
                loss=e[mm,i]**2;ordered=np.sort(loss)[::-1]
                r[n+'_top1pct_loss_fraction']=float(ordered[:max(1,int(np.ceil(.01*len(loss))))].sum()/loss.sum())
                r[n+'_top10pct_loss_fraction']=float(ordered[:max(1,int(np.ceil(.1*len(loss))))].sum()/loss.sum())
            r['F_better_than_U_pct']=float(100*(e[mm,1]**2<e[mm,0]**2).mean())
            r['mu_better_than_U_pct']=float(100*(e[mm,2]**2<e[mm,0]**2).mean());moments.append(r)
            for n,pred in [('U',h[:,0]),('F',h[:,1]),('mu',h[:,2]),('truth_hull_oracle',oracle)]:
                rows.append(dict(stratum=key,subset=label,model=n,**support(d,mm),**metrics(y[mm],pred[mm])))
    table(OUT/'complementarity.tsv',moments);table(OUT/'oracle_metrics.tsv',rows)
    return dict(truth_hull_bound_checked_eventwise=True,oracle_is_not_deployment_or_information_limit=True,
        no_oracle_admission_gate=True,source_OOF_only=True,N=len(y),new_fits=0,new_model_queries=0)


def main():
    start=begin();OUT.mkdir(exist_ok=True);CACHE.mkdir(exist_ok=True)
    assert not (OUT/'protocol.json').exists() and not ART.exists()
    old=json.loads((REPO/'workbook/stage73_energy_ml/protocol.json').read_text())
    p={k:old[k] for k in ['features','feature_version','fold_by_group','seed','rounds','xgboost','xgboost_version']}
    import scipy,sklearn
    p.update(stage=78,starting_commit='4c3fae0',frozen_utc=datetime.now(timezone.utc).isoformat(),
        partition_seed=2026110378,partition=dict(max_depth=3,min_samples_leaf=200,criterion='squared_error',outputs=2),
        preprocessing='actual head train finite median (all-missing 0) + all62 missing masks; base X untouched',
        scipy_version=scipy.__version__,sklearn_version=sklearn.__version__,solver='SLSQP',solver_ftol=1e-11,
        solver_maxiter=2000,solver_feasibility_tolerance=1e-7,secondary_tau_tolerance=1e-8,
        solver_start='all leaves U vertex; primary tau=max low normalized risk',
        secondary='single call minimize N-leaf-weighted squared distance to U under primary tau+1e-8 and same protections',
        solver_failure='no solver/parameter retries; unresolved primary or prescribed secondary is numerical failure, no scientific conclusion',
        scientific_experts=['U_raw','F_raw','log(pz/.8)'],main_candidate='Q_local_cal',control='Q0',
        formal_base_fits_max=12,formal_partition_fits_max=4,convex_problems_max=8,solver_calls_max=16,
        inner='remaining original2 source folds inside each purged outer train; inner training incoming purge',
        final_head='original stage73 raw OOF41447; final predictions use existing final U/F',
        objective='min max two lowE MSE/mu MSE',training_protection_RMSE=COST,
        calibration='raw OOF only; final each one unit global mean log offset from original cal8440',
        bootstrap_seed=2026111378,bootstrap_repeats=500,
        bootstrap_scope='fixed experts/head/offset; excludes retraining,partition/calibration,lineage,response,research-selection; not joint coverage',
        recovery_RMSE_ratio_high95=1.05,protection_RMSE_ratio_high95=COST,tail50_delta_high95_pp=2.,
        formal_jobs_max=4,request_cpus=1,request_memory_MB=3000,total_CPU_budget_s=7200,
        wall_per_job_s=3600,worker_timeout_s=3550,callback_CPU_per_job_s=1700,callback_wall_per_job_s=3500,
        retained_budget_bytes=20000000,no_new_ROOT_RDO_F7=True,no_feature_or_policy_scan=True,
        resource_status='upper limits only; actual package and pilot required before submit')
    save(OUT/'protocol.json',p)
    d=inputs();assert configuration()['features']==p['features'] and len(p['features'])==62
    assert [len(np.unique(d['group'][d['role']==r])) for r in ['train','cal','eval']]==[91,16,22]
    assert [int(d['missing'][d['role']==r].sum()) for r in ['train','cal','eval']]==[21,3,7]
    assert not set(p['features'])&{'ML_mu_p_GeV','ML_track_p1_GeV','ML_track_pz1_GeV','ML_track_log_p1_over_p0'}
    assert sum(n.endswith('_raw_charge') for n in p['features'])==11
    cfg=configuration()
    for j,n in enumerate(p['features']):np.testing.assert_array_equal(clean(d['x'][:,j],cfg['rules'][n]).astype('float32'),d['x'][:,j])
    ix=[p['features'].index(f'ML_calo{j}_E_EM_GeV') for j in range(4)]
    np.testing.assert_array_equal(np.isnan(d['x'][:,p['features'].index('ML_calo_total_E_EM_GeV')]),np.isnan(d['x'][:,ix]).any(1))
    tr=d['role']=='train';a=arrays(REPO/'ml/artifacts/stage73/oof_predictions.npz')
    np.testing.assert_array_equal(a['row'],d['row'][tr])
    d['old_oof_h']=np.full((len(tr),3),np.nan)
    d['old_oof_h'][tr]=np.c_[a['U_raw_log'],a['F_raw_log'],np.log(d['pz'][tr]/.8)]
    final=arrays(REPO/'ml/artifacts/stage73/final/predictions.npz');d['old_final_h']=np.full((len(tr),3),np.nan)
    for role in ['train','cal','eval']:
        m=d['role']==role;np.testing.assert_array_equal(final[role+'_row'],d['row'][m])
        d['old_final_h'][m]=np.c_[final[role+'_U_raw_log'],final[role+'_F_raw_log'],np.log(d['pz'][m]/.8)]
    splits=[];support_rows=[]
    for job in JOBS:
        outer,held,purge=training_split(d,p,job)
        splits.append(dict(job=job,level='outer',inner=-1,train_N=int(outer.sum()),held_N=int(held.sum()) if held is not None else 0,
            purged_N=int(purge.sum()),source_overlap=0,known_incoming_overlap=0))
        if held is None:continue
        seen=np.zeros(len(tr),int)
        for k,it,ih,ip in inner_splits(d,p,job):
            seen[ih]+=1
            # Outer held source AND exact incoming never reach any inner model or head.
            assert not set(map(tuple,d['incoming'][it]))&set(map(tuple,d['incoming'][held]))
            for name,m in [('train',it),('held',ih)]:
                dd=subset(d,m)
                for key,sel in diagnostic_masks(dd).items():support_rows.append(dict(job=job,inner=k,role=name,stratum=key,**support(dd,sel)))
            splits.append(dict(job=job,level='inner',inner=k,train_N=int(it.sum()),held_N=int(ih.sum()),purged_N=int(ip.sum()),source_overlap=0,known_incoming_overlap=0))
        np.testing.assert_array_equal(seen[outer],np.ones(int(outer.sum()),int));assert not seen[~outer].any()
    table(OUT/'splits.tsv',splits);table(OUT/'inner_support.tsv',support_rows)
    qa=complementarity(subset(d,tr),d['old_oof_h'][tr]);qa.update(**resources(start));save(OUT/'A_validation.json',qa)
    np.savez_compressed(CACHE/'input.npz',**d)
    save(OUT/'input_validation.json',dict(passed=True,role_N=[41447,8440,14057],source_groups=[91,16,22],eligible_missing_N=[21,3,7],protected_missing_N=11,
        nested_sources_and_exact_incoming_isolated=True,all_outer_train_once_inner_OOF=True,
        original62_and_typed_NaN_preserved=True,old_expert_rows_exact=True,input_logical_bytes=(CACHE/'input.npz').stat().st_size,
        physical_EOS_network_IO='未测量',**resources(start)))
    print((OUT/'input_validation.json').read_text())


if __name__=='__main__':main()
