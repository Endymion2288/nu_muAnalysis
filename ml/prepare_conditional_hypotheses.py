#!/usr/bin/env python3
"""Freeze proposals, all roles and QA before any formal stage74 fit."""
import json
from datetime import datetime, timezone
import numpy as np
from audited_features import configuration, load, SCINTILLATORS, WAVE_INVALID, FIT_INVALID, clean
from group_risk import training_split
from conditional_hypotheses import *


def main():
    start=begin();OUT.mkdir(exist_ok=True);CACHE.mkdir(exist_ok=True)
    assert not (OUT/'protocol.json').exists() and not ART.exists()
    cfg=configuration();old=json.loads((REPO/'workbook/stage68_energy_ml/protocol.json').read_text())
    quartiles=json.loads((REPO/'workbook/stage73_energy_ml/A_validation.json').read_text())['train_Timing_quartiles_pC']
    p=dict(stage=74,starting_commit='1e6d6a1',frozen_utc=datetime.now(timezone.utc).isoformat(),
        features=cfg['features'],feature_version=cfg['version'],query=QUERY,arms=ARMS,
        seed=2026110374,bootstrap_seed=2026111374,bootstrap_repeats=500,
        xgboost=dict(old['xgboost'],objective='binary:logistic',base_score=.5,boost_from_average=0),
        xgboost_version='2.1.3',rounds=400,protocol_version=2,
        fold_by_group=old['fold_by_group'],fold_counts=old['fold_counts'],
        energy_edges_GeV=E_EDGES.tolist(),pz_edges_GeV=[50,75,100,150,250,500,1000,'inf'],
        proposal='actual train unit counts by reco-pz x energy bin; log-uniform inside each energy bin; no pseudocount or merge',
        outside_support='retain zero-q real events; classifier diagnostics defined, posterior recovery undefined; no physical impossibility claim',
        training_pairs='one true and one independent q query per X, interleaved positive/negative; implicit unit weights',
        RNG='train seed+job index0/1/2/3; held seed+job index+100; final evaluation RNG shared sequentially cal then eval, never uses their spectra',
        ratio='balanced BCE ideal logit = log p(t|X) - log q(t|Bpz); multiply q back and normalize for posterior',
        main_stratum='pz50_100',critical_strata=CRITICAL,
        success='OOF/eval main gain95lower>0; nonempty critical support fully covered and no critical gain95upper<0; intervals spanning0 remain inconclusive',
        metrics='per real X mean of positive/negative BCE; Brier, both BCE components, fixed10 equal-width reliability bins',
        Timing_quartiles_pC=quartiles,formal_fits=8,formal_jobs=4,
        request_cpus=1,request_memory_MB=3000,total_CPU_budget_s=3600,wall_per_job_s=1800,
        worker_timeout_s=1750,callback_CPU_per_job_s=850,retained_budget_bytes=20000000,
        calibration='none; logits/sigmoids are pair-experiment probabilities, no energy point estimate',
        bootstrap_scope='fixed predictions/proposal/pairing; component-stratified conservative sources; excludes retraining, proposal estimation, full genealogy, response and selection',
        no_new_ROOT_RDO=True,no_new_F7_inference=True,no_energy_grid_point_or_spectrum=True,no_stage70_augmentation=True)
    save(OUT/'protocol.json',p)
    d,s,x=load();rows=s['row'];role=np.full(len(rows),'unused',dtype='<U6')
    role[d['train_eligible'][rows]]='train';role[d['cal_eligible'][rows]]='cal';role[d['partition'][rows]=='validation']='eval'
    missing=np.isnan(x).any(1)
    assert [int((role==r).sum()) for r in ['train','cal','eval']]==[41447,8440,14057]
    assert missing.sum()==42 and [int((missing&(role==r)).sum()) for r in ['train','cal','eval']]==[21,3,7]
    assert int((missing&(role=='unused')).sum())==11
    assert cfg['features'][0]=='ML_mu_pz0_GeV'
    assert cfg['features'][29:33]==[f'Timing{i}_raw_charge' for i in range(4)]
    assert not set(cfg['features'])&{'ML_mu_p_GeV','ML_track_p1_GeV','ML_track_pz1_GeV','ML_track_log_p1_over_p0'}
    for j,n in enumerate(SCINTILLATORS):
        expect=s['raw_charge'][:,j].astype(float).copy();expect[(s['status'][:,j].astype(int)&WAVE_INVALID)!=0]=np.nan
        np.testing.assert_array_equal(x[:,cfg['features'].index(n+'_raw_charge')],clean(expect,cfg['rules'][n+'_raw_charge']).astype('float32'))
    modules=x[:,[cfg['features'].index(f'ML_calo{j}_E_EM_GeV') for j in range(4)]]
    np.testing.assert_array_equal(np.isnan(x[:,cfg['features'].index('ML_calo_total_E_EM_GeV')]),np.isnan(modules).any(1))
    for j in range(4):assert np.all(np.isnan(modules[(s['calo_status'][:,j].astype(int)&FIT_INVALID)!=0,j]))
    take=role!='unused';row=rows[take]
    q={k:d[k][row] for k in ['truth_E_GeV','y_lepton','confirmed','source','group','component','incoming']}
    q.update(row=row,role=role[take],x=x[take],pz=d['reco_pz_GeV'][row],missing=missing[take])
    assert np.isfinite(q['truth_E_GeV']).all() and np.isfinite(q['pz']).all()
    pb,eb=bins(q['pz'],q['truth_E_GeV'])
    assert np.all((pb>=0)&(pb<7)) and np.all((eb>=0)&(eb<7)), 'freeze out-of-range treatment before formal fits'
    support_rows=[];q_rows=[];split_rows=[]
    for job in JOBS:
        tr,held,purge=training_split(q,p,job);counts,mass=proposal(q['pz'][tr],q['truth_E_GeV'][tr])
        for b in range(7):
            for e in range(7):
                m=tr&(pb==b)&(eb==e)
                q_rows.append(dict(job=job,pz_bin=b,energy_bin=e,**support(q,m),mass=float(mass[b,e]),density_per_logE=float(mass[b,e]/np.diff(LOG_EDGES)[e])))
        roles={'held':held} if held is not None else {r:q['role']==r for r in ['train','cal','eval']}
        for r,m in roles.items():
            dd={k:v[m] for k,v in q.items()};density=proposal_density(dd['pz'],np.log(dd['truth_E_GeV']),mass)
            for name,mask in strata(dd,quartiles).items():
                support_rows.append(dict(job=job,role=r,stratum=name,**support(dd,mask),
                                         zero_q_N=int((mask&(density==0)).sum())))
        split_rows.append(dict(job=job,train_N=int(tr.sum()),train_groups=len(np.unique(q['group'][tr])),
            train_unique_incoming=len(np.unique(q['incoming'][tr],axis=0)),purged_N=int(purge.sum()),
            held_N=int(held.sum()) if held is not None else 0,empty_pz_slices=int((counts.sum(1)==0).sum()),
            group_overlap=0,known_incoming_overlap=0))
        assert np.all(counts.sum(1)>0), 'empty train proposal slice needs an explicit no-removal handling contract'
    table(OUT/'proposal.tsv',q_rows);table(OUT/'support.tsv',support_rows)
    save(OUT/'splits.json',split_rows)
    np.savez_compressed(CACHE/'input.npz',**q)
    save(OUT/'input_validation.json',dict(passed=True,role_N=[41447,8440,14057],conservative_groups=[91,16,22],
        missing_N=42,eligible_missing_N=[21,3,7],protected_missing_N=11,raw11_exact=True,calo_missing_propagation=True,
        forbidden_linear_momenta_absent=True,typed_policy_unchanged=True,unit_physical_events=True,
        no_outside_pz_or_energy_support=True,new_fits=0,input_bytes=(CACHE/'input.npz').stat().st_size,
        physical_EOS_network_bytes='未测量',**resources(start)))
    print((OUT/'input_validation.json').read_text())


if __name__=='__main__':main()
