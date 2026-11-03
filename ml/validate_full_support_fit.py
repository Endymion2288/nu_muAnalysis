"""Stage84 independent pooled input, model readback and per-event risk checks."""
import csv
import gzip
import json

import numpy as np
import xgboost as xgb

from audited_features import REPO, load, configuration, SCINTILLATORS
from full_support_fit import OUT, ART, CACHE
from k_support_curve import check_features, masks
from support_augmentation import arrays, save, begin, resources, boot_weights, TAILS, LOW, COST
from report_full_support_fit import review


def read(name):
    path=OUT/(name+'.tsv')
    with path.open() if path.exists() else gzip.open(str(path)+'.gz','rt') as stream:
        return list(csv.DictReader(stream,delimiter='\t'))


def direct_metrics(y,pred):
    if not len(y):return None
    e=pred-y; r=np.expm1(e); q=np.quantile(r,[.16,.5,.84]); loss=e*e
    result=dict(log_RMSE=float(np.sqrt(np.mean(loss))),mean_bias_pct=float(100*r.mean()),median_bias_pct=float(100*q[1]),R68_pct=float(50*(q[2]-q[0])))
    for tail in TAILS:
        threshold=.5 if '50' in tail else 1.
        use=r>threshold if tail.startswith('positive') else r < -threshold if tail.startswith('negative') else abs(r)>threshold
        result[tail+'_pct']=float(100*use.mean())
        result[tail+'_loss_fraction']=float(loss[use].sum()/loss.sum()) if loss.sum() else 0.
    return result


def main():
    start=begin(); p=json.loads((OUT/'protocol.json').read_text()); d,a,md=review(); cfg=configuration()
    old,s,x=load(); rows=s['row'];tr=old['train_eligible'][rows]
    assert [int(tr.sum()),int(old['cal_eligible'][rows].sum()),int((old['partition'][rows]=='validation').sum())]==[41447,8440,14057]
    assert p['features']==cfg['features'] and p['seeds']==cfg['seeds'] and p['xgboost']==cfg['xgboost']
    assert not set(p['features']) & {'ML_mu_p_GeV','ML_track_p1_GeV','ML_track_pz1_GeV','ML_track_log_p1_over_p0'}
    assert not set(p['features']) & {k+'_charge' for k in SCINTILLATORS}
    parts=[]
    for stage,n in [(70,28),(81,742),(82,1016),(83,5934)]:
        z=arrays(REPO/f'ntuples/energy_ml_stage{stage}/support.npz');keep=z['new_training_support'];assert keep.sum()==n;check_features(z)
        parts.append({k:z[k][keep] for k in ['x','incoming','truth_E_GeV','reco_pz_GeV','y_lepton','confirmed','group','component']})
    pool={k:np.concatenate([z[k] for z in parts]) for k in parts[0]}
    known=old['incoming'];_,inv=np.unique(np.vstack([known,pool['incoming']]),axis=0,return_inverse=True)
    assert not np.isin(inv[len(known):],inv[:len(known)]).any() and len(np.unique(inv[len(known):]))==7720
    tx=np.concatenate([x[tr],pool['x']]);ty=np.r_[np.log(old['truth_E_GeV'][rows[tr]]),np.log(pool['truth_E_GeV'])]
    assert tx.shape==(49167,62) and np.isnan(tx).any(1).sum()==23 and (pool['component']=='k').sum()==1016
    if (CACHE/'input.npz').exists():
        np.testing.assert_array_equal(d['train_x'],tx);np.testing.assert_array_equal(d['train_y'],ty)
        for k,v in pool.items():np.testing.assert_array_equal(d['new_'+k],v)
    original=arrays(REPO/'ml/artifacts/stage56/predictions.npz');om=json.loads(str(original['metadata_json']))
    prev=arrays(REPO/'ml/artifacts/stage82/full/comparison.npz');pm=json.loads((REPO/'workbook/stage82_energy_ml/fit_full.json').read_text())
    trainmat=xgb.DMatrix(tx,feature_names=p['features'],nthread=1);trainpred=[];models=[]
    for j,seed in enumerate(p['seeds']):
        assert md['records'][j]['params']==dict(p['xgboost'],seed=seed) and md['records'][j]['rounds']==400
        model=xgb.Booster(params={'nthread':1});model.load_model(ART/f'{seed}.ubj')
        assert model.num_boosted_rounds()==400 and model.feature_names==p['features'] and json.loads(model.attr('stage84_protocol'))==p
        trainpred.append(model.predict(trainmat).astype(float))
        for role in ['cal','eval']:
            idx=np.searchsorted(rows,d[role+'_row']);np.testing.assert_array_equal(rows[idx],d[role+'_row'])
            np.testing.assert_array_equal(original[role+'_row'],d[role+'_row']);np.testing.assert_array_equal(prev[role+'_row'],d[role+'_row'])
            np.testing.assert_array_equal(d[role+'_F7'],original[role+'_raw_log'].mean(0)+om['offset_log'])
            np.testing.assert_array_equal(d[role+'_stage82'],prev[role+'_raw_log'].mean(0)+pm['offset_log'])
            predicted=model.predict(xgb.DMatrix(x[idx],feature_names=p['features'],nthread=1))
            np.testing.assert_array_equal(a[role+'_raw_log'][j],predicted)
        models.append(dict(seed=seed,rounds=400,cal_eval_predictions_exact=True,parameters_exact=True))
    assert md['formal_fits']==3 and not (ART/'started.txt').exists()
    offset=float(np.mean(np.log(d['cal_truth_E_GeV'])-a['cal_raw_log'].mean(0)));assert offset==md['offset_log']
    metricrows=read('metrics');paired=read('paired');source=read('source_metrics');seedrows=read('seed_metrics')
    paired_lookup={(r['sample'],r['stratum'],r['model'],r['reference']):r for r in paired}
    maximum=0.;intervalrows=0;metriccount=0
    for role in ['cal','eval']:
        dd={k:d[role+'_'+k] for k in ['truth_E_GeV','pz','y_lepton','confirmed','missing','group','source','component']}
        yy=np.log(dd['truth_E_GeV']);raw=a[role+'_raw_log'].mean(0)
        logs=dict(mu=np.log(dd['pz']/.8),F7=d[role+'_F7'],stage82_full=d[role+'_stage82'],pooled_raw=raw,pooled_cal=raw+offset)
        mm=masks(dd);groups,gid,w=boot_weights(dd,p['bootstrap_seed']+(role=='cal'),500)
        assert len(groups)==(16 if role=='cal' else 22)
        for r in [v for v in metricrows+source+seedrows if v['sample']==role]:
            take=mm[r['stratum']].copy()
            if 'group' in r:take &= dd['group']==r['group']
            pred=a[role+'_raw_log'][p['seeds'].index(int(r['seed']))]+offset if 'seed' in r else logs[r['model']]
            assert int(r['N'])==take.sum();expected=direct_metrics(yy[take],pred[take])
            if expected is None:assert r['log_RMSE']=='未测量'
            else:
                assert all(abs(float(r[k])-v)<1e-10 for k,v in expected.items());metriccount+=1
        for key,m in mm.items():
            if not m.any():continue
            # Explicit per-event source weights, independent of reporter group sums.
            weights=w[:,gid[m]].astype(float);den=weights.sum(1)
            errors={name:pred[m]-yy[m] for name,pred in logs.items()}
            squares={name:weights@(e*e) for name,e in errors.items()}
            for name in ['pooled_raw','pooled_cal']:
                for ref in ['mu','F7','stage82_full']:
                    row=paired_lookup[(role,key,name,ref)];good=(den>0)&(squares[ref]>0)
                    ratio=float(np.sqrt(np.mean(errors[name]**2)/np.mean(errors[ref]**2)))
                    assert abs(ratio-float(row['RMSE_ratio']))<1e-12
                    if len(np.unique(gid[m]))<3:
                        assert row['RMSE_ratio_high95']=='未测量';continue
                    lo,hi=np.quantile(np.sqrt(squares[name][good]/squares[ref][good]),[.025,.975])
                    differences=[abs(lo-float(row['RMSE_ratio_low95'])),abs(hi-float(row['RMSE_ratio_high95']))]
                    for tail in TAILS:
                        def tailmask(e):
                            r=np.expm1(e);v=.5 if '50' in tail else 1.
                            return r>v if tail.startswith('positive') else r < -v if tail.startswith('negative') else abs(r)>v
                        delta=100*(tailmask(errors[name]).astype(float)-tailmask(errors[ref]).astype(float))
                        low,high=np.quantile((weights@delta)[good]/den[good],[.025,.975])
                        differences.extend([abs(low-float(row[tail+'_low95_pp'])),abs(high-float(row[tail+'_high95_pp']))])
                        assert abs(float(row[tail+'_delta_pp'])-delta.mean())<1e-12
                    maximum=max(maximum,max(differences));assert max(differences)<1e-10;intervalrows+=1
    meantrain=np.mean(trainpred,axis=0);energy=np.exp(ty)
    for r in read('train_metrics'):
        m=np.ones(len(ty),bool) if r['scope']=='all' else np.arange(len(ty))<41447 if r['scope']=='old_nominal' else np.arange(len(ty))>=41447
        if r['stratum']=='E50_100':m &= (energy>=50)&(energy<100)
        if r['stratum']=='E100_200':m &= (energy>=100)&(energy<200)
        expected=direct_metrics(ty[m],meantrain[m]+(offset if r['policy']=='cal' else 0.))
        assert int(r['N'])==m.sum() and all(abs(float(r[k])-v)<1e-10 for k,v in expected.items())
    decision=json.loads((OUT/'decisions.json').read_text())
    for name in ['pooled_raw','pooled_cal']:
        result=decision['versions'][name]
        for key in LOW:assert result['recovery'][key]==(float(paired_lookup[('eval',key,name,'mu')]['RMSE_ratio_high95'])<=1.05)
        for key,limit in COST.items():assert result['protection'][key]==(float(paired_lookup[('eval',key,name,'F7')]['RMSE_ratio_high95'])<=limit)
        for key in LOW+list(COST):
            for tail in TAILS[:3]:assert result['tail50'][key][tail]==(float(paired_lookup[('eval',key,name,'F7')][tail+'_high95_pp'])<=2)
        assert result['pass_all']==(all(result['recovery'].values()) and all(result['protection'].values()) and all(all(v.values()) for v in result['tail50'].values()))
    h=json.loads((OUT/'history.json').read_text());assert len(h)==1 and h[0]['NumJobStarts']==1 and h[0]['ExitCode']==0
    assert h[0]['RequestCpus']==1 and h[0]['RequestMemory']==3000 and h[0]['RemoteWallClockTime']<=h[0]['MaxRuntime']<=1800
    assert h[0]['RemoteUserCpu']+h[0]['RemoteSysCpu']<1800
    save(OUT/'validation.json',dict(passed=True,models=models,train_N=49167,all_new_unique_N=7720,retained_K_N=1016,
        original_features_and_roles_exact=True,no_second_Calo_scale=True,new_keys_old_exposure_intersection_N=0,
        metrics_rows_independently_checked=metriccount,paired_interval_rows_checked=intervalrows,source_draws=500,
        max_interval_absolute_difference=maximum,cal_offset_exact=True,train_metrics_in_sample_verified=True,
        original_gates_independently_verified=True,once_exit0=True,formal_fits=3,F7_inference=0,**resources(start)))
    print('Stage84 input, three models, all metrics and fixed-prediction source intervals independently verified')


if __name__=='__main__':main()
