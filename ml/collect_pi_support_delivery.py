"""Stage83 complete-source pi collection, native incoming veto and support census."""
import json
import re
import subprocess
import tarfile
from pathlib import Path

import numpy as np

from audited_features import REPO, SCINTILLATORS, WAVE_INVALID, configuration, load
from collect_alternative_support import masks
from pi_support_delivery import OUT, CACHE, SPOOL, check_features
from support_augmentation import arrays, save, table, begin, resources


def history():
    sub=json.loads((OUT/'submission.json').read_text())
    logfile=SPOOL/'logs'/f'extract.{sub["cluster"]}.log'
    h=json.loads(subprocess.check_output(['condor_history','-userlog',str(logfile),'-json'],text=True,timeout=30))
    assert len(h)==4 and all(r['JobStatus']==4 and r['ExitCode']==0 and r['NumJobStarts']==1 for r in h)
    for r in h:
        ad=next(a for a in sub['actual_ads'] if a['ProcId']==r['ProcId'])
        assert ad['RequestCpus']==1 and ad['RequestMemory']==3000 and 1100<=ad['MaxRuntime']<=1800
        r.update({k:ad[k] for k in ['RequestCpus','RequestMemory','MaxRuntime']})
        r['resource_provenance']='condor_history -userlog, phase execute wall; requests from recorded actual submit ads'
    assert sum(r['RemoteUserCpu']+r['RemoteSysCpu'] for r in h)<1800
    save(OUT/'history.json',h)
    (OUT/'condor_events.txt').write_text('\n'.join(s.rstrip() for s in logfile.read_text().splitlines())+'\n')
    return h


def existing():
    old,s,x=load()
    previous={}
    for stage,n in [(70,28),(81,742),(82,1016)]:
        a=arrays(REPO/f'ntuples/energy_ml_stage{stage}/support.npz')
        keep=a['new_training_support'];assert int(keep.sum())==n
        previous[stage]={k:a[k][keep] for k in ['x','incoming','truth_E_GeV','reco_pz_GeV','y_lepton','confirmed','group','component']}
    return old,s,x,previous


def main():
    start=begin();p=json.loads((OUT/'protocol.json').read_text());h=history()
    assert not (CACHE/'support.npz').exists()
    # Return only one copy of the five-source scalars and compact timings per job.
    for shard in range(4):
        with tarfile.open(CACHE/f'shard_{shard}.tar.gz') as t:
            assert t.extractfile('result/exitcode.txt').read().strip()==b'0'
            for member in t.getmembers():
                if member.isdir():continue
                assert member.isfile() and '..' not in member.name
                if member.name.startswith('ntuples/energy_ml_stage83/'):
                    dest=CACHE/Path(member.name).name
                elif member.name.startswith('result/'):
                    if member.name.endswith('exitcode.txt'):continue
                    if not member.name.endswith('.time'):continue # repeated stdout metadata isn't retained
                    dest=OUT/Path(member.name).name
                else:
                    raise ValueError(member.name)
                assert not dest.exists();dest.write_bytes(t.extractfile(member).read())
    parts=[];metadata=[];cutflows=[];calo=[];performance=[]
    for i,source in enumerate(p['sources']):
        d=arrays(CACHE/f'source{i}.npz');md=json.loads(str(d.pop('metadata_json')))
        assert md['source']==source and md['raw_N']==10000 and md['features']==p['features']
        assert md['feature_version']==p['feature_version'] and not md['qa']
        assert np.all(d['run']==source['run']) and len(np.unique(d['eventID']))==len(d['run'])
        assert md['selected_N']==len(d['run'])==md['cutflow_passed'][-1]
        assert np.all(np.diff(d['input_entry'])>0)
        check_features(d)
        qa=arrays(CACHE/f'qa{i}.npz');use=d['input_entry']<2
        for key,value in qa.items():np.testing.assert_array_equal(d[key][use],value)
        n=len(d['run']);d.update(source_index=np.full(n,i),group=np.full(n,source['group']),component=np.full(n,'pi'),
            source_probability=np.ones(n),conditional_event_probability=np.ones(n))
        parts.append(d);metadata.append(md)
        for name,count in zip(md['cutflow_names'],md['cutflow_passed']):
            cutflows.append(dict(source=i,group=source['group'],cut=name,passed=count))
        c=md['calibration_QA'];assert c['reference']=='WAVE-Calibration-01-LG' and not c['rescaled']
        for r in c['checks']:calo.append(dict(source=i,**r))
        text=(OUT/f'source{i}.time').read_text()
        measured={k:float(v) for k,v in re.findall(r'(wall_s|user_s|system_s|maxRSS_KiB)=([\d.]+)',text)}
        performance.append(dict(source=i,group=source['group'],selected_N=n,CPU_s=measured['user_s']+measured['system_s'],
            wall_s=measured['wall_s'],peak_RSS_MiB=measured['maxRSS_KiB']/1024,
            selected_events_per_wall_s=n/measured['wall_s'],raw_events_per_wall_s=10000/measured['wall_s'],
            Uproot_requested_bytes=md['requested_uproot_bytes']+c['requested_uproot_bytes']))
    assert all(sum(r['N'] for r in calo if r['module']==j)>0 for j in range(4))
    d={k:np.concatenate([a[k] for a in parts]) for k in parts[0]}
    old,s,x,previous=existing()
    known={55:set(map(tuple,old['incoming']))}
    for stage,a in previous.items():known[stage]=set(map(tuple,a['incoming']))
    reuse={stage:np.array([tuple(k) in keys for k in d['incoming']]) for stage,keys in known.items()}
    reused=np.logical_or.reduce(list(reuse.values()));seen={};same=[];cross=[];repeat=[]
    for key,src in zip(map(tuple,d['incoming']),d['source_index']):
        repeat.append(key in seen);same.append(key in seen and seen[key]==src);cross.append(key in seen and seen[key]!=src)
        seen.setdefault(key,int(src))
    repeat=np.array(repeat);keep=~(reused|repeat)
    d.update(new_training_support=keep,known_reuse=reused,internal_repeat=repeat,
        within_source_repeat=np.array(same),cross_source_repeat=np.array(cross),
        **{f'known_stage{stage}_reuse':value for stage,value in reuse.items()})
    assert len(set(map(tuple,d['incoming'][keep])))==int(keep.sum())
    assert not set(map(tuple,d['incoming'][keep]))&set.union(*known.values())
    summary=dict(raw_N=200000,selected_N=len(keep),new_unique_N=int(keep.sum()),unique_selected_keys=len(seen),
        known_reuse_N=int(reused.sum()),known_by_stage={str(stage):int(a.sum()) for stage,a in reuse.items()},
        internal_repeat_N=int(repeat.sum()),known_repeat_overlap_N=int((reused&repeat).sum()),
        within_source_repeat_N=int(np.sum(same)),cross_source_repeat_N=int(np.sum(cross)),
        complete_sources=20,new_sources=len(np.unique(d['source_index'][keep])),
        original_exposed_N=len(old['incoming']),original_unique_keys=len(known[55]),previous_new_unique_N=1786,
        logical_PHYS_bytes=611988745,formal_requested_Uproot_bytes=sum(a['Uproot_requested_bytes'] for a in performance),
        analysis_ROOT_requested_bytes='未测量',physical_EOS_network_IO='未测量',
        remote_CPU_s=sum(a['RemoteUserCpu']+a['RemoteSysCpu'] for a in h),remote_wall_sum_s=sum(a['RemoteWallClockTime'] for a in h),
        subprocess_CPU_sum_s=sum(a['CPU_s'] for a in performance),subprocess_wall_sum_s=sum(a['wall_s'] for a in performance),
        subprocess_peak_RSS_MiB=max(a['peak_RSS_MiB'] for a in performance),
        feature_version=p['feature_version'],reference='native01-LG no rescaling',energy_model_fits=0,F7_inference=0,ROOT_reconstruction=0,
        locked_test_read=False,independence='development only; full parent/subfile/seed and untouched confirmation unproven',
        source_probability='1 conditional on remaining20known compatible train sources, not physical flux weighting',**resources(start))
    mm=masks(d);support=[];identities=[];validity=[];rawvalid=[]
    scopes=[(f'source{i}',d['source_index']==i) for i in range(20)]+[('all',np.ones(len(keep),bool))]
    for label,take in scopes:
        for state,select in [('selected',np.ones(len(keep),bool)),('known',reused),('internal',repeat),('new',keep)]:
            for key,m in mm.items():
                use=take&select&m
                support.append(dict(scope=label,state=state,stratum=key,N=int(use.sum()),sources=len(np.unique(d['source_index'][use])),
                    unique_incoming=len(set(map(tuple,d['incoming'][use])))))
        identities.append(dict(scope=label,selected_N=int(take.sum()),known_reuse_N=int((take&reused).sum()),
            **{f'stage{stage}_reuse_N':int((take&mask).sum()) for stage,mask in reuse.items()},
            within_source_repeat_N=int((take&d['within_source_repeat']).sum()),cross_source_repeat_N=int((take&d['cross_source_repeat']).sum()),
            known_repeat_overlap_N=int((take&reused&repeat).sum()),new_N=int((take&keep).sum())))
    # Aggregate variable audit; source-level missing support is in the census.
    for state,select in [('selected',np.ones(len(keep),bool)),('new',keep)]:
        for j,name in enumerate(p['features']):
            v=d['x'][select,j];finite=v[np.isfinite(v)]
            validity.append(dict(state=state,feature=name,N=len(v),missing_N=int(np.isnan(v).sum()),negative_N=int((v<0).sum()),
                minus1_N=int((v==-1).sum()),minus999_N=int((v==-999).sum()),minimum=float(finite.min()) if len(finite) else '未测量',
                maximum=float(finite.max()) if len(finite) else '未测量'))
        for j,det in enumerate(SCINTILLATORS):
            st=d['status'][select,j].astype(int);raw=d['raw_charge'][select,j]
            rawvalid.append(dict(state=state,detector=det,N=len(raw),negative_raw_N=int((raw<0).sum()),wave_invalid_N=int(((st&WAVE_INVALID)!=0).sum()),
                fit_failure_raw_valid_N=int((((st&48)!=0)&((st&WAVE_INVALID)==0)&np.isfinite(raw)).sum())))
    # Describe support increments against the identical old training cohort.
    rows=s['row'];tr=old['train_eligible'][rows]
    context_old=dict(x=x[tr],**{k:old[k][rows[tr]] for k in ['truth_E_GeV','reco_pz_GeV','y_lepton','confirmed']})
    fields=['x','incoming','truth_E_GeV','reco_pz_GeV','y_lepton','confirmed','group','component']
    pooled={k:np.concatenate([a[k] for a in previous.values()]+[d[k][keep]]) for k in fields}
    assert len(np.unique(pooled['incoming'],axis=0))==len(pooled['incoming'])
    cm,pm=masks(context_old),masks(pooled);context=[]
    for key,m in cm.items():
        baseline=int(m.sum());current=int((keep&mm[key]).sum());total=int(pm[key].sum())
        context.append(dict(stratum=key,old_train_N=baseline,new_stage83_N=current,previous_new_N=total-current,pooled_new_N=total,
            stage83_increment_pct=100*current/baseline if baseline else '未测量',pooled_increment_pct=100*total/baseline if baseline else '未测量'))
    summary.update(new_lowE={k:int((keep&mm[k]).sum()) for k in ['E50_100','E100_200']},
        new_difficult={k:int((keep&mm[k]).sum()) for k in ['pz50_100','pz50_100_trueE200_inf','pz50_100_high_y','pz50_100_unconfirmed','high_y','unconfirmed','input_missing','E3200_6400','E6400_inf']},
        pooled_new_N=len(pooled['incoming']),pooled_groups=len(np.unique(pooled['group'])),new_negative_raw_N=int((d['raw_charge'][keep]<0).sum()))
    np.savez_compressed(CACHE/'support.npz',**d,metadata_json=np.array(json.dumps(dict(features=p['features'],reference='WAVE-Calibration-01-LG',calibration_policy=p['reference'],source_plan='workbook/stage83_energy_ml/source_plan.json'))))
    save(OUT/'extractions.json',metadata)
    for name,rr in [('support',support),('identities',identities),('cutflow',cutflows),('feature_validity',validity),('raw_validity',rawvalid),('training_context',context),('calo_formula',calo),('source_resources',performance)]:
        table(OUT/(name+'.tsv'),rr)
    save(OUT/'summary.json',summary);print(json.dumps(summary,indent=2,ensure_ascii=False))


if __name__=='__main__':main()
