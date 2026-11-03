"""Stage82 independent pooled-key/subset, model, offset and paired risk verification."""
import csv
import json
import numpy as np
import xgboost as xgb
from audited_features import REPO,load,configuration
from alternative_calibration import reference_matrix
from support_augmentation import arrays,save,begin,resources,boot_weights,indicator,TAILS
from k_support_curve import OUT,CACHE,ART,masks,review_input,read_predictions


def main():
    start=begin()
    p=json.loads((OUT/'protocol.json').read_text())
    d=review_input()
    old,s,x=load()
    rows=s['row']
    tr=old['train_eligible'][rows]
    np.testing.assert_array_equal(d['old_train_x'],x[tr])
    np.testing.assert_array_equal(d['old_train_y'],np.log(old['truth_E_GeV'][rows[tr]]))
    pool=[]
    prior=[old['incoming']]
    for stage in [70,81,82]:
        z=arrays(REPO/f'ntuples/energy_ml_stage{stage}/support.npz')
        keep=z['new_training_support']
        pool.append(z['incoming'][keep])
        if stage==82:
            np.testing.assert_array_equal(z['x'],reference_matrix(z['x_produced'],200081))
            before=np.concatenate(prior);joint=np.vstack([before,z['incoming']])
            _,first=np.unique(joint,axis=0,return_index=True)
            expected=np.zeros(len(z['incoming']),bool)
            expected[first[first>=len(before)]-len(before)]=True
            np.testing.assert_array_equal(expected,z['new_training_support'])
        else:
            prior.append(z['incoming'][keep])
    np.testing.assert_array_equal(d['new_incoming'],np.concatenate(pool))
    combined=np.vstack([old['incoming'],d['new_incoming']])
    _,inv=np.unique(combined,axis=0,return_inverse=True)
    assert not np.isin(inv[len(old['incoming']):],inv[:len(old['incoming'])]).any()
    assert len(np.unique(inv[len(old['incoming']):]))==len(d['new_incoming'])
    rng=np.random.default_rng(p['subset_seed'])
    half=np.zeros(len(d['new_incoming']),bool)
    for group in sorted(set(d['new_group'])):
        idx=np.flatnonzero(d['new_group']==group)
        half[rng.choice(idx,len(idx)//2,replace=False)]=True
    np.testing.assert_array_equal(half,d['half'])
    base=arrays(REPO/'ml/artifacts/stage56/predictions.npz')
    bm=json.loads(str(base['metadata_json']))
    checks=[]
    bootstrap_rows=0
    maxdiff=0.
    for arm in ['half','full']:
        a=read_predictions(arm)
        md=json.loads(str(a['metadata_json']))
        assert md['formal_fits']==3 and len(md['records'])==3 and md['status']=='completed'
        for j,seed in enumerate(p['seeds']):
            assert md['records'][j]['params']==dict(p['xgboost'],seed=seed)
            model=xgb.Booster(params={'nthread':1})
            model.load_model(ART/arm/f'{seed}.ubj')
            assert model.num_boosted_rounds()==400 and model.feature_names==p['features']
            assert json.loads(model.attr('stage82_protocol'))==p and model.attr('arm')==arm
            for role in ['cal','eval']:
                idx=np.searchsorted(rows,d[role+'_row'])
                np.testing.assert_array_equal(rows[idx],d[role+'_row'])
                np.testing.assert_array_equal(x[idx],d[role+'_x'])
                np.testing.assert_array_equal(a[role+'_row'],base[role+'_row'])
                np.testing.assert_array_equal(d[role+'_F7'],base[role+'_raw_log'].mean(0)+bm['offset_log'])
                pred=model.predict(xgb.DMatrix(x[idx],feature_names=p['features'],nthread=1))
                np.testing.assert_array_equal(pred,a[role+'_raw_log'][j])
            checks.append(dict(arm=arm,seed=seed,rounds=400,predictions_exact=True,params_exact=True))
        residual=np.log(d['cal_truth_E_GeV'])-a['cal_raw_log'].mean(0)
        assert float(residual.mean())==md['offset_log']
        assert abs(np.mean(residual-md['offset_log']))<1e-12
        # Verify every reported paired interval directly from per-event weights,
        # independently of the report's group-sum matrix calculation.
        tab=list(csv.DictReader((OUT/arm/'paired.tsv').open(),delimiter='\t'))
        for role in ['cal','eval']:
            dd={k:d[role+'_'+k] for k in ['truth_E_GeV','pz','y_lepton','confirmed','missing','group','source','component']}
            groups,gid,w=boot_weights(dd,p['bootstrap_seed']+(role=='cal'),500)
            yy=np.log(dd['truth_E_GeV'])
            logs=dict(mu=np.log(dd['pz']/.8),F7=d[role+'_F7'],augmented_raw=a[role+'_raw_log'].mean(0),augmented_cal=a[role+'_raw_log'].mean(0)+md['offset_log'])
            for key,m in masks(dd).items():
                if not m.any() or len(np.unique(gid[m]))<3:
                    continue
                ww=w[:,gid[m]].astype(float)
                den=ww.sum(1)
                for name in ['augmented_raw','augmented_cal']:
                    for ref in ['mu','F7']:
                        row=next(t for t in tab if t['sample']==role and t['stratum']==key and t['model']==name and t['reference']==ref)
                        e,r=logs[name][m]-yy[m],logs[ref][m]-yy[m]
                        num=ww@(e*e);reference=ww@(r*r)
                        good=(den>0)&(reference>0)
                        lo,hi=np.quantile(np.sqrt(num[good]/reference[good]),[.025,.975])
                        diffs=[abs(lo-float(row['RMSE_ratio_low95'])),abs(hi-float(row['RMSE_ratio_high95']))]
                        for tail in TAILS:
                            delta=100*(indicator(e,tail).astype(float)-indicator(r,tail).astype(float))
                            low,high=np.quantile((ww@delta)[good]/den[good],[.025,.975])
                            diffs.extend([abs(low-float(row[tail+'_low95_pp'])),abs(high-float(row[tail+'_high95_pp']))])
                        maxdiff=max(maxdiff,max(diffs))
                        assert max(diffs)<1e-10
                        bootstrap_rows+=1
    curve=list(csv.DictReader((OUT/'curve.tsv').open(),delimiter='\t'))
    curve_checks=0
    for role in ['cal','eval']:
        dd={k:d[role+'_'+k] for k in ['truth_E_GeV','pz','y_lepton','confirmed','missing','group','source','component']}
        groups,gid,w=boot_weights(dd,p['bootstrap_seed']+(role=='cal'),500)
        y=np.log(dd['truth_E_GeV']);logs={}
        for arm in ['half','full']:
            a=read_predictions(arm)
            logs[arm]=a[role+'_raw_log'].mean(0)+json.loads(str(a['metadata_json']))['offset_log']
        for key,m in masks(dd).items():
            if not m.any() or len(np.unique(gid[m]))<3:continue
            weights=w[:,gid[m]].astype(float)
            v={arm:weights@((pred[m]-y[m])**2) for arm,pred in logs.items()}
            good=v['half']>0
            lo,hi=np.quantile(np.sqrt(v['full'][good]/v['half'][good]),[.025,.975])
            row=next(t for t in curve if t['sample']==role and t['stratum']==key)
            delta=max(abs(lo-float(row['low95'])),abs(hi-float(row['high95'])))
            assert delta<1e-10
            maxdiff=max(maxdiff,delta);curve_checks+=1
    save(OUT/'validation.json',dict(passed=True,models=checks,all_reported_source_draws=500,paired_rows_checked=bootstrap_rows,full_half_curve_intervals_checked=curve_checks,max_interval_absolute_difference=maxdiff,all_stage55_exposure_veto=True,subset_reproduced=True,old_roles_and_features_exact=True,F7_old_predictions_exact=True,new_F7_inference=0,calibration_payload_conversion_exact=True,**resources(start)))
    print('Stage82 six models, pooled identities, source subsets and all paired intervals verified')


if __name__=='__main__':
    main()
