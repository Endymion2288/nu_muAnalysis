"""Stage84: one frozen complete pi+K ensemble; exactly three energy fits."""
import argparse
import json
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from audited_features import REPO, configuration, load
from support_augmentation import arrays, save, table, begin, resources, metrics

OUT = REPO/'workbook/stage84_energy_ml'
CACHE = REPO/'ntuples/energy_ml_stage84'
ART = REPO/'ml/artifacts/stage84'
SPOOL = Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage84')


def prepare():
    import xgboost as xgb
    from k_support_curve import check_features, masks
    start = begin(); OUT.mkdir(exist_ok=True); CACHE.mkdir(exist_ok=True)
    assert not (OUT/'protocol.json').exists()
    request = json.loads((REPO/'workbook/stage83_energy_ml/followup_input_request.json').read_text())
    cfg = configuration(); old, s, x = load(); rows = s['row']
    role = np.full(len(rows),'unused',dtype='<U6')
    role[old['train_eligible'][rows]] = 'train'; role[old['cal_eligible'][rows]] = 'cal'
    role[old['partition'][rows]=='validation'] = 'eval'
    assert [int((role==r).sum()) for r in ['train','cal','eval']] == [41447,8440,14057]
    assert [len(np.unique(old['group'][rows[role==r]])) for r in ['train','cal','eval']] == [91,16,22]
    missing = np.isnan(x).any(1)
    assert [int((missing & (role==r)).sum()) for r in ['train','cal','eval','unused']] == [21,3,7,11]
    parts = []; input_bytes = 0
    for entry in request['inputs']:
        path = REPO/entry['path']; a = arrays(path); take = a['new_training_support']
        assert int(take.sum()) == entry['new_N']; check_features(a)
        input_bytes += path.stat().st_size
        parts.append({k:a[k][take] for k in ['x','incoming','group','component','truth_E_GeV','reco_pz_GeV','y_lepton','confirmed']})
    pool = {k:np.concatenate([p[k] for p in parts]) for k in parts[0]}
    assert len(pool['incoming']) == 7720 and len(np.unique(pool['incoming'],axis=0)) == 7720
    assert not set(map(tuple,pool['incoming'])) & set(map(tuple,old['incoming']))
    assert len(np.unique(pool['group'])) == 26 and int((pool['component']=='k').sum()) == 1016
    assert set(pool['group']) <= set(old['group'][rows[role=='train']])
    for a,b in [('train','cal'),('train','eval'),('cal','eval')]:
        assert not set(map(tuple,old['incoming'][rows[role==a]])) & set(map(tuple,old['incoming'][rows[role==b]]))
    train_x = np.concatenate([x[role=='train'],pool['x']])
    train_y = np.r_[np.log(old['truth_E_GeV'][rows[role=='train']]),np.log(pool['truth_E_GeV'])]
    d = dict(train_x=train_x,train_y=train_y,old_train_row=rows[role=='train'],**{'new_'+k:v for k,v in pool.items()})
    base = arrays(REPO/'ml/artifacts/stage56/predictions.npz'); bm = json.loads(str(base['metadata_json']))
    previous = arrays(REPO/'ml/artifacts/stage82/full/comparison.npz')
    pm = json.loads((REPO/'workbook/stage82_energy_ml/fit_full.json').read_text())
    for record,seed in zip(bm['fits'],request['seeds']):
        assert record['seed']==seed and record['rounds']==400 and record['params']==dict(request['xgboost'],seed=seed)
    for r in ['cal','eval']:
        take = role==r; idx = rows[take]
        np.testing.assert_array_equal(base[r+'_row'],idx); np.testing.assert_array_equal(previous[r+'_row'],idx)
        d.update({r+'_row':idx,r+'_x':x[take],r+'_pz':old['reco_pz_GeV'][idx],r+'_missing':missing[take],
                  r+'_F7':base[r+'_raw_log'].mean(0)+bm['offset_log'],
                  r+'_stage82':previous[r+'_raw_log'].mean(0)+pm['offset_log']})
        for k in ['truth_E_GeV','y_lepton','confirmed','group','source','component','incoming']:
            d[r+'_'+k] = old[k][idx]
    assert cfg['features']==request['features'] and cfg['version']==request['feature_version']
    assert cfg['xgboost']==request['xgboost'] and cfg['seeds']==request['seeds'] and xgb.__version__=='2.1.3'
    dm = xgb.DMatrix(train_x,label=train_y,feature_names=cfg['features'],nthread=1)
    assert dm.num_row()==49167 and dm.num_col()==62 and dm.get_weight().size==0
    assert np.isnan(train_x).any(1).sum()==23
    np.savez_compressed(CACHE/'input.npz',**d)
    for k,v in arrays(CACHE/'input.npz').items(): np.testing.assert_array_equal(v,d[k])
    protocol = dict(request,stage=84,starting_commit='fe89ba9',frozen_utc=datetime.now(timezone.utc).isoformat(),executed=False,
                    formal_fits=3,main='pooled_cal',calibration=request['calibration'],
                    figure_title='Stage84: full pooled pi+K support; developed evaluation',
                    input_scalar_bytes=(CACHE/'input.npz').stat().st_size,retained_max_bytes=20000000)
    save(OUT/'protocol.json',protocol)
    rr=[]
    for label,dd in [('old_train',dict(truth_E_GeV=np.exp(train_y[:41447]),pz=old['reco_pz_GeV'][rows[role=='train']],y_lepton=old['y_lepton'][rows[role=='train']],confirmed=old['confirmed'][rows[role=='train']],missing=missing[role=='train'])),
                      ('new_support',dict(pool,pz=pool['reco_pz_GeV'],missing=np.isnan(pool['x']).any(1)))]:
        for key,m in masks(dd).items(): rr.append(dict(sample=label,stratum=key,N=int(m.sum())))
    table(OUT/'training_support.tsv',rr)
    save(OUT/'input_QA.json',dict(passed=True,train_N=49167,new_N=7720,new_K_N=1016,pooled_groups=26,
         old_roles=[41447,8440,14057],old_groups=[91,16,22],old_missing=[21,3,7,11],new_missing=2,
         full_exposure_key_veto=True,raw_status_typed_policy=True,calo_reference='WAVE-Calibration-01-LG',additional_rescaling=False,
         zero_fit_DMatrix_checked=True,formal_fits=0,F7_inference=0,source_cache_bytes_read=input_bytes,**resources(start)))
    print('Input QA passed: 49167 train, 7720 new incl1016K; zero fits',flush=True)


def fit():
    import xgboost as xgb
    import time
    start = begin(); p = json.loads((OUT/'protocol.json').read_text()); d = arrays(CACHE/'input.npz')
    assert not ART.exists(), 'do not repeat started formal fits'
    ART.mkdir(parents=True); (ART/'started.txt').write_text('exactly three fixed fits; no restart\n')
    assert xgb.__version__==p['xgboost_version'] and d['train_x'].shape==(49167,62)
    dm = xgb.DMatrix(d['train_x'],label=d['train_y'],feature_names=p['features'],nthread=1)
    assert dm.get_weight().size==0
    matrices = {r:xgb.DMatrix(d[r+'_x'],feature_names=p['features'],nthread=1) for r in ['cal','eval']}
    pred = {r+'_row':d[r+'_row'] for r in matrices}; values={r:[] for r in matrices}; records=[]; train=[]
    class Budget(xgb.callback.TrainingCallback):
        def after_iteration(self,model,epoch,evals_log):
            if time.perf_counter()-start[0]>1050 or time.process_time()-start[1]>1050:
                raise RuntimeError('stage84 budget exceeded; no shortened or retried candidate')
            return False
    for seed in p['seeds']:
        ts=begin(); params=dict(p['xgboost'],seed=seed)
        model=xgb.train(params,dm,num_boost_round=p['rounds'],callbacks=[Budget()])
        assert model.num_boosted_rounds()==400
        model.set_attr(stage84_protocol=json.dumps(p),feature_version=p['feature_version'])
        path=ART/f'{seed}.ubj'; model.save_model(path)
        back=xgb.Booster(params={'nthread':1}); back.load_model(path)
        for r,mat in matrices.items():
            v=model.predict(mat); np.testing.assert_array_equal(v,back.predict(mat)); values[r].append(v.astype(float))
        train.append(model.predict(dm).astype(float))
        records.append(dict(seed=seed,rounds=400,params=params,model_reload_exact=True,
            actual_learner_model_param=json.loads(model.save_config())['learner']['learner_model_param'],**resources(ts)))
        print(json.dumps(records[-1]),flush=True)
    for r in matrices: pred[r+'_raw_log']=np.array(values[r])
    offset=float(np.mean(np.log(d['cal_truth_E_GeV'])-pred['cal_raw_log'].mean(0)))
    md=dict(status='completed',formal_fits=3,records=records,offset_log=offset,train_N=49167,**resources(start))
    np.savez_compressed(ART/'predictions.npz',**pred,metadata_json=np.array(json.dumps(md)))
    save(OUT/'fit.json',md)
    trpred=np.mean(train,axis=0); y=d['train_y']; e=np.exp(y); rr=[]
    for scope,m in [('all',np.ones(len(y),bool)),('old_nominal',np.arange(len(y))<41447),('new_support',np.arange(len(y))>=41447)]:
        for key,use in [('all',np.ones(len(y),bool)),('E50_100',(e>=50)&(e<100)),('E100_200',(e>=100)&(e<200))]:
            for policy,delta in [('raw',0.),('cal',offset)]:
                t=m&use; rr.append(dict(scope=scope,stratum=key,policy=policy,N=int(t.sum()),evaluation='in-sample, not OOF',**metrics(y[t],trpred[t]+delta)))
    table(OUT/'train_metrics.tsv',rr); (ART/'started.txt').unlink()


def submit():
    start=begin(); assert not (OUT/'submission.json').exists()
    assert json.loads((OUT/'input_QA.json').read_text())['passed']
    references=[]
    for stage in [70,81,82,83]:
        z=arrays(REPO/f'ntuples/energy_ml_stage{stage}/support.npz')
        m=json.loads(str(z['metadata_json']))
        reference=m.get('reference',m.get('calibration_reference'))
        assert reference=='WAVE-Calibration-01-LG' and m['features']==configuration()['features']
        references.append(dict(stage=stage,reference=reference,additional_rescaling=False))
    paths=['ml/full_support_fit.py','ml/audited_features.py','ml/support_augmentation.py','ml/configs/audited_features.json',
           'ntuples/energy_ml_stage84/input.npz','workbook/stage84_energy_ml/protocol.json']
    archive=REPO/'software/energy-ml-full-support-stage84.tar.gz'; assert not archive.exists()
    with tarfile.open(archive,'w:gz',compresslevel=1) as t:
        for path in paths:t.add(REPO/path,arcname=path)
    check="""import sys,json,numpy as np,xgboost as x
sys.path.insert(0,'ml')
import full_support_fit as f
p=json.load(open('workbook/stage84_energy_ml/protocol.json'))
with np.load('ntuples/energy_ml_stage84/input.npz') as d:
 dm=x.DMatrix(d['train_x'],label=d['train_y'],feature_names=p['features'],nthread=1)
 assert dm.num_row()==49167 and dm.num_col()==62 and dm.get_weight().size==0
 assert np.isnan(d['train_x']).any(1).sum()==23
 for r,n in [('cal',8440),('eval',14057)]:
  assert x.DMatrix(d[r+'_x'],feature_names=p['features'],nthread=1).num_row()==n
 assert len(np.unique(d['new_incoming'],axis=0))==7720 and (d['new_component']=='k').sum()==1016
assert x.__version__==p['xgboost_version']
assert not f.ART.exists()
print('actual payload: full train/cal/eval DMatrix, missing/key/K and version QA passed; zero fits')
"""
    with tempfile.TemporaryDirectory(prefix='full84_payload_') as td:
        with tarfile.open(archive) as t:t.extractall(td,filter='data')
        result=subprocess.check_output([sys.executable,'-c',check],cwd=td,text=True)
    save(OUT/'package_QA.json',dict(passed=True,actual_payload=result,source_references=references,payload_bytes=archive.stat().st_size,model_fits=0,**resources(start)))
    (SPOOL/'logs').mkdir(parents=True,exist_ok=True)
    worker=SPOOL/'worker_v1.sh'; assert not worker.exists()
    worker.write_bytes((REPO/'AnalysisZipFramework/submission/run_ml_full_support.sh').read_bytes())
    sub=REPO/'AnalysisZipFramework/submission/ml_full_support.sub'
    dry=subprocess.check_output(['condor_submit','-dry-run',str(SPOOL/'dryrun.ads'),str(sub)],text=True)
    ads=''.join((SPOOL/'dryrun.ads').read_text().split())
    assert 'MaxRuntime=1800' in ads and 'RequestCpus=1' in ads and 'RequestMemory=3000' in ads
    result=subprocess.check_output(['condor_submit','-terse',str(sub)],text=True); cluster=int(result.split('.')[0])
    save(OUT/'submission.json',dict(cluster=cluster,result=result,paths=paths,payload_bytes=archive.stat().st_size,dryrun=dry))
    actual=json.loads(subprocess.check_output(['condor_q',str(cluster),'-json','-attributes','ClusterId,ProcId,RequestCpus,RequestMemory,MaxRuntime,Args'],text=True))
    record=json.loads((OUT/'submission.json').read_text()); record['actual_ads']=actual; save(OUT/'submission.json',record)
    assert len(actual)==1 and all(1100<=a['MaxRuntime']<=1800 and a['RequestCpus']==1 and a['RequestMemory']==3000 for a in actual)
    print(result,flush=True)


def collect():
    sub=json.loads((OUT/'submission.json').read_text()); logfile=SPOOL/'logs'/f'fit.{sub["cluster"]}.log'
    h=json.loads(subprocess.check_output(['condor_history','-userlog',str(logfile),'-json'],text=True,timeout=30))
    assert len(h)==1 and h[0]['JobStatus']==4 and h[0]['ExitCode']==0 and h[0]['NumJobStarts']==1
    a=sub['actual_ads'][0]; h[0].update({k:a[k] for k in ['RequestCpus','RequestMemory','MaxRuntime']})
    assert h[0]['RemoteUserCpu']+h[0]['RemoteSysCpu']<=1800 and h[0]['RemoteWallClockTime']<=a['MaxRuntime']<=1800
    save(OUT/'history.json',h)
    (OUT/'condor_events.txt').write_text('\n'.join(line.rstrip() for line in logfile.read_text().splitlines())+'\n')
    with tarfile.open(CACHE/'result.tar.gz') as t:
        for m in t.getmembers():
            if m.isdir():continue
            assert m.isfile() and '..' not in m.name and m.name.startswith(('workbook/stage84_energy_ml/','ml/artifacts/stage84/'))
            dest=REPO/m.name; value=t.extractfile(m).read()
            if dest.exists():assert dest.read_bytes()==value
            else:dest.parent.mkdir(exist_ok=True,parents=True); dest.write_bytes(value)
    assert json.loads((OUT/'fit.json').read_text())['formal_fits']==3
    print('one job once exit0; three fixed fits collected')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','fit','submit','collect'])
    globals()[p.parse_args().action]()
