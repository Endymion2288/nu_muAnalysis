"""Stage83 complete remaining frozen pi PHYS sources; no energy model operations."""
import argparse
import csv
import json
import resource
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import uproot

from audited_features import REPO, SCINTILLATORS, WAVE_INVALID, FIT_INVALID, configuration, clean, load
from extract_alternative_support import extract
from collect_alternative_support import masks
from support_augmentation import arrays, begin, resources, save, table

OUT = REPO/'workbook/stage83_energy_ml'
CACHE = REPO/'ntuples/energy_ml_stage83'
SPOOL = Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage83')
REFERENCE = 330/.07129999995231628


def plan():
    return json.loads((OUT/'source_plan.json').read_text())


def check_features(d):
    cfg = configuration()
    assert d['x'].shape == (len(d['incoming']),62)
    assert np.all(d['reco_pz_GeV'] > 50) and np.all(d['incoming'][:,3] > 50000)
    np.testing.assert_array_equal(d['x'][:,0],d['reco_pz_GeV'].astype('float32'))
    assert np.isfinite(d['incoming']).all()
    np.testing.assert_allclose(d['truth_E_GeV'],np.linalg.norm(d['incoming'][:,1:],axis=1)/1000,rtol=1e-10)
    for j,name in enumerate(cfg['features']):
        np.testing.assert_array_equal(clean(d['x'][:,j],cfg['rules'][name]).astype('float32'),d['x'][:,j])
    for j,det in enumerate(SCINTILLATORS):
        v=d['raw_charge'][:,j].astype('float32').copy()
        v[(d['status'][:,j].astype(int)&WAVE_INVALID)!=0]=np.nan
        v[~np.isfinite(v)]=np.nan
        np.testing.assert_array_equal(d['x'][:,cfg['features'].index(det+'_raw_charge')],v)
        if j<2:
            assert np.isnan(d['x'][(d['status'][:,j].astype(int)&WAVE_INVALID)!=0,cfg['features'].index(det+'_reduced_charge')]).all()
    cols=[cfg['features'].index(f'ML_calo{i}_E_EM_GeV') for i in range(4)]
    assert np.isnan(d['x'][:,cols][(d['calo_status'].astype(int)&FIT_INVALID)!=0]).all()
    np.testing.assert_array_equal(d['x'][:,cfg['features'].index('ML_calo_total_E_EM_GeV')],d['x'][:,cols].astype(float).sum(1).astype('float32'))


def calo_check(path, entry_stop=None):
    with uproot.open(path,array_cache=None) as f:
        a=f['nt'].arrays([f'Calo{j}_{k}' for j in range(4) for k in ['charge','E_EM','status']],entry_stop=entry_stop,library='np')
        requested=int(f.file.source.num_requested_bytes)
    rows=[]
    for j in range(4):
        q,e,st=(a[f'Calo{j}_{k}'] for k in ['charge','E_EM','status'])
        use=(st==0)&np.isfinite(q)&np.isfinite(e)&(abs(q)>1e-6)
        if use.any():
            np.testing.assert_allclose(e[use].astype(float)/q[use],REFERENCE,rtol=2e-6,atol=1e-3)
        rows.append(dict(module=j,N=int(use.sum()),median_MeV_per_pC=float(np.median(e[use].astype(float)/q[use])) if use.any() else None))
    return dict(reference='WAVE-Calibration-01-LG',rescaled=False,checks=rows,requested_uproot_bytes=requested)


def prepare():
    start=begin();OUT.mkdir(exist_ok=True);CACHE.mkdir(exist_ok=True)
    assert not (OUT/'source_plan.json').exists()
    request=json.loads((REPO/'workbook/stage82_energy_ml/followup_input_request.json').read_text())
    previous=json.loads((REPO/'workbook/stage81_energy_ml/source_plan.json').read_text())
    sources=request['sources']
    expected=[s for s in previous['candidates'] if s['component']=='pi' and s['group'] not in {'pi:00100-00109','pi:00250-00259','pi:00440-00449'}]
    assert sources==expected and len(sources)==20
    assert sum(s['file_bytes'] for s in sources)==611988745
    assert len({s['group'] for s in sources})==20
    for i,s in enumerate(sources):
        roles=previous['roles_by_canonical_group'][s['group']]
        assert set(roles)==set(s['historical_roles']) and 'train' in roles
        assert not set(roles)&{'test','validation','calibration'}
        assert Path(s['input']).stat().st_size==s['file_bytes']
        s.update(index=i,source_probability=1.,conditional_event_probability=1.,role='development_enrichment')
    save(OUT/'source_plan.json',dict(stage=83,frozen_utc=datetime.now(timezone.utc).isoformat(),starting_commit='1f3af68',sources=sources,
        selection='all20 remaining frozen known compatible pi train sources; no outcome/source-yield selection',
        source_probability_scope='conditional on the stage81 known available legal pool and prior deliveries; not physical flux weight',
        shards=[list(range(i*5,(i+1)*5)) for i in range(4)],QA_entries_per_source=2,QA_identities_max=40,
        event_data_read_before_freeze=0,logical_PHYS_bytes=611988745,request=request,
        features=configuration()['features'],feature_version=configuration()['version'],**resources(start)))
    print('Frozen all20 sources, four contiguous five-source shards; zero event reads')


def qa(shard):
    import ROOT
    from track_response import TRACK_BRANCHES
    ROOT.gROOT.SetBatch(True)
    p=plan()
    for i in p['shards'][shard]:
        start=begin();source=p['sources'][i]
        assert not (OUT/f'qa{i}.json').exists()
        with uproot.open(source['input'],array_cache=None) as f:
            t=f['nt'];branches=set(t.keys());N=t.num_entries
            required=['run','eventID','Track_PropagationError','Track_isForward']+TRACK_BRANCHES
            required += [s+'_'+k for s in SCINTILLATORS for k in ['raw_charge','charge','status']]
            required += [f'Calo{j}_{k}' for j in range(4) for k in ['charge','E_EM','status']]
            assert not set(required)-branches and N==10000
            scalar=t.arrays(['run','eventID']+[s+'_'+k for s in SCINTILLATORS for k in ['raw_charge','status']],entry_stop=2,library='np')
            requested=int(f.file.source.num_requested_bytes)
        assert np.all(scalar['run']==source['run'])
        calo=calo_check(source['input'],2)
        with tempfile.TemporaryDirectory(prefix='pi83_QA_') as td:
            tmp=Path(td);native=ROOT.TFile.Open(source['input']);tree=native.Get('nt')
            target=ROOT.TFile.Open(str(tmp/'qa.root'),'RECREATE');target.cd();clone=tree.CloneTree(2);clone.Write()
            clonebytes=int(native.GetBytesRead());target.Close();native.Close()
            extract(i,tmp/'qa.root',tmp/'qa.npz',qa=True,source=source)
            d=arrays(tmp/'qa.npz');md=json.loads(str(d.pop('metadata_json')));check_features(d)
            assert md['raw_N']==2 and md['features']==p['features']
            assert np.isin(d['eventID'],scalar['eventID']).all()
            np.savez_compressed(CACHE/f'qa{i}.npz',**d)
        save(OUT/f'qa{i}.json',dict(index=i,identities=[dict(run=int(r),eventID=int(e)) for r,e in zip(scalar['run'],scalar['eventID'])],
            input_entries=[0,1],raw_N=N,branches_N=len(branches),missing_required=[],scalar_requested_bytes=requested,
            ROOT_clone_requested_bytes=clonebytes,calibration=calo,extraction=md,original62_raw_typed_NaN_passed=True,
            production='known local d32b0ff3 nominal merge withoutIFT family, original manifest and stage70 paired01 closure; full historical response snapshot unproven',
            model_fits=0,**resources(start)))
        print('QA complete',i,md['selected_N'],flush=True)


def extract_source(index, qa_input=None, output=None):
    source=plan()['sources'][index]
    path=qa_input or Path(source['input'])
    output=output or CACHE/f'source{index}.npz'
    extract(index,path,output,qa=bool(qa_input),source=source)
    d=arrays(output);md=json.loads(str(d.pop('metadata_json')))
    check_features(d)
    md['calibration_QA']=calo_check(path)
    assert md['features']==plan()['features']
    # A compact rewritten scalar file carries full-source unit evidence with it.
    np.savez_compressed(output,**d,metadata_json=np.array(json.dumps(md)))


def submit():
    start=begin();p=plan();assert not (OUT/'submission.json').exists()
    qa=[json.loads((OUT/f'qa{i}.json').read_text()) for i in range(20)]
    assert sum(len(q['identities']) for q in qa)==40
    assert all(q['original62_raw_typed_NaN_passed'] and q['raw_N']==10000 for q in qa)
    protocol=dict(stage=83,frozen_utc=datetime.now(timezone.utc).isoformat(),sources=p['sources'],shards=p['shards'],features=p['features'],feature_version=p['feature_version'],
        QA_identities=40,full_source_events=200000,model_fits=0,F7_inference=0,request_cpus=1,request_memory_MB=3000,request_disk_MB=200,
        MaxRuntime_ceiling_s=1800,worker_CPU_soft_hard_s=[400,430],total_CPU_max_s=1800,worker_wall_timeout_s=1100,
        reference='native01-LG, no scale conversion',retained_limit_bytes=10000000,input_limit_bytes=10000000000,
        identity='all stage55 exposure+stage70new28+stage81new742+stage82new1016+stable source-internal/cross incoming veto',
        QA_cost_basis='same-source2event selection/62 readout extraction across20 sources; same recorded compatible family, no energy fitting',
        limitations='development only; full parent/subfile/seed and common response unproven; full yields/costs not yet measured')
    save(OUT/'protocol.json',protocol)
    paths=['build/analysis','AnalysisZipFramework/config','AnalysisZipFramework/include','ml/pi_support_delivery.py',
        'ml/extract_alternative_support.py','ml/audited_features.py','ml/collect_alternative_support.py','ml/support_augmentation.py',
        'ml/alternative_calibration.py','ml/frozen_evaluation.py','ml/track_response.py','ml/train_bdt.py',
        'ml/configs/audited_features.json','ml/configs/baseline.yaml','ml/configs/track_response.yaml',
        'workbook/stage83_energy_ml/source_plan.json','workbook/stage83_energy_ml/protocol.json']
    paths += [str(a.relative_to(REPO)) for a in (REPO/'build').glob('*.so')]
    archive=REPO/'software/energy-ml-pi-support-stage83.tar.gz';assert not archive.exists()
    with tarfile.open(archive,'w:gz',compresslevel=1) as t:
        for name in paths:t.add(REPO/name,arcname=name)
    # Actual transferred package startup on the same frozen identities, no extras.
    import ROOT
    ROOT.gROOT.SetBatch(True);checks=[]
    with tempfile.TemporaryDirectory(prefix='pi83_payload_') as td:
        tmp=Path(td)
        with tarfile.open(archive) as t:t.extractall(tmp,filter='data')
        for i in [0,19]:
            source=p['sources'][i];native=ROOT.TFile.Open(source['input']);tree=native.Get('nt')
            target=ROOT.TFile.Open(str(tmp/f'qa{i}.root'),'RECREATE');target.cd();clone=tree.CloneTree(2);clone.Write()
            requested=int(native.GetBytesRead());target.Close();native.Close()
            subprocess.run([sys.executable,str(tmp/'ml/pi_support_delivery.py'),'extract','--index',str(i),'--qa-input',str(tmp/f'qa{i}.root'),'--output',str(tmp/f'package{i}.npz')],check=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
            a=arrays(tmp/f'package{i}.npz');b=arrays(CACHE/f'qa{i}.npz')
            for key in b:np.testing.assert_array_equal(a[key],b[key])
            md=json.loads(str(a['metadata_json']))
            checks.append(dict(index=i,exact_all_arrays=True,ROOT_clone_requested_bytes=requested,Uproot_requested_bytes=md['requested_uproot_bytes']+md['calibration_QA']['requested_uproot_bytes'],child_CPU_s=md['child_user_s']+md['child_system_s']))
    save(OUT/'package_QA.json',dict(passed=True,actual_payload=True,payload_bytes=archive.stat().st_size,records=checks,new_identities=0,**resources(start)))
    (SPOOL/'logs').mkdir(parents=True,exist_ok=True)
    worker=SPOOL/'worker_v1.sh';assert not worker.exists()
    worker.write_bytes((REPO/'AnalysisZipFramework/submission/run_ml_pi_support.sh').read_bytes())
    submit_path=REPO/'AnalysisZipFramework/submission/ml_pi_support.sub'
    dry=subprocess.check_output(['condor_submit','-dry-run',str(SPOOL/'dryrun.ads'),str(submit_path)],text=True)
    ads=''.join((SPOOL/'dryrun.ads').read_text().split())
    assert 'MaxRuntime=1800' in ads and 'RequestCpus=1' in ads and 'RequestMemory=3000' in ads
    result=subprocess.check_output(['condor_submit','-terse',str(submit_path)],text=True)
    cluster=int(result.split('.')[0])
    # Persist submission before the adaptive resource check to avoid losing job IDs.
    save(OUT/'submission.json',dict(cluster=cluster,result=result,paths=paths,payload_bytes=archive.stat().st_size,dryrun=dry))
    actual=json.loads(subprocess.check_output(['condor_q',str(cluster),'-json','-attributes','ClusterId,ProcId,MaxRuntime,RequestCpus,RequestMemory,Args'],text=True))
    record=json.loads((OUT/'submission.json').read_text());record.update(actual_ads=actual,**resources(start));save(OUT/'submission.json',record)
    assert len(actual)==4 and all(1100<=a['MaxRuntime']<=1800 and a['RequestCpus']==1 and a['RequestMemory']==3000 for a in actual)
    print(result,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','qa','extract','submit'])
    parser.add_argument('--shard',type=int,choices=range(4))
    parser.add_argument('--index',type=int,choices=range(20))
    parser.add_argument('--qa-input',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.action=='qa':
        assert args.shard is not None
        qa(args.shard)
    elif args.action=='extract':
        assert args.index is not None
        extract_source(args.index,args.qa_input,args.output)
    else:
        globals()[args.action]()
