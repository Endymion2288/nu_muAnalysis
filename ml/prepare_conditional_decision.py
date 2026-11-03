#!/usr/bin/env python3
"""Freeze one mapping, input identities and numerical gates before any queries."""
from datetime import datetime, timezone
from audited_features import configuration
from group_risk import inputs, training_split
from conditional_decision import *


def main():
    start = begin(); OUT.mkdir(exist_ok=True); CACHE.mkdir(exist_ok=True)
    assert not (OUT/'protocol.json').exists() and not ART.exists()
    old = json.loads((REPO/'workbook/stage74_energy_ml/protocol.json').read_text())
    p = dict(stage=75, starting_commit='a3cc31b', frozen_utc=datetime.now(timezone.utc).isoformat(),
        features=old['features'], fold_by_group=old['fold_by_group'], source_model_stage=74,
        xgboost_version='2.1.3', formal_fits=0, main_candidate='X_cal',
        mapping='r proportional to original q*exp(score); sole exp(mean logE) decision',
        interpolation='piecewise linear exp(score), exact zeroth and first moments; split at every original q edge',
        main_grid_base_nodes=257, QA_grid_base_nodes=513, actual_main_nodes=len(grid(257)),
        actual_QA_nodes=len(grid(513)), chunk_real_X=64,
        numerical_max_abs_log_mean_difference=.005, numerical_source_median_limit=.001,
        QA_selection='sorted global row equally spaced:64 per held fold;32 final cal and32 eval;no residual selection',
        calibration='OOF raw only; final M/X each one unit global mean-log offset from original8440 cal',
        bootstrap_repeats=500, bootstrap_seed=2026111375,
        bootstrap_scope='fixed model/q/offset; component-stratified conservative sources; no retraining, q/pairing RNG, genealogy,response or research-selection uncertainty',
        recovery_RMSE_ratio_high95=1.05, protection_RMSE_ratio_high95=dict(all=1.01,E200_inf=1.03,pz50_100=1.03,high_y=1.03,unconfirmed=1.03),
        tail50_delta_high95_pp=2., formal_jobs_max=4, request_cpus=1, request_memory_MB=3000,
        total_CPU_budget_s=3600, wall_per_job_s=1800, worker_timeout_s=1750,
        retained_budget_bytes=20000000, no_new_classifier_or_q_or_temperature=True,
        no_new_ROOT_RDO_or_production=True, no_energy_risk_before_numerical_gate=True)
    save(OUT/'protocol.json', p)
    d = inputs(); cfg=configuration(); assert cfg['features']==p['features']
    assert [int((d['role']==r).sum()) for r in ['train','cal','eval']]==[41447,8440,14057]
    assert [int(d['missing'][d['role']==r].sum()) for r in ['train','cal','eval']]==[21,3,7]
    identities=[]; splits=[]
    for job in JOBS:
        tr, held, purge=training_split(d,p,job)
        a=arrays(MODEL_ART/job/'predictions.npz');count,mass=proposal(d['pz'][tr],d['truth_E_GeV'][tr])
        np.testing.assert_array_equal(count,a['proposal_counts']);np.testing.assert_array_equal(mass,a['proposal_mass'])
        roles={'held':held} if held is not None else {r:d['role']==r for r in ['cal','eval']}
        for role,take in roles.items():
            idx=np.flatnonzero(take);fixed=idx[fixed_indices(d['row'][idx],64 if held is not None else 32)]
            identities += [dict(job=job,role=role,row=int(d['row'][i]),group=str(d['group'][i])) for i in fixed]
        splits.append(dict(job=job,train_N=int(tr.sum()),held_N=int(held.sum()) if held is not None else 0,
            purged_N=int(purge.sum()),source_overlap=0,known_incoming_overlap=0))
        for arm in ARMS:model(job,arm,p['features'])
    table(OUT/'numerical_QA_identities.tsv',identities);save(OUT/'splits.json',splits)
    np.savez_compressed(CACHE/'input.npz',**d)
    save(OUT/'input_validation.json',dict(passed=True,role_N=[41447,8440,14057],eligible_missing_N=[21,3,7],
        same62_pz0_raw_typed_NaN=True,all_eight_models_and_original_q_checked=True,QA_real_X_N=len(identities),
        formal_fits=0,input_logical_bytes=(CACHE/'input.npz').stat().st_size,physical_EOS_IO='未测量',**resources(start)))
    print((OUT/'input_validation.json').read_text())


if __name__=='__main__':main()
