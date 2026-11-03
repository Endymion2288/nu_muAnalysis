#!/usr/bin/env python3
"""Freeze stage76 unchanged decision, roles, exact integration and QA identities."""
from datetime import datetime, timezone
from audited_features import configuration
from group_risk import inputs, training_split
from exact_conditional_decision import *


def main():
    start=begin();OUT.mkdir(exist_ok=True);CACHE.mkdir(exist_ok=True)
    assert not (OUT/'protocol.json').exists() and not ART.exists()
    previous=json.loads((REPO/'workbook/stage75_energy_ml/protocol.json').read_text())
    p={k:previous[k] for k in ['features','fold_by_group','xgboost_version','bootstrap_repeats',
        'bootstrap_seed','bootstrap_scope','calibration','main_candidate','recovery_RMSE_ratio_high95',
        'protection_RMSE_ratio_high95','tail50_delta_high95_pp','formal_jobs_max','request_cpus',
        'request_memory_MB','total_CPU_budget_s','wall_per_job_s','worker_timeout_s','retained_budget_bytes']}
    p.update(stage=76,starting_commit='3b3cb07',frozen_utc=datetime.now(timezone.utc).isoformat(),
        formal_fits=0,source_model_stage=74,chunk_real_X=64,formal_jobs=4,
        mapping='original q*exp(float32 tree margin), normalized; sole exp(mean logE)',
        integration='piecewise constant on all serialized query cut float32-cast transitions plus original q edges',
        numeric_log_mean_tolerance=1e-6,numeric_normalization_tolerance=1e-12,
        QA_identities='same stage75 fixed256; within each held sorted8;final cal/eval sorted4 each for constancy/traversal',
        no_model_q_seed_temperature_or_decision_change=True,no_new_ROOT_RDO_production_or_F7=True,
        callback_CPU_per_job_s=850,callback_wall_per_job_s=1700,
        unsupported='all12zero-q OOF retained; point risk all events; density logscore -infinity, no floor')
    save(OUT/'protocol.json',p)
    d=inputs();assert configuration()['features']==p['features']
    assert [int((d['role']==r).sum()) for r in ['train','cal','eval']]==[41447,8440,14057]
    assert [len(np.unique(d['group'][d['role']==r])) for r in ['train','cal','eval']]==[91,16,22]
    assert [int(d['missing'][d['role']==r].sum()) for r in ['train','cal','eval']]==[21,3,7]
    proposals={};splits=[];inventory=[]
    for job in JOBS:
        tr,held,purge=training_split(d,p,job);a=arrays(MODEL_ART/job/'predictions.npz')
        count,mass=proposal(d['pz'][tr],d['truth_E_GeV'][tr])
        np.testing.assert_array_equal(count,a['proposal_counts']);np.testing.assert_array_equal(mass,a['proposal_mass'])
        proposals[job]=dict(count=count.tolist(),mass=mass.tolist())
        splits.append(dict(job=job,train_N=int(tr.sum()),held_N=int(held.sum()) if held is not None else 0,
            purged_N=int(purge.sum()),source_overlap=0,known_incoming_overlap=0))
        for arm in ARMS:
            booster=model(job,arm,p['features']);edges,cuts=partition(booster)
            inventory.append(dict(job=job,arm=arm,trees=400,reco_features=1 if arm=='M' else 62,
                unique_query_cuts=len(cuts),intervals=len(edges)-1))
    save(OUT/'proposals.json',proposals);save(OUT/'splits.json',splits);table(OUT/'partition_inventory.tsv',inventory)
    (OUT/'numerical_QA_identities.tsv').write_bytes((REPO/'workbook/stage75_energy_ml/numerical_QA_identities.tsv').read_bytes())
    np.savez_compressed(CACHE/'input.npz',**d)
    save(OUT/'input_validation.json',dict(passed=True,role_N=[41447,8440,14057],source_groups=[91,16,22],
        eligible_missing_N=[21,3,7],original62_pz0_raw_NaN_unchanged=True,
        all_eight_models_and_original_q_exact=True,formal_fits=0,input_logical_bytes=(CACHE/'input.npz').stat().st_size,
        physical_EOS_network_IO='未测量',**resources(start)))
    print((OUT/'input_validation.json').read_text())


if __name__=='__main__':main()
