"""Stage82 complete K delivery and frozen half/full pi+K support experiment."""
import argparse
import json
import io
import re
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from audited_features import REPO, configuration, load, clean, SCINTILLATORS, WAVE_INVALID, FIT_INVALID
from alternative_calibration import reference_matrix
from support_augmentation import arrays, save, table, begin, resources, masks as base_masks

OUT = REPO/'workbook/stage82_energy_ml'
CACHE = REPO/'ntuples/energy_ml_stage82'
ART = REPO/'ml/artifacts/stage82'


def job_history(logfile, submission):
    """Use this phase's small event log; requests come from recorded actual ads."""
    history=json.loads(subprocess.check_output(['condor_history','-userlog',str(logfile),'-json'],text=True,timeout=30))
    ads=submission.get('actual_ads',submission.get('ads'))
    for h in history:
        assert h['ClusterId']==submission['cluster']
        request=next(a for a in ads if a['ProcId']==h['ProcId'])
        for key in ['RequestCpus','RequestMemory','MaxRuntime']:
            h[key]=request[key]
        h['request_provenance']='recorded actual submission ClassAds; not inferred from history'
        h['resource_provenance']='condor_history -userlog, this phase event log; RemoteWallClockTime is execute time'
    return history


def read_predictions(arm):
    path=ART/arm/'predictions.npz'
    if path.exists():
        return arrays(path)
    d=arrays(ART/arm/'comparison.npz')
    d['metadata_json']=np.array((OUT/f'fit_{arm}.json').read_text())
    return d


def review_input():
    """Rebuild disposable feature input from retained scalar caches, never ROOT."""
    if (CACHE/'input.npz').exists():
        return arrays(CACHE/'input.npz')
    old,s,x=load();rows=s['row'];tr=old['train_eligible'][rows]
    d=arrays(ART/'full/comparison.npz')
    d.update(old_train_x=x[tr],old_train_y=np.log(old['truth_E_GeV'][rows[tr]]),old_train_row=rows[tr])
    for role in ['cal','eval']:
        idx=np.searchsorted(rows,d[role+'_row'])
        np.testing.assert_array_equal(rows[idx],d[role+'_row'])
        d[role+'_x']=x[idx]
    parts=[]
    for stage in [70,81,82]:
        z=arrays(REPO/f'ntuples/energy_ml_stage{stage}/support.npz');take=z['new_training_support']
        parts.append({k:z[k][take] for k in ['x','incoming','group','component','truth_E_GeV','reco_pz_GeV','y_lepton','confirmed']})
    for key in parts[0]:
        d['new_'+key]=np.concatenate([p[key] for p in parts])
    p=json.loads((OUT/'protocol.json').read_text())
    rng=np.random.default_rng(p['subset_seed']);half=np.zeros(len(d['new_incoming']),bool)
    for group in sorted(set(d['new_group'])):
        idx=np.flatnonzero(d['new_group']==group)
        half[rng.choice(idx,len(idx)//2,replace=False)]=True
    d['half']=half
    return d


def masks(d):
    m = base_masks(d)
    valid = d['confirmed'] & np.isfinite(d['y_lepton']) & (d['y_lepton'] >= 0) & (d['y_lepton'] <= 1)
    for k in ['E50_100', 'E100_200']:
        m[k+'_confirmed_low_transfer'] = m[k] & valid & (d['y_lepton'] < .2)
    for k in ['E200_inf', 'high_y', 'unconfirmed']:
        m['pz50_100_'+('trueE200_inf' if k == 'E200_inf' else k)] = m['pz50_100'] & m[k]
    return m


def check_features(d):
    cfg = configuration()
    assert d['x'].shape == (len(d['incoming']), 62)
    np.testing.assert_array_equal(d['x'][:,0], d['reco_pz_GeV'].astype('float32'))
    assert np.all(d['reco_pz_GeV'] > 50) and np.all(d['incoming'][:,3] > 50000)
    for j, name in enumerate(cfg['features']):
        np.testing.assert_array_equal(clean(d['x'][:,j], cfg['rules'][name]).astype('float32'), d['x'][:,j])
    for j, det in enumerate(SCINTILLATORS):
        raw = d['raw_charge'][:,j].astype('float32').copy()
        raw[(d['status'][:,j].astype(int) & WAVE_INVALID) != 0] = np.nan
        raw[~np.isfinite(raw)] = np.nan
        np.testing.assert_array_equal(raw, d['x'][:,cfg['features'].index(det+'_raw_charge')])
    cols = [cfg['features'].index(f'ML_calo{j}_E_EM_GeV') for j in range(4)]
    assert np.isnan(d['x'][:,cols][(d['calo_status'].astype(int)&FIT_INVALID) != 0]).all()
    np.testing.assert_array_equal(d['x'][:,cfg['features'].index('ML_calo_total_E_EM_GeV')], d['x'][:,cols].astype(float).sum(1).astype('float32'))


def collect():
    start = begin()
    p = json.loads((OUT/'production_protocol.json').read_text())
    fresh = json.loads((OUT/'calo_conditions_qa.json').read_text())
    reference = json.loads((REPO/'workbook/stage70_energy_ml/calo_conditions_qa.json').read_text())
    assert fresh['resolved_tag'] == reference['resolved_tag'] == 'WAVE-Calibration-03-LG'
    assert fresh['measurements'] == reference['measurements']
    sub = json.loads((OUT/'production_submission.json').read_text())
    log=Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage82/logs')/f'k.{sub["cluster"]}.log'
    hist = job_history(log,sub)
    assert len(hist) == 3 and all(h['JobStatus']==4 and h['ExitCode'] == 0 and h['NumJobStarts'] == 1 and h['MaxRuntime'] == 28800 for h in hist)
    (OUT/'production_events.log').write_bytes(log.read_bytes())
    save(OUT/'production_history.json', hist)
    old, _, _ = load()
    known55 = set(map(tuple, old['incoming']))
    known = set(known55)
    previous = {}
    for stage in [70,81]:
        d = arrays(REPO/f'ntuples/energy_ml_stage{stage}/support.npz')
        previous[stage] = set(map(tuple, d['incoming'][d['new_training_support']]))
        known.update(previous[stage])
    seen = {}
    parts, records, flows, summaries = [], [], [], []
    for i, source in enumerate(p['sources']):
        with tarfile.open(CACHE/f'k_{i}.tar.gz') as t:
            dest = CACHE/f'k{i}'
            assert not dest.exists()
            dest.mkdir()
            for member in t.getmembers():
                if member.isdir():
                    continue
                assert member.isfile() and member.name.startswith('result/') and '..' not in member.name
                (dest/Path(member.name).name).write_bytes(t.extractfile(member).read())
        assert (dest/'exitcode.txt').read_text().strip() == '0'
        conditions=(dest/'conditions.txt').read_text()
        assert set(re.findall(r'Global tag: (\S+)',conditions)) == {'OFLCOND-FASER-06'}
        assert 'FASERNU-04' in conditions and 'resolved to WAVE-Calibration-03-LG' in conditions
        calibration = json.loads((dest/'calibration.json').read_text())
        assert calibration['passed']
        d = arrays(dest/'selected.npz')
        md = json.loads(str(d.pop('metadata_json')))
        assert md['source'] == source and md['raw_N'] == 10000 and md['features'] == configuration()['features']
        assert 'validated entries=10000' in (dest/'production_validation.txt').read_text()
        assert np.all(d['run'] == 200081) and len(np.unique(d['eventID'])) == len(d['eventID'])
        assert np.isfinite(d['incoming']).all() and np.all(d['truth_E_GeV'] > 50)
        np.testing.assert_allclose(d['truth_E_GeV'],np.linalg.norm(d['incoming'][:,1:],axis=1)/1000,rtol=1e-10)
        if i == 0:
            with tarfile.open(CACHE/'qa_0.tar.gz') as t:
                with np.load(io.BytesIO(t.extractfile('result/selected.npz').read())) as qa:
                    lookup={int(e):j for j,e in enumerate(d['eventID'])}
                    idx=np.array([lookup[int(e)] for e in qa['eventID']])
                    for key in qa.files:
                        if key != 'metadata_json':
                            np.testing.assert_array_equal(d[key][idx],qa[key])
        check_features(d)
        d['x_produced'] = d['x'].copy()
        d['x'] = reference_matrix(d['x'], source['run'])
        check_features(d)
        for key in ['conditions.txt','production_validation.txt','reco.time','ntuple.time','extract.time','copy.time','reco_tail.txt','ntuple_tail.txt','calibration.json']:
            (OUT/f'k{i}_{key}').write_bytes((dest/key).read_bytes())
        n = len(d['incoming'])
        reuse = np.array([tuple(k) in known for k in d['incoming']])
        repeat,same,cross = [],[],[]
        for k in map(tuple, d['incoming']):
            repeat.append(k in seen)
            same.append(k in seen and seen[k] == i)
            cross.append(k in seen and seen[k] != i)
            seen.setdefault(k,i)
        repeat = np.array(repeat)
        keep = ~(reuse | repeat)
        d.update(new_training_support=keep, known_reuse=reuse, internal_repeat=repeat,
                 within_source_repeat=np.array(same),cross_source_repeat=np.array(cross),
                 known_stage55_reuse=np.array([tuple(k) in known55 for k in d['incoming']]),
                 known_stage70_reuse=np.array([tuple(k) in previous[70] for k in d['incoming']]),
                 known_stage81_reuse=np.array([tuple(k) in previous[81] for k in d['incoming']]),
                 group=np.full(n,source['group']), component=np.full(n,'k'),source_index=np.full(n,i),
                 source_probability=np.full(n,source.get('source_probability',source.get('source_inclusion_probability'))))
        parts.append(d)
        dd = dict(d, pz=d['reco_pz_GeV'], missing=np.isnan(d['x']).any(1))
        for name, mask in masks(dd).items():
            records.append(dict(source=i, group=source['group'], stratum=name, selected_N=int(mask.sum()), new_N=int((keep&mask).sum())))
        for name, count in zip(md['cutflow_names'], md['cutflow_passed']):
            flows.append(dict(source=i,cut=name,passed=count))
        summaries.append(dict(index=i,group=source['group'],raw_N=md['raw_N'],selected_N=n,new_N=int(keep.sum()),known_reuse_N=int(reuse.sum()),reuse55_N=int(d['known_stage55_reuse'].sum()),reuse70_N=int(d['known_stage70_reuse'].sum()),reuse81_N=int(d['known_stage81_reuse'].sum()),internal_repeat_N=int(repeat.sum()),within_source_repeat_N=int(np.sum(same)),cross_source_repeat_N=int(np.sum(cross)),calibration=calibration,extraction=md))
    d = {k:np.concatenate([p[k] for p in parts]) for k in parts[0]}
    keep = d['new_training_support']
    assert len(np.unique(d['incoming'][keep],axis=0)) == int(keep.sum())
    assert not set(map(tuple,d['incoming'][keep])) & known
    assert not (CACHE/'support.npz').exists()
    np.savez_compressed(CACHE/'support.npz', **d, metadata_json=np.array(json.dumps(dict(reference='WAVE-Calibration-01-LG',features=configuration()['features']))))
    table(OUT/'K_support.tsv',records)
    table(OUT/'K_cutflow.tsv',flows)
    validity=[]
    for label,take in [('selected',np.ones(len(keep),bool)),('new',keep)]:
        for j,name in enumerate(configuration()['features']):
            v=d['x'][take,j];f=v[np.isfinite(v)]
            validity.append(dict(scope=label,feature=name,N=len(v),missing_N=int(np.isnan(v).sum()),negative_N=int((v<0).sum()),minus1_N=int((v==-1).sum()),minus999_N=int((v==-999).sum()),minimum=float(f.min()) if len(f) else '未测量',maximum=float(f.max()) if len(f) else '未测量'))
    table(OUT/'K_feature_validity.tsv',validity)
    save(OUT/'K_delivery.json',dict(sources=summaries,selected_N=len(keep),new_N=int(keep.sum()),raw_N=30000,remote_CPU_s=sum(h['RemoteUserCpu']+h['RemoteSysCpu'] for h in hist),remote_wall_sum_s=sum(h['RemoteWallClockTime'] for h in hist),development_only=True,physical_EOS_IO='未测量',**resources(start)))


def prepare():
    import xgboost as xgb
    start = begin()
    cfg = configuration()
    old,s,x = load()
    rows = s['row']
    roles = np.full(len(rows),'unused',dtype='<U6')
    roles[old['train_eligible'][rows]] = 'train'
    roles[old['cal_eligible'][rows]] = 'cal'
    roles[old['partition'][rows] == 'validation'] = 'eval'
    assert [(roles == r).sum() for r in ['train','cal','eval']] == [41447,8440,14057]
    assert [len(np.unique(old['group'][rows[roles == r]])) for r in ['train','cal','eval']] == [91,16,22]
    missing = np.isnan(x).any(1)
    assert missing.sum() == 42 and [(missing & (roles == r)).sum() for r in ['train','cal','eval','unused']] == [21,3,7,11]
    assert not set(cfg['features']) & {'ML_mu_p_GeV','ML_track_p1_GeV','ML_track_pz1_GeV','ML_track_log_p1_over_p0'}
    assert not set(cfg['features']) & {s+'_charge' for s in SCINTILLATORS}
    np.testing.assert_array_equal(clean([-999,-1,0,1],dict(domain='nonnegative')), [np.nan,np.nan,0,1])
    np.testing.assert_array_equal(clean([-999,-1,0],dict(domain='signed')),[-999,-1,0])
    parts = []
    for stage in [70,81,82]:
        d = arrays(REPO/f'ntuples/energy_ml_stage{stage}/support.npz')
        take = d['new_training_support']
        if stage in [70,81]:
            assert take.sum() == (28 if stage == 70 else 742)
        check_features(d)
        parts.append({k:d[k][take] for k in ['x','incoming','group','component','truth_E_GeV','reco_pz_GeV','y_lepton','confirmed']})
    pool = {k:np.concatenate([p[k] for p in parts]) for k in parts[0]}
    n = len(pool['incoming'])
    assert len(np.unique(pool['incoming'],axis=0)) == n
    assert not set(map(tuple,pool['incoming'])) & set(map(tuple,old['incoming']))
    assert set(pool['group']) <= set(old['group'][rows[roles == 'train']])
    for a,b in [('train','cal'),('train','eval'),('cal','eval')]:
        assert not set(map(tuple,old['incoming'][rows[roles==a]])) & set(map(tuple,old['incoming'][rows[roles==b]]))
    rng = np.random.default_rng(2026110382)
    half = np.zeros(n,bool)
    groups = []
    for group in sorted(set(pool['group'])):
        idx = np.flatnonzero(pool['group'] == group)
        half[rng.choice(idx,len(idx)//2,replace=False)] = True
        groups.append(dict(group=group,full_N=len(idx),half_N=len(idx)//2,half_conditional_probability=(len(idx)//2)/len(idx)))
    payload = dict(old_train_x=x[roles == 'train'],old_train_y=np.log(old['truth_E_GeV'][rows[roles == 'train']]),old_train_row=rows[roles=='train'],half=half,**{'new_'+k:v for k,v in pool.items()})
    baseline = arrays(REPO/'ml/artifacts/stage56/predictions.npz')
    md = json.loads(str(baseline['metadata_json']))
    for record, seed in zip(md['fits'], cfg['seeds']):
        assert record['seed'] == seed and record['rounds'] == 400
        assert record['params'] == dict(cfg['xgboost'], seed=seed)
    for role in ['cal','eval']:
        use = roles == role
        idx = rows[use]
        np.testing.assert_array_equal(baseline[role+'_row'],idx)
        payload.update({role+'_row':idx,role+'_x':x[use],role+'_pz':old['reco_pz_GeV'][idx],role+'_missing':missing[use],role+'_F7':baseline[role+'_raw_log'].mean(0)+md['offset_log']})
        for k in ['truth_E_GeV','y_lepton','confirmed','group','source','component','incoming']:
            payload[role+'_'+k] = old[k][idx]
    for arm,keep in [('half',half),('full',np.ones(n,bool))]:
        dm = xgb.DMatrix(np.concatenate([payload['old_train_x'],pool['x'][keep]]),label=np.r_[payload['old_train_y'],np.log(pool['truth_E_GeV'][keep])],feature_names=cfg['features'],nthread=1)
        assert dm.num_col() == 62 and dm.num_row() == 41447+keep.sum() and dm.get_weight().size == 0
    assert not (CACHE/'input.npz').exists()
    np.savez_compressed(CACHE/'input.npz',**payload)
    for k,v in arrays(CACHE/'input.npz').items():
        np.testing.assert_array_equal(v,payload[k])
    support = []
    for label,dd in [('old_train',dict(truth_E_GeV=old['truth_E_GeV'][rows[roles=='train']],pz=old['reco_pz_GeV'][rows[roles=='train']],y_lepton=old['y_lepton'][rows[roles=='train']],confirmed=old['confirmed'][rows[roles=='train']],missing=missing[roles=='train'])),('new_half',{**pool,'pz':pool['reco_pz_GeV'],'missing':np.isnan(pool['x']).any(1)}),('new_full',{**pool,'pz':pool['reco_pz_GeV'],'missing':np.isnan(pool['x']).any(1)})]:
        for key,m in masks(dd).items():
            support.append(dict(sample=label,stratum=key,N=int((m & half).sum()) if label=='new_half' else int(m.sum())))
    table(OUT/'training_support.tsv',support)
    protocol = dict(stage=82,features=cfg['features'],feature_version=cfg['version'],xgboost=cfg['xgboost'],seeds=cfg['seeds'],rounds=400,xgboost_version=xgb.__version__,formal_fits=6,main='full_cal',subset_seed=2026110382,bootstrap_seed=2026111382,bootstrap_replicates=500,groups=groups,new_full_N=n,new_half_N=int(half.sum()),train_N=dict(half=41447+int(half.sum()),full=41447+n),cal_N=8440,eval_N=14057,calibration='one unit global mean log offset per three-seed ensemble on original cal; raw parallel',initialization='original F7 xgb.train defaults, no base_score or boost_from_average override',CPU_total_max_s=1800,MaxRuntime=1800,request_cpus=1,request_memory_MB=3000,retained_max_bytes=20000000,F7_new_fit=0,F7_new_inference=0,locked_test=False)
    assert not (OUT/'protocol.json').exists()
    protocol['frozen_utc']=datetime.now(timezone.utc).isoformat()
    save(OUT/'protocol.json',protocol)
    save(OUT/'input_QA.json',dict(passed=True,old_roles_N=[41447,8440,14057],old_missing_N=[21,3,7,11],features=62,signed_raw11=True,typed_NaN=True,all_stage55_exposure_veto=True,pooled_unique=True,new_K_N=int((pool['component']=='k').sum()),no_fit_DMatrix_arms=2,xgb_version=xgb.__version__,input_bytes=(CACHE/'input.npz').stat().st_size,**resources(start)))


def fit(arm):
    import xgboost as xgb
    start = begin()
    p = json.loads((OUT/'protocol.json').read_text())
    d = arrays(CACHE/'input.npz')
    target = ART/arm
    assert not target.exists()
    target.mkdir(parents=True)
    (target/'started.txt').write_text('fixed three original seeds, no successful fit rerun\n')
    take = d['half'] if arm == 'half' else np.ones(len(d['new_incoming']),bool)
    x = np.concatenate([d['old_train_x'],d['new_x'][take]])
    y = np.r_[d['old_train_y'],np.log(d['new_truth_E_GeV'][take])]
    assert len(y) == p['train_N'][arm] and xgb.__version__ == p['xgboost_version']
    dm = xgb.DMatrix(x,label=y,feature_names=p['features'],nthread=1)
    matrices = {r:xgb.DMatrix(d[r+'_x'],feature_names=p['features'],nthread=1) for r in ['cal','eval']}
    predictions = {r+'_row':d[r+'_row'] for r in matrices}
    values = {r:[] for r in matrices}
    records = []
    train_preds = []
    for seed in p['seeds']:
        ts = begin()
        params = dict(p['xgboost'],seed=seed)
        model = xgb.train(params,dm,num_boost_round=400)
        assert model.num_boosted_rounds() == 400
        model.set_attr(stage82_protocol=json.dumps(p), arm=arm)
        path = target/f'{seed}.ubj'
        model.save_model(path)
        back = xgb.Booster(params={'nthread':1})
        back.load_model(path)
        for r,mat in matrices.items():
            pred = model.predict(mat)
            np.testing.assert_array_equal(pred,back.predict(mat))
            values[r].append(pred.astype(float))
        train_preds.append(model.predict(dm).astype(float))
        records.append(dict(seed=seed,rounds=400,params=params,actual_learner_model_param=json.loads(model.save_config())['learner']['learner_model_param'],model_reload_exact=True,**resources(ts)))
        print(arm,records[-1],flush=True)
    for r in matrices:
        predictions[r+'_raw_log'] = np.array(values[r])
    offset = float(np.mean(np.log(d['cal_truth_E_GeV'])-predictions['cal_raw_log'].mean(0)))
    md = dict(status='completed',formal_fits=3,arm=arm,train_N=len(y),records=records,offset_log=offset,**resources(start))
    assert md['CPU_s'] < 900 and md['wall_s'] < 1800
    np.savez_compressed(target/'predictions.npz',**predictions,metadata_json=np.array(json.dumps(md)))
    save(OUT/f'fit_{arm}.json',md)
    from support_augmentation import metrics
    e = np.exp(y)
    train_rows = []
    for scope,scope_mask in [('all',np.ones(len(y),bool)),('old_nominal',np.arange(len(y))<41447),('new_support',np.arange(len(y))>=41447)]:
        for key,m in dict(all=np.ones(len(y),bool),E50_100=(e>=50)&(e<100),E100_200=(e>=100)&(e<200)).items():
            use=m&scope_mask
            train_rows.append(dict(scope=scope,stratum=key,N=int(use.sum()),**metrics(y[use],np.mean(train_preds,axis=0)[use])))
    table(OUT/f'train_metrics_{arm}.tsv',train_rows)
    (target/'started.txt').unlink()


def report():
    import report_support_augmentation as report
    p = json.loads((OUT/'protocol.json').read_text())
    d = review_input()
    for arm in ['half','full']:
        out = OUT/arm
        out.mkdir(exist_ok=True)
        save(out/'protocol.json',dict(p,figure_title=f'Stage82: {arm} fixed pi+K support; developed evaluation'))
        save(out/'fit.json',json.loads((OUT/f'fit_{arm}.json').read_text()))
        report.OUT, report.ART, report.CACHE = out, ART/arm, CACHE
        report.masks = masks
        report.main()
    # Direct full/half curve with the same fixed source draws.
    from support_augmentation import boot_weights, metrics
    rr = []
    for role in ['cal','eval']:
        dd = {k:d[role+'_'+k] for k in ['truth_E_GeV','pz','y_lepton','confirmed','missing','group','source','component']}
        y = np.log(dd['truth_E_GeV'])
        logs = {}
        for arm in ['half','full']:
            a = read_predictions(arm)
            logs[arm] = a[role+'_raw_log'].mean(0)+json.loads(str(a['metadata_json']))['offset_log']
        groups,gid,w = boot_weights(dd,p['bootstrap_seed']+(role=='cal'),500)
        for key,m in masks(dd).items():
            if not m.any():
                continue
            sums = {arm:w@np.bincount(gid[m],weights=(v[m]-y[m])**2,minlength=len(groups)) for arm,v in logs.items()}
            good = (sums['half'] > 0) & np.isfinite(sums['full'])
            lo,hi = np.quantile(np.sqrt(sums['full'][good]/sums['half'][good]),[.025,.975]) if good.any() else [np.nan,np.nan]
            enough = len(np.unique(gid[m])) >= 3
            rr.append(dict(sample=role,stratum=key,N=int(m.sum()),groups=len(np.unique(gid[m])),full_over_half=float(np.sqrt(np.mean((logs['full'][m]-y[m])**2)/np.mean((logs['half'][m]-y[m])**2))),low95=float(lo) if enough else '未测量',high95=float(hi) if enough else '未测量'))
    table(OUT/'curve.tsv',rr)
    import csv
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,4,figsize=(13,6),constrained_layout=True)
    keys=['E50_100','E100_200','all','E200_inf','pz50_100','high_y','unconfirmed']
    points=[0,p['new_half_N'],p['new_full_N']]
    for ax,key in zip(axes.flat,keys):
        ref='mu' if key in keys[:2] else 'F7'
        vals=[];low=[];high=[]
        for arm in ['half','full']:
            rows=list(csv.DictReader((OUT/arm/'paired.tsv').open(),delimiter='\t'))
            r=next(r for r in rows if r['sample']=='eval' and r['stratum']==key and r['model']=='augmented_cal' and r['reference']==ref)
            vals.append(float(r['RMSE_ratio']));low.append(float(r['RMSE_ratio_low95']));high.append(float(r['RMSE_ratio_high95']))
        dd={k:d['eval_'+k] for k in ['truth_E_GeV','pz','y_lepton','confirmed','missing','group','source','component']}
        m=masks(dd)[key];y=np.log(dd['truth_E_GeV'])
        reference=np.log(dd['pz']/.8) if ref=='mu' else d['eval_F7']
        zero=float(np.sqrt(np.mean((d['eval_F7'][m]-y[m])**2)/np.mean((reference[m]-y[m])**2)))
        ax.plot(points,[zero]+vals,'o-',ms=4)
        ax.errorbar(points[1:],vals,yerr=[np.array(vals)-low,np.array(high)-vals],fmt='none',capsize=3)
        ax.axhline(1.05 if ref=='mu' else (1.01 if key=='all' else 1.03),color='red',ls='--',lw=.8)
        ax.axhline(1,color='black',lw=.5)
        ax.set_title(key);ax.set_ylabel('log-RMSE / '+ref);ax.set_xlabel('Added unique pi+K events')
    axes.flat[-1].axis('off')
    axes.flat[-1].text(0,1,'Fixed F7 policy, developed eval\n3 seeds per added-support size\nPrimary: full, one cal log offset\n500 source-paired fixed-prediction draws\nZero: archived F7, no refit\nRed: original risk limit\nError bars exclude refit/systematics',va='top',fontsize=9)
    fig.savefig(OUT/'learning_curve.png',dpi=150);plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['collect','prepare','fit','report'])
    parser.add_argument('--arm',choices=['half','full'])
    a = parser.parse_args()
    if a.action == 'fit':
        assert a.arm
        fit(a.arm)
    else:
        globals()[a.action]()
