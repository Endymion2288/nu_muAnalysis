"""Exactly three frozen energy arms on the complete original active cohort; Condor only."""
import csv
import gzip
import json
import multiprocessing as mp
import resource
import time
from pathlib import Path

import numpy as np
import xgboost as xgb
from audited_features import configuration, clean
from stage119_curve_common import masks, weights, LAYERS
from stage119_reportcurve import metrics, ci

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage163_energy_ml'
CACHE=ROOT/'ntuples/energy_ml_stage163';ART=ROOT/'ml/artifacts/stage163'
ARMS=['X62','X62_M12','X62_M12_Q4']
A_NAMES=[f'Calo{i}_{v}' for i in range(4) for v in ['raw_valid','fit_invalid','overflow']]
G_NAMES=[f'Calo{i}_asinh_raw_charge_pC' for i in range(4)]
_FIT_DATA=None


def table(name,rows):
    if not rows:return
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with (OUT/name).open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,delimiter='\t',lineterminator='\n',quoting=csv.QUOTE_NONNUMERIC)
        writer.writeheader();writer.writerows(rows)


def load(path):
    with np.load(path,allow_pickle=False) as source:return {k:source[k] for k in source.files if k!='metadata_json'}


def layer_masks(d):
    return dict(masks(d),raw_missing=~np.all(d['raw_valid'],axis=1),fit_invalid=np.any(d['m'][:,1::3]==1,axis=1),overflow=np.any(d['m'][:,2::3]==1,axis=1))


def prepare():
    from stage163_extract import represent
    cpu,tick=time.process_time(),time.perf_counter()
    d=load(ROOT/'ntuples/energy_ml_stage119/old_input.npz');n=len(d['role'])
    assert n==89033 and [int((d['role']==i).sum()) for i in range(4)]==[17657,46575,11612,13189]
    active=d['role']>0;loaded=np.zeros(n,bool)
    raw=np.full((n,4),np.nan);status=raw.copy();rms=raw.copy();m=np.full((n,12),np.nan,'float32');q=np.full((n,4),np.nan,'float32')
    pilot=load(CACHE/'pilot.npz');repeat=load(CACHE/'repeat.npz');lookup={int(row):i for i,row in enumerate(pilot['row'])}
    for k,v in repeat.items():np.testing.assert_array_equal(v,pilot[k][[lookup[int(row)] for row in repeat['row']]])
    checks=[]
    for batch in range(8):
        part=load(CACHE/f'batch_{batch:02d}.npz');rows=part['row'];assert np.all(active[rows]) and not loaded[rows].any()
        loaded[rows]=True;raw[rows]=part['raw'];status[rows]=part['status'];rms[rows]=part['rms'];m[rows]=part['m'];q[rows]=part['q']
        for i,row in enumerate(rows):
            if int(row) in lookup:
                j=lookup[int(row)]
                for k,v in part.items():np.testing.assert_array_equal(v[i],pilot[k][j])
                checks.append(dict(row=int(row),pilot_full_exact=True))
    np.testing.assert_array_equal(loaded,active);assert len(checks)==len(pilot['row'])
    a,b,valid,known=represent(raw[active],status[active],rms[active]);np.testing.assert_array_equal(a,m[active]);np.testing.assert_array_equal(b,q[active])
    raw_valid=np.zeros((n,4),bool);raw_valid[active]=valid
    cfg=configuration();typed=[]
    for j,name in enumerate(cfg['features']):
        np.testing.assert_array_equal(clean(d['x'][active,j],cfg['rules'][name]).astype('float32'),d['x'][active,j]);typed.append(dict(feature=name,typed_clean_unchanged=True))
    d.update(m=m,q=q,raw_valid=raw_valid)
    np.savez_compressed(CACHE/'features.npz',m=m,q=q,raw_valid=raw_valid,raw=raw,status=status,rms=rms,loaded=loaded)
    table('pilot_full_validation.tsv',checks);table('typed_feature_audit.tsv',typed)
    names=cfg['features'];fitted=d['x'][:,[names.index(f'ML_calo{i}_E_EM_GeV') for i in range(4)]]
    support=[]
    for role in [1,2,3]:
        for layer,mask in layer_masks(d).items():
            ix=np.flatnonzero((d['role']==role)&mask)
            support.append(dict(role=role,stratum=layer,N=len(ix),all_raw_available_N=int(raw_valid[ix].all(1).sum()),
                valid_raw_module_N=int(raw_valid[ix].sum()),valid_raw_fitted_missing_module_N=int((raw_valid[ix]&~np.isfinite(fitted[ix])).sum()),
                legal_negative_raw_module_N=int((raw_valid[ix]&(raw[ix]<0)).sum())))
    table('raw_coverage.tsv',support)
    cohort=[]
    for role in [1,2,3]:
        for field in ['component','origin']:
            for value in sorted(set(d[field][d['role']==role])):
                ix=np.flatnonzero((d['role']==role)&(d[field]==value))
                cohort.append(dict(role=role,grouping=field,source=str(value),N=len(ix),
                    all_raw_available_N=int(raw_valid[ix].all(1).sum()),valid_raw_module_N=int(raw_valid[ix].sum()),
                    valid_raw_fitted_missing_module_N=int((raw_valid[ix]&~np.isfinite(fitted[ix])).sum()),
                    legal_negative_raw_module_N=int((raw_valid[ix]&(raw[ix]<0)).sum())))
    table('cohort_support.tsv',cohort)
    result=dict(passed=True,N=n,active_N=int(active.sum()),loaded_N=int(loaded.sum()),pilot_full_checks=len(checks),independent4_exact=True,
        valid_raw_module_N=int(valid.sum()),valid_raw_fitted_missing_module_N=int((raw_valid&~np.isfinite(fitted)).sum()),
        legal_negative_raw_module_N=int((raw_valid&(raw<0)).sum()),all_raw_available_N=int(raw_valid[active].all(1).sum()),
        raw_unavailable_parent_N=int((~raw_valid[active].all(1)).sum()),original_X62_unchanged=True,CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick)
    (OUT/'preparation.json').write_text(json.dumps(result,indent=2)+'\n');return d


def fit(spec):
    arm,d=spec;cpu,tick=time.process_time(),time.perf_counter()
    x=d['x'];names=configuration()['features'].copy()
    if arm!='X62':x=np.column_stack([x,d['m']]);names+=A_NAMES
    if arm=='X62_M12_Q4':x=np.column_stack([x,d['q']]);names+=G_NAMES
    train=d['role']==1;cal=d['role']==2;active=d['role']>0;y=np.log(d['truth_E_GeV']);w=weights(d['incoming'][train])
    dm=xgb.DMatrix(x[train],label=y[train],weight=w,feature_names=names,nthread=1)
    evaluation=xgb.DMatrix(x[active],feature_names=names,nthread=1)
    policy=json.loads((ROOT/'workbook/stage87_energy_ml/protocol.json').read_text())['baseline'];pred=[]
    for seed in policy['seeds']:
        params=dict(policy['xgboost'],seed=seed,base_score=float(np.average(y[train],weights=w)),boost_from_average=0)
        model=xgb.train(params,dm,num_boost_round=policy['rounds']);path=ART/f'{arm}_{seed}.ubj';model.save_model(path)
        again=xgb.Booster(params={'nthread':1});again.load_model(path)
        values=model.predict(evaluation).astype(float);np.testing.assert_array_equal(values,again.predict(evaluation));pred.append(values)
    raw=np.full(len(y),np.nan);raw[active]=np.mean(pred,axis=0)
    offset=float(np.average(y[cal]-raw[cal],weights=weights(d['incoming'][cal])))
    np.savez_compressed(ART/f'{arm}_prediction.npz',raw=raw,cal=raw+offset)
    return dict(arm=arm,features=x.shape[1],train_N=int(train.sum()),cal_N=int(cal.sum()),offset=offset,seeds=policy['seeds'],
        reload_exact=True,CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


def evaluate(d):
    policies={arm:load(ART/f'{arm}_prediction.npz')['cal'] for arm in ARMS}
    cached=load(ROOT/'ml/artifacts/stage87/predictions.npz');active=np.flatnonzero(d['role']>0)
    np.testing.assert_array_equal(cached['row'],active)
    policies['direct_cal']=np.full(len(d['role']),np.nan);policies['direct_cal'][active]=cached['direct_cal']
    np.testing.assert_array_equal(policies['X62'][active],policies['direct_cal'][active])
    policies['traditional']=np.full(len(d['role']),np.nan);policies['traditional'][active]=np.log(d['pz'][active]/.8)
    assert all(np.isnan(v[d['role']==0]).all() for v in policies.values())
    pairs=[];points=[];support=[];gates=[];checks=[]
    comparisons=[('X62_M12_Q4','X62_M12'),('X62_M12_Q4','X62'),('X62_M12','X62')]
    comparisons += [(arm,ref) for arm in ARMS for ref in ['direct_cal','traditional']]
    for role in [1,2,3]:
        selected=np.flatnonzero(d['role']==role);sd={k:v[selected] for k,v in d.items()}
        _,first,gid=np.unique(sd['incoming'],axis=0,return_index=True,return_inverse=True);nk=len(first)
        rng=np.random.default_rng(20261108163+role);draw=np.zeros((500,nk),np.int16)
        for component in sorted(set(sd['component'][first])):
            use=np.flatnonzero(sd['component'][first]==component)
            draw[:,use]=rng.multinomial(len(use),np.full(len(use),1/len(use)),size=500)
        w=weights(sd['incoming']);np.testing.assert_allclose(w,sd['weight'],rtol=0,atol=1e-12);names=list(policies)
        for layer,mask in layer_masks(sd).items():
            use=selected[mask];ww=w[mask];gg=gid[mask]
            if not len(use):support.append(dict(role=role,stratum=layer,N=0,incoming=0));continue
            error=np.column_stack([policies[name][use]-np.log(d['truth_E_GeV'][use]) for name in names]);assert np.isfinite(error).all()
            den=draw@np.bincount(gg,weights=ww,minlength=nk);good=den>0
            agg=np.zeros((nk,len(names)));np.add.at(agg,gg,ww[:,None]*error**2);bt=draw@agg
            base=dict(role=role,stratum=layer,N=len(use),incoming=len(np.unique(gg)),ESS=float(ww.sum()**2/(ww@ww)),valid_draws=int(good.sum()))
            support.append(base)
            for j,name in enumerate(names):
                lo,hi=ci(np.sqrt(bt[good,j]/den[good]));points.append(dict(**base,model=name,**metrics(error[:,j],ww),RMSE_low95=lo,RMSE_high95=hi))
            relative=np.expm1(error);tails={}
            for sign,flag in [('total',abs(relative)>.5),('positive',relative>.5),('negative',relative<-.5)]:
                values=np.zeros_like(agg);np.add.at(values,gg,ww[:,None]*flag);tails[sign]=(values.sum(0)/ww.sum(),draw@values)
            for candidate,reference in comparisons:
                j,k=names.index(candidate),names.index(reference);valid=good&(bt[:,k]>0)
                low,high=ci(np.sqrt(bt[valid,j]/bt[valid,k]));dl,dh=ci((bt[valid,j]-bt[valid,k])/den[valid])
                row=dict(**base,candidate=candidate,reference=reference,RMSE_ratio=float(np.sqrt(agg[:,j].sum()/agg[:,k].sum())),
                    low95=low,high95=high,MSE_delta=float((agg[:,j].sum()-agg[:,k].sum())/ww.sum()),MSE_delta_low95=dl,MSE_delta_high95=dh)
                for sign,(central,values) in tails.items():
                    lo,hi=ci(100*(values[valid,j]-values[valid,k])/den[valid])
                    row.update({sign+'_tail_delta_pp':float(100*(central[j]-central[k])),sign+'_tail_low95_pp':lo,sign+'_tail_high95_pp':hi})
                pairs.append(row)
                if candidate=='X62_M12_Q4' and reference=='X62_M12' and layer in LAYERS:
                    rw=draw[:,gg]*ww;alternative=ci(np.sqrt((rw@error[:,j]**2)/(rw@error[:,k]**2)))
                    delta=max(abs(alternative[0]-low),abs(alternative[1]-high)) if low is not None else None
                    assert delta is None or delta<1e-10
                    checks.append(dict(role=role,stratum=layer,independent_row_space_interval_delta=delta))
        for arm in ARMS:
            for layer in LAYERS:
                reference='traditional' if layer in LAYERS[:2] else 'direct_cal'
                limit=1.05 if reference=='traditional' else 1.01 if layer=='all' else 1.03
                row=next((r for r in pairs if r['role']==role and r['stratum']==layer and r['candidate']==arm and r['reference']==reference),None)
                tail=next((r for r in pairs if r['role']==role and r['stratum']==layer and r['candidate']==arm and r['reference']=='direct_cal'),None)
                gates.append(dict(role=role,arm=arm,stratum=layer,RMSE_upper95=row['high95'] if row else None,limit=limit,
                    RMSE_pass=bool(row and row['high95'] is not None and row['high95']<=limit),
                    tail_pass=bool(tail and all(tail[s+'_tail_high95_pp'] is not None and tail[s+'_tail_high95_pp']<=2 for s in ['total','positive','negative']))))
    table('metrics.tsv',points);table('paired.tsv',pairs);table('support.tsv',support);table('gates.tsv',gates);table('paired_validation.tsv',checks)
    source_rows=[]
    for role in [1,2,3]:
        for field in ['run','component','origin']:
            for value in sorted(set(d[field][d['role']==role])):
                for layer,mask in layer_masks(d).items():
                    ix=np.flatnonzero((d['role']==role)&(d[field]==value)&mask)
                    if not len(ix):continue
                    w=weights(d['incoming'][ix]);target=np.log(d['truth_E_GeV'][ix])
                    row=dict(role=role,grouping=field,source=str(value),stratum=layer,N=len(ix),incoming=len(np.unique(d['incoming'][ix],axis=0)))
                    row.update({arm+'_log_RMSE':float(np.sqrt(np.average((policies[arm][ix]-target)**2,weights=w))) for arm in ARMS})
                    source_rows.append(row)
    table('source_direction.tsv',source_rows)
    np.savez_compressed(ART/'predictions.npz',**policies)
    low=[r for r in pairs if r['candidate']=='X62_M12_Q4' and r['reference']=='X62_M12' and r['role'] in [2,3] and r['stratum'] in LAYERS[:2]]
    protected=[r for r in pairs if r['candidate']=='X62_M12_Q4' and r['reference']=='X62_M12' and r['role'] in [2,3] and r['stratum'] in LAYERS]
    content_tails=bool(len(protected)==16 and all(r[s+'_tail_high95_pp'] is not None and r[s+'_tail_high95_pp']<=2 for r in protected for s in ['total','positive','negative']))
    original_tails=all(r['tail_pass'] for r in gates if r['arm']=='X62_M12_Q4' and r['role'] in [2,3])
    result=dict(passed=True,N=len(d['role']),active_N=len(active),dimensions=dict(X62=62,X62_M12=74,X62_M12_Q4=78),
        joint={f'{role}_{arm}':all(r['RMSE_pass'] and r['tail_pass'] for r in gates if r['role']==role and r['arm']==arm) for role in [2,3] for arm in ARMS},
        content_two_low_5pct_expansion_gate=bool(len(low)==4 and all(r['RMSE_ratio']<=.95 and r['high95'] is not None and r['high95']<1 for r in low) and content_tails and original_tails),
        content_two_low_intervals_below1=bool(len(low)==4 and all(r['high95'] is not None and r['high95']<1 for r in low)),
        X62_vs_direct_max_abs_log_difference=0.,reserved_forward=0,quarantine_predictions=0,new_G4=0,new_independent_nu=0,
        formal_arms=ARMS,energy_models=9,promotion=False,overall_complete=False,
        limitations=['original developed cohort; no independent confirmation','incoming proxy is not full GENIE family',
            'conditional intervals exclude source/refit/research selection and actual correlated response systematics',
            'ordinary Calo raw as-produced definitions; missing original producer kept unknown, no data calibration','raw amplitude is not source ancestry or calibrated noise/muon subtraction; no data purity certification'])
    (OUT/'comparison_summary.json').write_text(json.dumps(result,indent=2)+'\n');print('COMPARISON',result,flush=True)


def fit_arm(arm):
    return fit((arm,_FIT_DATA))


def main():
    global _FIT_DATA
    assert not ART.exists(),'Do not refit the frozen arms to seek a better result'
    cpu,tick=time.process_time(),time.perf_counter();d=prepare();ART.mkdir(parents=True)
    _FIT_DATA=d
    with mp.get_context('fork').Pool(3) as pool:fits=pool.map(fit_arm,ARMS)
    (OUT/'fits.json').write_text(json.dumps(fits,indent=2)+'\n');evaluate(d)
    (OUT/'fit_process.json').write_text(json.dumps(dict(CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,
        RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,scope='Parent CPU excludes pool child fits; GNU/scheduler includes descendants'),indent=2)+'\n')


if __name__=='__main__':main()
