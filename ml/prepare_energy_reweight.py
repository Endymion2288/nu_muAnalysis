#!/usr/bin/env python3
"""Freeze stage73 before A; inspect all low-E events without a new energy fit."""
import json
from datetime import datetime, timezone
import numpy as np
from audited_features import load, configuration, SCINTILLATORS, WAVE_INVALID, FIT_INVALID, clean
from group_risk import training_split
from energy_reweight import *


def main():
    start=begin();OUT.mkdir(exist_ok=True);CACHE.mkdir(exist_ok=True)
    assert not (OUT/'protocol.json').exists()
    cfg=configuration();old=json.loads((REPO/'workbook/stage68_energy_ml/protocol.json').read_text())
    p=dict(stage=73, frozen_utc=datetime.now(timezone.utc).isoformat(),features=cfg['features'],
        feature_version=cfg['version'],seed=2026110373,bootstrap_seed=2026111373,rounds=400,
        xgboost=old['xgboost'],xgboost_version='2.1.3',protocol_version=2,
        fold_by_group=old['fold_by_group'],fold_counts=old['fold_counts'],arms=ARMS,
        edges_GeV=EDGES.tolist(),outside_edges='separate under/overflow categories, no removal; report support',
        initialization='same explicit unweighted actual-training mean(logE), boost_from_average=0',
        main_candidate='S_cal',calibration='one unit global mean log offset each; OOF raw only',
        A_formula='a=log(pz/((1-y)E)); b=log(Ehat/pz)+log(1-y); e=a+b; signed cross term retained',
        A_strata='cal/eval two lowE bins, all/tail50/non-tail and each source; pz50-75/75-100 x train-only strict Timing raw sum quartiles plus missing; highE, high-y and unconfirmed controls (overlap explicit)',
        A_stop='only reproducible field/unit/alignment error affecting X pauses B; correlation alone does not',
        formal_fits=12,formal_jobs=4,request_cpus=1,request_memory_MB=3000,
        total_CPU_budget_s=3600,wall_per_job_s=1800,worker_timeout_s=1750,callback_CPU_per_job_s=850,
        retained_budget_bytes=20000000,bootstrap_repeats=500,
        decision='original traditional/F7 thresholds; S fixed; no alpha/seed/architecture scan',
        macro='sqrt(equal mean MSE over fixed seven nonempty energy bins); undefined if a required bootstrap bin is empty',
        no_new_ROOT_RDO=True,no_F7_inference=True,no_stage70_augmentation=True,
        followup='S stable and protected -> independent response/support confirmation; F endpoint tradeoff -> stop alpha scans; train-only gain -> new ambiguous-side support; a small b large -> one conditional hypothesis/response/support study')
    save(OUT/'protocol.json',p)
    d,s,x=load();rows=s['row'];role=np.full(len(rows),'unused',dtype='<U6')
    role[d['train_eligible'][rows]]='train';role[d['cal_eligible'][rows]]='cal';role[d['partition'][rows]=='validation']='eval'
    assert [int((role==r).sum()) for r in ['train','cal','eval']]==[41447,8440,14057]
    missing=np.isnan(x).any(1)
    assert missing.sum()==42 and [int((missing&(role==r)).sum()) for r in ['train','cal','eval']]==[21,3,7]
    assert int((missing&(role=='unused')).sum())==11
    use=role!='unused';row=rows[use]
    q={k:d[k][row] for k in ['truth_E_GeV','y_lepton','confirmed','primary_valid','primary_candidates','primary_p_GeV',
                            'source','group','component','incoming','run','eventID','vertex_x_mm','vertex_y_mm','vertex_z_mm']}
    q.update(row=row,role=role[use],x=x[use],pz=d['reco_pz_GeV'][row],missing=missing[use])
    raw=s['raw_charge'][use];status=s['status'][use].astype(int);calo=s['calo_status'][use].astype(int)
    features=cfg['features'];ix={n:i for i,n in enumerate(features)}
    assert len(features)==62 and not set(features)&{'ML_mu_p_GeV','ML_track_p1_GeV','ML_track_pz1_GeV','ML_track_log_p1_over_p0'}
    checks=[]
    for j,n in enumerate(SCINTILLATORS):
        expected=raw[:,j].astype(float).copy();expected[(status[:,j]&WAVE_INVALID)!=0]=np.nan
        expected=clean(expected,cfg['rules'][n+'_raw_charge']).astype('float32')
        np.testing.assert_array_equal(q['x'][:,ix[n+'_raw_charge']],expected)
    for j,n in enumerate(features):
        np.testing.assert_array_equal(clean(q['x'][:,j],cfg['rules'][n]).astype('float32'),q['x'][:,j])
        checks.append(dict(feature=n,invalid_N=int(np.isnan(q['x'][:,j]).sum()),negative_N=int((q['x'][:,j]<0).sum()),
                           minus1_N=int((q['x'][:,j]==-1).sum()),minus999_N=int((q['x'][:,j]==-999).sum())))
    modules=q['x'][:,[ix[f'ML_calo{j}_E_EM_GeV'] for j in range(4)]]
    np.testing.assert_array_equal(np.isnan(q['x'][:,ix['ML_calo_total_E_EM_GeV']]),np.isnan(modules).any(1))
    for j in range(4):assert np.all(np.isnan(modules[(calo[:,j]&FIT_INVALID)!=0,j]))
    np.testing.assert_array_equal(clean([-999,-1,0],dict(domain='signed')),[-999,-1,0])
    np.testing.assert_array_equal(clean([-999,-1,0],dict(domain='nonnegative')),[np.nan,np.nan,0])
    tr=q['role']=='train';_,_,count=weights(q['truth_E_GeV'][tr],1)
    assert count.tolist()==[0,767,3564,9232,13805,10141,3656,282,0]
    np.savez_compressed(CACHE/'input.npz',**q)
    table(OUT/'feature_validity.tsv',checks)
    # Fixed stored predictions only; all joins use global row, never run/event alone.
    f=arrays(REPO/'ml/artifacts/stage56/predictions.npz');offset=json.loads(str(f['metadata_json']))['offset_log']
    pred=np.full(len(row),np.nan)
    for r in ['cal','eval']:
        take=q['role']==r;np.testing.assert_array_equal(row[take],f[r+'_row'])
        pred[take]=f[r+'_raw_log'].mean(0)+offset
    timing=np.sum(q['x'][:,[ix[f'Timing{j}_raw_charge'] for j in range(4)]],axis=1)
    quant=np.quantile(timing[tr&np.isfinite(timing)],[.25,.5,.75])
    cell=np.full(len(row),-1,int);lowpz=(q['pz']>=50)&(q['pz']<100)
    good=lowpz&np.isfinite(timing);cell[good]=4*(q['pz'][good]>=75)+np.searchsorted(quant,timing[good],side='right')
    cell[lowpz&~np.isfinite(timing)]=8
    valid=q['confirmed']&q['primary_valid']&np.isfinite(q['y_lepton'])&(q['y_lepton']>=0)&(q['y_lepton']<1)
    a=np.full(len(row),np.nan);b=a.copy()
    a[valid]=np.log(q['pz'][valid]/((1-q['y_lepton'][valid])*q['truth_E_GeV'][valid]))
    b[valid]=pred[valid]-np.log(q['pz'][valid])+np.log1p(-q['y_lepton'][valid])
    e=pred-np.log(q['truth_E_GeV']);tail=indicator(e,'tail50')
    check=valid&np.isfinite(pred);identity=float(np.max(abs(e[check]-a[check]-b[check])))
    assert identity<1e-12
    states=dict(wave_invalid=((status&WAVE_INVALID)!=0).any(1),fit_failure=((status&(16|32))!=0).any(1),
        negative_valid_raw=((raw<0)&((status&WAVE_INVALID)==0)).any(1),calo_invalid=((calo&FIT_INVALID)!=0).any(1),
        input_missing=q['missing'],unconfirmed=~q['confirmed'])
    values=dict(a=a,b=b,F7_log_correction=pred-np.log(q['pz']),F7_error=e,Timing_raw_sum_pC=timing,
                vertex_z_mm=q['vertex_z_mm'],**{n:q['x'][:,ix[n]] for n in ['LeadTrack_Chi2_NDF','LeadTrack_nLayers',
                    'LeadTrack_r_atMaxRadius','LeadTrack_rVetoNu','LeadTrack_Theta','ML_mu_x0_mm','ML_mu_y0_mm','SpacePoints','nClusters3',
                    'ML_calo_total_E_EM_GeV']})
    evidence=[];feature_groups=[]
    def record(r,label,m):
        v=m&valid;ee=e[v];aa=a[v];bb=b[v]
        z=dict(role=r,stratum=label,**support(q,m),decomposable_N=int(v.sum()),invalid_label_N=int((m&~valid).sum()),
          F7_log_RMSE=float(np.sqrt(np.mean(e[m]**2))) if m.any() else np.nan,
          mean_e2=float(np.mean(ee**2)) if v.any() else np.nan,mean_a2=float(np.mean(aa**2)) if v.any() else np.nan,
          mean_b2=float(np.mean(bb**2)) if v.any() else np.nan,cross_2ab=float(2*np.mean(aa*bb)) if v.any() else np.nan)
        for n,t in states.items():z[n+'_N']=int((m&t).sum())
        for n,t in values.items():
            vv=t[m&np.isfinite(t)];z[n+'_valid_N']=len(vv)
            for tag,qt in zip(['q16','median','q84'],[.16,.5,.84]):z[n+'_'+tag]=float(np.quantile(vv,qt)) if len(vv) else np.nan
        evidence.append(z)
        if ':group=' not in label:
            for j,n in enumerate(features):feature_groups.append(dict(role=r,stratum=label,feature=n,N=int(m.sum()),invalid_N=int((m&np.isnan(q['x'][:,j])).sum())))
    for r in ['cal','eval']:
        rr=q['role']==r
        for lo,hi in [(50,100),(100,200)]:
            base=rr&(q['truth_E_GeV']>=lo)&(q['truth_E_GeV']<hi)
            for label,sel in [('all',np.ones(len(row),bool)),('tail50',tail),('non_tail50',~tail)]:
                record(r,f'E{lo}_{hi}:{label}',base&sel)
                for g in np.unique(q['group'][base]):record(r,f'E{lo}_{hi}:{label}:group={g}',base&sel&(q['group']==g))
            for n,state in states.items():
                record(r,f'E{lo}_{hi}:state={n}',base&state)
                record(r,f'E{lo}_{hi}:not_state={n}',base&~state)
        for c in range(9):
            common=rr&(cell==c)
            for name,sel in [('low50_100',q['truth_E_GeV']<100),('low100_200',(q['truth_E_GeV']>=100)&(q['truth_E_GeV']<200)),
               ('highE',q['truth_E_GeV']>=200),('high_y',q['y_lepton']>=.8),('unconfirmed',~q['confirmed'])]:
                record(r,f'cell{c}:{name}',common&sel)
    table(OUT/'reconstruction_evidence.tsv',[finite(v) for v in evidence]);table(OUT/'feature_strata.tsv',feature_groups)
    selected=(q['role']!='train')&((q['truth_E_GeV']<200)|lowpz)
    event={k:v[selected] for k,v in q.items()}
    event.update(a=a[selected],b=b[selected],F7=pred[selected],cell=cell[selected],raw_charge=raw[selected],status=status[selected],calo_status=calo[selected])
    ART.mkdir(exist_ok=True)
    np.savez_compressed(ART/'reconstruction_events.npz',**event)
    save(OUT/'A_validation.json',dict(identity_max_abs=identity,train_Timing_quartiles_pC=quant.tolist(),
        all_lowE_and_controls_included=True,current_X_reproducible_error_found=False,
        error_scope='cached row/role/status/domain/dependency contracts; no new native file or same-plane covariance verification',
        missing_N=42,eligible_missing_N=[21,3,7],protected_missing_N=11,raw11_exact=True,calo_missing_propagation=True,
        measurement_vectors_used=False,preselection_efficiency='未测量',new_energy_fits=0,new_F7_inference=0,
        input_bytes=(CACHE/'input.npz').stat().st_size,**resources(start)))
    print(json.dumps(json.loads((OUT/'A_validation.json').read_text()),indent=2,ensure_ascii=False))


if __name__=='__main__':main()
