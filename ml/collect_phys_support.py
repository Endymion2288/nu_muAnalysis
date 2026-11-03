"""Stage81 complete-source collection, exact incoming veto, support and cost tables."""
import csv
import json
import subprocess
import tarfile
import tempfile
from pathlib import Path
import numpy as np
from audited_features import REPO,SCINTILLATORS,WAVE_INVALID,FIT_INVALID,configuration,clean,load
from support_augmentation import begin,resources,save,arrays,table
from collect_alternative_support import masks

OUT=REPO/'workbook/stage81_energy_ml'
CACHE=REPO/'ntuples/energy_ml_stage81'


def main():
    start=begin();p=json.loads((OUT/'protocol.json').read_text());sub=json.loads((OUT/'submission.json').read_text())
    attrs='ClusterId,ProcId,JobStatus,ExitCode,NumJobStarts,RequestCpus,RequestMemory,MaxRuntime,RemoteUserCpu,RemoteSysCpu,RemoteWallClockTime,ResidentSetSize'
    hist=json.loads(subprocess.check_output(['condor_history',str(sub['cluster']),'-limit','2','-json','-attributes',attrs],text=True))
    assert len(hist)==2 and all(h['ExitCode']==0 and h['NumJobStarts']==1 and h['RequestCpus']==1 and h['RequestMemory']==3000 and h['MaxRuntime']==3600 for h in hist)
    save(OUT/'history.json',hist)
    parts=[];metadata=[];cutflow=[];cfg=configuration()
    for i in p['compatible_source_indices']:
        path=CACHE/f'source_{i}.tar.gz'
        with tempfile.TemporaryDirectory(prefix='stage81_collect_') as td:
            if not path.exists():
                path=Path(td)/f'source_{i}.tar.gz'
                subprocess.run(['xrdcp','--silent',f'root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage81/source_{i}.tar.gz',str(path)],check=True)
            with tarfile.open(path) as t:
                for member in t.getmembers():
                    if member.isdir():continue
                    assert member.isfile() and '..' not in member.name and member.name.startswith(('ntuples/energy_ml_stage81/','workbook/stage81_energy_ml/'))
                    dest=REPO/member.name;contents=t.extractfile(member).read()
                    if dest.exists():assert dest.read_bytes()==contents
                    else:dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(contents)
        d=arrays(CACHE/f'source{i}.npz');md=json.loads(str(d.pop('metadata_json')));metadata.append(md)
        assert md['source']==p['sources'][i] and md['raw_N']==10000 and md['features']==cfg['features']
        assert np.all(d['reco_pz_GeV']>50) and np.all(d['incoming'][:,3]>50000)
        for j,s in enumerate(SCINTILLATORS):
            expected=d['raw_charge'][:,j].astype('float32');expected[(d['status'][:,j].astype(int)&WAVE_INVALID)!=0]=np.nan
            np.testing.assert_array_equal(d['x'][:,cfg['features'].index(s+'_raw_charge')],expected)
        for j,name in enumerate(cfg['features']):np.testing.assert_array_equal(clean(d['x'][:,j],cfg['rules'][name]).astype('float32'),d['x'][:,j])
        cols=[cfg['features'].index(f'ML_calo{j}_E_EM_GeV') for j in range(4)]
        np.testing.assert_array_equal(d['x'][:,cfg['features'].index('ML_calo_total_E_EM_GeV')],d['x'][:,cols].astype(float).sum(1).astype('float32'))
        for j,col in enumerate(cols):assert np.isnan(d['x'][(d['calo_status'][:,j].astype(int)&FIT_INVALID)!=0,col]).all()
        n=len(d['run']);d.update(source_index=np.full(n,i),component=np.full(n,p['sources'][i]['component']),group=np.full(n,p['sources'][i]['group']),
            source_probability=np.full(n,p['sources'][i]['source_probability']),conditional_event_probability=np.ones(n))
        parts.append(d)
        for name,passed in zip(md['cutflow_names'],md['cutflow_passed']):cutflow.append(dict(source=i,component=p['sources'][i]['component'],cut=name,passed=passed))
        save(OUT/f'extraction{i}.json',md)
    d={k:np.concatenate([x[k] for x in parts]) for k in parts[0]}
    old,_,_=load();previous=arrays(REPO/'ntuples/energy_ml_stage70/support.npz');prev=previous['incoming'][previous['new_training_support']]
    assert len(prev)==28
    stage55=set(map(tuple,old['incoming']));stage70=set(map(tuple,prev));known=stage55|stage70
    keys=list(map(tuple,d['incoming']));seen={};reuse55=[];reuse70=[];internal=[];same=[];cross=[]
    for key,src in zip(keys,d['source_index']):
        reuse55.append(key in stage55);reuse70.append(key in stage70);internal.append(key in seen)
        same.append(key in seen and seen[key]==src);cross.append(key in seen and seen[key]!=src)
        seen.setdefault(key,int(src))
    reuse55=np.array(reuse55);reuse70=np.array(reuse70);internal=np.array(internal)
    keep=~(reuse55|reuse70|internal)
    np.testing.assert_array_equal(np.flatnonzero(~internal),np.sort(np.unique(d['incoming'],axis=0,return_index=True)[1]))
    joint=np.vstack([old['incoming'],prev,d['incoming']]);_,inv=np.unique(joint,axis=0,return_inverse=True)
    np.testing.assert_array_equal(reuse55|reuse70,np.isin(inv[len(old['incoming'])+28:],inv[:len(old['incoming'])+28]))
    assert len(set(k for k,m in zip(keys,keep) if m))==int(keep.sum()) and not set(k for k,m in zip(keys,keep) if m)&known
    d.update(known_stage55_reuse=reuse55,known_stage70_reuse=reuse70,internal_repeat=internal,
             within_source_repeat=np.array(same),cross_source_repeat=np.array(cross),new_training_support=keep)
    rows=[];identities=[];validity=[];rawvalid=[];mm=masks(d)
    for k in ['E50_100','E100_200']:mm['pz50_100_'+k]=mm['pz50_100']&mm[k]
    for label,take in [(f'source{i}',d['source_index']==i) for i in range(4)]+[('pi',d['component']=='pi'),('k',d['component']=='k'),('all',np.ones(len(keys),bool))]:
        measured=label not in ['source2','source3','k']
        for state,select in [('selected',np.ones(len(keys),bool)),('known55',reuse55),('known70',reuse70),('internal',internal),('new',keep)]:
            for key,m in mm.items():
                use=take&select&m;y=d['y_lepton'];valid=d['confirmed']&np.isfinite(y)&(y>=0)&(y<=1)
                rows.append(dict(scope=label,state=state,stratum=key,measured=measured,N=int(use.sum()) if measured else '未测量',
                    sources=len(np.unique(d['source_index'][use])) if measured else '未测量',groups=len(np.unique(d['group'][use])) if measured else '未测量',
                    unique_incoming=len(set(k for k,b in zip(keys,use) if b)) if measured else '未测量',
                    confirmed_N=int((use&d['confirmed']).sum()) if measured else '未测量',valid_y_N=int((use&valid).sum()) if measured else '未测量',
                    interpretation='complete delivered development source' if measured else 'incompatible backward-only K PHYS; full selected support unmeasured'))
        if not measured:continue
        identities.append(dict(scope=label,selected_N=int(take.sum()),stage55_reuse_N=int((take&reuse55).sum()),stage70_reuse_N=int((take&reuse70).sum()),
            within_source_repeat_N=int((take&d['within_source_repeat']).sum()),cross_source_repeat_N=int((take&d['cross_source_repeat']).sum()),new_N=int((take&keep).sum())))
        for state,select in [('selected',np.ones(len(keys),bool)),('new',keep)]:
            use=take&select
            for j,name in enumerate(cfg['features']):
                v=d['x'][use,j];f=v[np.isfinite(v)]
                validity.append(dict(scope=label,state=state,feature=name,N=len(v),missing_N=int(np.isnan(v).sum()),negative_N=int((v<0).sum()),minus1_N=int((v==-1).sum()),minus999_N=int((v==-999).sum()),
                    minimum=float(f.min()) if len(f) else '未测量',median=float(np.median(f)) if len(f) else '未测量',maximum=float(f.max()) if len(f) else '未测量'))
            for j,s in enumerate(SCINTILLATORS):
                v=d['raw_charge'][use,j];st=d['status'][use,j].astype(int)
                rawvalid.append(dict(scope=label,state=state,detector=s,N=len(v),negative_N=int((v<0).sum()),wave_invalid_N=int(((st&WAVE_INVALID)!=0).sum()),
                    fit_invalid_but_raw_valid_N=int((((st&48)!=0)&((st&WAVE_INVALID)==0)&np.isfinite(v)).sum())))
    tr=old['nominal']&old['train_eligible'];assert tr.sum()==41447
    # Context uses the same original feature/missing definition, independently loaded.
    dataset,supp,x=load();rows_old=supp['row'];where={int(r):i for i,r in enumerate(rows_old)}
    take=np.flatnonzero(tr);oldx=x[np.array([where[int(r)] for r in take])]
    contextdata=dict(x=oldx,truth_E_GeV=old['truth_E_GeV'][tr],reco_pz_GeV=old['reco_pz_GeV'][tr],y_lepton=old['y_lepton'][tr],confirmed=old['confirmed'][tr])
    cm=masks(contextdata)
    for k in ['E50_100','E100_200']:cm['pz50_100_'+k]=cm['pz50_100']&cm[k]
    context=[]
    for key,m in cm.items():
        n=int(m.sum());nnew=int((keep&mm[key]).sum());context.append(dict(stratum=key,original_train_N=n,new_N=nnew,increment_pct=100*nnew/n if n else '未测量'))
    for name,values in [('support',rows),('identities',identities),('cutflow',cutflow),('feature_validity',validity),('raw_validity',rawvalid),('training_context',context)]:table(OUT/(name+'.tsv'),values)
    summary=dict(raw_N=sum(m['raw_N'] for m in metadata),selected_N=len(keys),new_N=int(keep.sum()),
        unique_selected_keys=len(set(keys)),stage55_reuse_N=int(reuse55.sum()),stage70_reuse_N=int(reuse70.sum()),internal_repeat_N=int(internal.sum()),
        within_source_repeat_N=int(np.sum(same)),cross_source_repeat_N=int(np.sum(cross)),new_sources=len(np.unique(d['source_index'][keep])),new_groups=len(np.unique(d['group'][keep])),
        original_exposed_N=len(old['incoming']),original_unique_keys=len(stage55),old_stage70_new_keys=28,
        new_lowE={k:int((keep&mm[k]).sum()) for k in ['E50_100','E100_200']},
        new_difficult={k:int((keep&mm[k]).sum()) for k in ['pz50_100_trueE200_inf','pz50_100_high_y','pz50_100_unconfirmed','high_y','unconfirmed','input_missing','E3200_6400','E6400_inf']},
        complete_sources=[0,1],unmeasured_sources=[2,3],K_selected_and_new='未测量',K_reason=p['unavailable_reason'],
        requested_uproot_bytes=sum(m['requested_uproot_bytes'] for m in metadata),analysis_ROOT_requested_bytes='未测量',physical_EOS_network_IO='未测量',
        remote_CPU_s=sum(h['RemoteUserCpu']+h['RemoteSysCpu'] for h in hist),remote_wall_sum_s=sum(h['RemoteWallClockTime'] for h in hist),
        energy_model_fits=0,F7_inference=0,new_RDO_HITS_or_generation=0,locked_test_read=False,
        calibration='existing reference01-LG; no rescaling',response_systematics_certified=False,
        independence='development only; full upstream parent/subfile/seed unproven',power='未测量',
        all62_policy_and_incoming_veto_verified=True,**resources(start))
    assert not (CACHE/'support.npz').exists()
    np.savez_compressed(CACHE/'support.npz',**d,metadata_json=np.array(json.dumps(dict(features=cfg['features'],reference='WAVE-Calibration-01-LG',protocol=p,summary=summary))))
    save(OUT/'summary.json',summary);print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
