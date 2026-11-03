"""Stage87: user-authorized regrouping and retraining of existing audited caches."""
import argparse
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import numpy as np

from audited_features import REPO, build, configuration
from latent_transfer_diagnostics import check_x, response
from support_augmentation import arrays, save, table, begin, resources

OUT=REPO/'workbook/stage87_energy_ml'
CACHE=REPO/'ntuples/energy_ml_stage87'
ART=REPO/'ml/artifacts/stage87'
SPOOL=Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage87')
INPUTS=['ntuples/energy_ml_stage55/dataset.npz','ntuples/energy_ml_stage56/readout.npz']
INPUTS += [f'ntuples/energy_ml_stage{s}/support.npz' for s in [70,81,82,83]]
CODE=['ml/resplit_energy.py','ml/transfer_posterior.py','ml/report_resplit_energy.py','ml/validate_resplit_energy.py',
      'ml/latent_transfer_diagnostics.py','ml/audited_features.py','ml/support_augmentation.py','ml/configs/audited_features.json']


def qa():
    start=begin(); OUT.mkdir(parents=True,exist_ok=True)
    old=arrays(REPO/INPUTS[0]);s=arrays(REPO/INPUTS[1])
    pos=np.linspace(0,len(s['row'])-1,30,dtype=int)
    small={k:v[pos] for k,v in s.items() if k!='metadata_json'}
    check_x(build(old,small)); ids=[dict(origin=55,row=int(j)) for j in small['row']]
    for stage,n in [(70,2),(81,2),(82,3),(83,3)]:
        z=arrays(REPO/f'ntuples/energy_ml_stage{stage}/support.npz');ix=np.flatnonzero(z['new_training_support'])[:n]
        check_x(z['x'][ix]);ids += [dict(origin=stage,row=int(j)) for j in ix]
    assert len(ids)==40
    save(OUT/'identity_QA.json',dict(passed=True,identities=ids,distinct_identities=40,new_fits=0,new_ROOT_reads=0,
         input_manifest_logical_bytes=sum((REPO/f).stat().st_size for f in INPUTS),**resources(start)))
    print('40 cache-identity QA passed, zero fits',flush=True)


def split_groups(groups,seed):
    unique=np.unique(groups);assigned={};rng=np.random.default_rng(seed)
    for comp in ['pi','k','charm']:
        gg=np.array([g for g in unique if g.startswith(comp+':')]);assert len(gg)>=3
        gg=rng.permutation(gg);nt=max(1,int(round(.15*len(gg))));nc=max(1,int(round(.15*len(gg))))
        for j,g in enumerate(gg):assigned[str(g)]=3 if j<nt else 2 if j<nt+nc else 1
    assert set(assigned)==set(unique)
    return np.array([assigned[str(g)] for g in groups],dtype=np.int8),assigned


def connected_blocks(group,key):
    gg,gi=np.unique(group,return_inverse=True);parent=np.arange(len(gg))
    def root(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]];i=parent[i]
        return i
    first={}
    for g,k in zip(gi,key):
        k=int(k);g=int(g)
        if k in first:
            a,b=root(g),root(first[k]);parent[max(a,b)]=min(a,b)
        else:first[k]=g
    roots=np.array([root(i) for i in range(len(gg))]);names={}
    for r in np.unique(roots):
        comps={g.split(':',1)[0] for g in gg[roots==r]};comp=next(iter(comps)) if len(comps)==1 else 'mixed'
        names[r]=comp+':block:'+str(gg[r])
    return np.array([names[roots[g]] for g in gi])


def prepare():
    start=begin();OUT.mkdir(parents=True,exist_ok=True);CACHE.mkdir(parents=True,exist_ok=True)
    assert not (CACHE/'input.npz').exists()
    p=json.loads((OUT/'protocol.json').read_text());old=arrays(REPO/INPUTS[0]);s=arrays(REPO/INPUTS[1]);x=build(old,s);check_x(x)
    keys=['truth_E_GeV','y_lepton','primary_p_GeV','primary_valid','primary_candidates','confirmed','incoming','group','component','run','eventID']
    row=s['row'];base={k:old[k][row] for k in keys}
    base.update(x=x,pz=old['reco_pz_GeV'][row],origin=np.full(len(row),55,np.int16),origin_row=row,
         source=old['source'][row].astype('int64'),nominal=old['nominal'][row])
    base.update(response(x,s['raw_charge'],s['status'],s['calo_status']))
    parts=[base];origin_counts=[dict(origin=55,selected_cached=len(old['incoming']),compatible_rows=len(row),unavailable_audited_readout=len(old['incoming'])-len(row))]
    for stage in [70,81,82,83]:
        z=arrays(REPO/f'ntuples/energy_ml_stage{stage}/support.npz');m=z['new_training_support'];check_x(z['x'][m])
        a={k:z[k][m] for k in keys};n=int(m.sum())
        a.update(x=z['x'][m],pz=z['reco_pz_GeV'][m],origin=np.full(n,stage,np.int16),origin_row=np.flatnonzero(m),
                 source=z['source_index'][m].astype('int64'),nominal=np.zeros(n,bool))
        a.update(response(a['x'],z['raw_charge'][m],z['status'][m],z['calo_status'][m]));parts.append(a)
        origin_counts.append(dict(origin=stage,selected_cached=n,compatible_rows=n,unavailable_audited_readout=0))
    d={k:np.concatenate([a[k] for a in parts]) for k in base};assert len(d['pz'])==89033
    assert np.isfinite(d['incoming']).all() and np.isfinite(d['truth_E_GeV']).all() and (d['truth_E_GeV']>0).all()
    assert (d['pz']>50).all(); check_x(d['x'])
    unique,keyid=np.unique(d['incoming'],axis=0,return_inverse=True);d['key_id']=keyid
    initial,assignment=split_groups(d['group'],p['split_seed'])
    # Source split is fixed without energy/target information. All collisions go to
    # their highest-priority role; lower-priority SOURCE rows remain in quarantine.
    priority=np.zeros(len(unique),np.int8);np.maximum.at(priority,keyid,initial)
    d['initial_role']=initial;d['role']=np.where(initial==priority[keyid],initial,0).astype('int8')
    d['weight']=np.zeros(len(initial),float)
    for code in [1,2,3]:
        m=d['role']==code;c=np.bincount(keyid[m],minlength=len(unique));d['weight'][m]=1/c[keyid[m]]
    d['block']=np.full(len(initial),'quarantine',dtype='<U80')
    for code in [1,2,3]:
        m=d['role']==code;d['block'][m]=connected_blocks(d['group'][m],keyid[m])
    for a,b in [(1,2),(1,3),(2,3)]:
        assert not set(d['group'][d['role']==a])&set(d['group'][d['role']==b])
        assert not set(keyid[d['role']==a])&set(keyid[d['role']==b])
    f=d['y_lepton'];mu=(1-f)*d['truth_E_GeV']
    d['label_physical']=d['primary_valid']&(d['primary_candidates']==1)&np.isfinite(mu)&(mu>.1056583755)&(f>=0)&(f<1)
    d['mu_truth_GeV']=mu
    rr=[];ss=[]
    for name,code in [('quarantine',0),('train',1),('cal',2),('test',3)]:
        m=d['role']==code;n=int(m.sum());w=d['weight'][m]
        rr.append(dict(role=name,N=n,groups=len(np.unique(d['group'][m])),unique_incoming=len(np.unique(keyid[m])),
            connected_blocks=len(np.unique(d['block'][m])) if code else 0,
            loss_weight_sum=float(w.sum()),ESS_records=float(w.sum()**2/(w@w)) if w.any() else 0,
            missing=int(d['input_missing'][m].sum()),K_N=int((d['component'][m]=='k').sum()),
            E50_100=int((m&(d['truth_E_GeV']>=50)&(d['truth_E_GeV']<100)).sum()),
            E100_200=int((m&(d['truth_E_GeV']>=100)&(d['truth_E_GeV']<200)).sum()),
            low_pz=int((m&(d['pz']<100)).sum()),low_pz_highE=int((m&(d['pz']<100)&(d['truth_E_GeV']>=200)).sum())))
    for g,code in sorted(assignment.items()):
        m=d['group']==g;ss.append(dict(group=g,initial_role={1:'train',2:'cal',3:'test'}[code],N=int(m.sum()),retained=int((m&(d['role']>0)).sum()),quarantine=int((m&(d['role']==0)).sum())))
    table(OUT/'split_counts.tsv',rr);table(OUT/'source_assignment.tsv',ss);table(OUT/'input_coverage.tsv',origin_counts)
    split_keys=['origin','origin_row','source','run','eventID','incoming','group','component','initial_role','role','key_id','weight','block']
    np.savez_compressed(CACHE/'split.npz',**{k:d[k] for k in split_keys})
    np.savez_compressed(CACHE/'input.npz',**d)
    save(OUT/'split_audit.json',dict(passed=True,input_records=len(initial),unique_incoming=len(unique),
         roles=rr,source_and_incoming_disjoint=True,quarantine_reason='exact incoming appears in higher-priority assigned source role; test>cal>train',
         per_incoming_training_weight='each role sum weights per key =1; keep all within-role response views',
         targets_used_to_assign_split=False,old_roles_preserved=False,all_existing_cached_selected_records=103468,
         unavailable_raw_status_records=14435,unknown_transfer_labels=int((~d['label_physical']).sum()),
         new_generation=0,new_ROOT_reads=0,**resources(start)))
    print(json.dumps(rr,indent=2),flush=True)


def submit(phase):
    start=begin();assert phase in ['prepare','fit'];assert not (OUT/f'submission_{phase}.json').exists()
    if phase=='prepare':qa()
    else:assert json.loads((OUT/'split_audit.json').read_text())['passed']
    paths=[f for f in CODE if (REPO/f).exists()]+['workbook/stage87_energy_ml/protocol.json']
    paths += INPUTS if phase=='prepare' else ['ntuples/energy_ml_stage87/input.npz','ntuples/energy_ml_stage87/split.npz']
    archive=REPO/f'software/energy-ml-resplit-stage87-{phase}.tar.gz'
    with tarfile.open(archive,'w:gz',compresslevel=1) as t:
        for path in paths:t.add(REPO/path,arcname=path)
    with tempfile.TemporaryDirectory(prefix='resplit87_package_') as td:
        with tarfile.open(archive) as t:t.extractall(td,filter='data')
        command=[sys.executable,'ml/resplit_energy.py','qa'] if phase=='prepare' else [sys.executable,'ml/transfer_posterior.py','qa']
        result=subprocess.check_output(command,cwd=td,text=True)
    save(OUT/f'package_QA_{phase}.json',dict(passed=True,actual_payload=result,archive_bytes=archive.stat().st_size,new_fits=0,**resources(start)))
    (SPOOL/'logs').mkdir(parents=True,exist_ok=True);worker=SPOOL/'worker_v1.sh'
    if not worker.exists():worker.write_bytes((REPO/'AnalysisZipFramework/submission/run_ml_resplit_energy.sh').read_bytes())
    result=subprocess.check_output(['condor_submit','-terse','-append',f'phase = {phase}',str(REPO/'AnalysisZipFramework/submission/ml_resplit_energy.sub')],text=True)
    cluster=int(result.split('.')[0]);ads=json.loads(subprocess.check_output(['condor_q',str(cluster),'-json','-attributes','ClusterId,ProcId,RequestCpus,RequestMemory,MaxRuntime,Args'],text=True))
    save(OUT/f'submission_{phase}.json',dict(cluster=cluster,result=result,actual_ads=ads,paths=paths))
    assert len(ads)==1 and ads[0]['RequestCpus']==1 and ads[0]['RequestMemory']==3000 and ads[0]['MaxRuntime']<=3600
    print(result,flush=True)


def collect(phase,result=None):
    sub=json.loads((OUT/f'submission_{phase}.json').read_text());log=SPOOL/'logs'/f'{phase}.{sub["cluster"]}.log'
    h=json.loads(subprocess.check_output(['condor_history','-userlog',str(log),'-json'],text=True,timeout=30))
    save(OUT/f'history_{phase}.json',h)
    assert len(h)==1 and h[0]['ExitCode']==0 and h[0]['NumJobStarts']==1
    assert h[0]['RemoteUserCpu']+h[0]['RemoteSysCpu']<=3600
    (OUT/f'condor_{phase}.txt').write_text('\n'.join(s.rstrip() for s in log.read_text().splitlines())+'\n')
    with tarfile.open(Path(result) if result else CACHE/f'result_{phase}.tar.gz') as t:
        for m in t.getmembers():
            if m.isdir():continue
            assert m.isfile() and '..' not in m.name and m.name.startswith(('workbook/stage87_energy_ml/','ntuples/energy_ml_stage87/','ml/artifacts/stage87/'))
            path=REPO/m.name;value=t.extractfile(m).read();path.parent.mkdir(exist_ok=True,parents=True)
            if path.exists():assert path.read_bytes()==value
            else:path.write_bytes(value)
    print(phase,'one job once exit0, collected',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['qa','prepare','fit','submit','collect']);p.add_argument('--phase',choices=['prepare','fit']);p.add_argument('--result',help='optional local XRootD-retrieved archive when EOS FUSE metadata is stale')
    a=p.parse_args()
    if a.action=='collect':collect(a.phase,a.result)
    elif a.action=='submit':submit(a.phase)
    elif a.action=='fit':
        from transfer_posterior import fit
        fit()
    else:globals()[a.action]()
