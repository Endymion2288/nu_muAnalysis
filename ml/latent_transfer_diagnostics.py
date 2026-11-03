"""Stage86: cached truth/response audit; no training, ROOT reads or inference."""
import argparse
import json
import resource
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from audited_features import REPO, WAVE_INVALID, FIT_INVALID, build, configuration
from support_augmentation import arrays, save, table, begin, resources, boot_weights

OUT = REPO/'workbook/stage86_energy_ml'
CACHE = REPO/'ntuples/energy_ml_stage86'
SPOOL = Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage86')
INPUTS = ['ntuples/energy_ml_stage55/dataset.npz', 'ntuples/energy_ml_stage56/readout.npz']
INPUTS += [f'ntuples/energy_ml_stage{s}/support.npz' for s in [70,81,82,83]]
INPUTS += ['ml/artifacts/stage84/comparison.npz', 'ml/artifacts/stage56/predictions.npz',
           'workbook/stage84_energy_ml/fit.json', 'workbook/stage81_energy_ml/source_plan.json',
           'workbook/stage34_energy_ml/test_summary.json', 'workbook/stage34_energy_ml/challenge_summary.json',
           'workbook/stage35_energy_ml/test_summary.json']
METRICS = ['log_RMSE', 'median_bias_pct', 'positive_tail50_pct', 'negative_tail50_pct', 'tail50_pct']


def roles(old, rows):
    role = np.full(len(rows), 'unused', dtype='<U6')
    role[old['train_eligible'][rows]] = 'train'
    role[old['cal_eligible'][rows]] = 'cal'
    role[old['partition'][rows]=='validation'] = 'eval'
    return role


def labels(a):
    e, f, p = a['truth_E_GeV'], a['y_lepton'], a['primary_p_GeV']
    mu = (1-f)*e
    valid = a['primary_valid'] & (a['primary_candidates']==1) & np.isfinite(mu) & (mu>0)
    physical = valid & np.isfinite(e) & (e>0) & np.isfinite(f) & (f>=0) & (f<1)
    # Retain undefined and out-of-domain labels; never clip to a physical target.
    h = e-mu
    shell = np.sqrt(p*p + .1056583755**2)
    return dict(mu_truth_GeV=mu, transfer_GeV=h, fraction=f, label_valid=valid,
                label_physical=physical, mass_shell_delta_GeV=mu-shell)


def check_x(x):
    cfg=configuration(); names=cfg['features']
    assert x.shape[1]==62 and not np.isinf(x).any()
    assert not set(names)&{'ML_mu_p_GeV','ML_track_p1_GeV','ML_track_pz1_GeV','ML_track_log_p1_over_p0'}
    cleaned = np.column_stack([__import__('audited_features').clean(x[:,j],cfg['rules'][n]) for j,n in enumerate(names)]).astype('float32')
    np.testing.assert_array_equal(x,cleaned)
    idx=[names.index(f'ML_calo{j}_E_EM_GeV') for j in range(4)]
    np.testing.assert_array_equal(np.isnan(x[:,idx]).any(1),np.isnan(x[:,names.index('ML_calo_total_E_EM_GeV')]))


def qa():
    start=begin(); OUT.mkdir(parents=True,exist_ok=True)
    old=arrays(REPO/INPUTS[0]); s=arrays(REPO/INPUTS[1]); role=roles(old,s['row'])
    positions=np.concatenate([np.flatnonzero(role==r)[:10] for r in ['train','cal','eval']])
    small={k:v[positions] for k,v in s.items() if k!='metadata_json'}
    x=build(old,small); check_x(x); ids=[]
    comp=arrays(REPO/INPUTS[6]); base=arrays(REPO/INPUTS[7])
    offset=json.loads(str(base['metadata_json']))['offset_log']
    for r in ['cal','eval']:
        np.testing.assert_array_equal(comp[r+'_row'][:10],small['row'][role[positions]==r])
        np.testing.assert_array_equal(comp[r+'_F7'][:10],base[r+'_raw_log'][:,:10].mean(0)+offset)
        for k in ['truth_E_GeV','incoming','group','confirmed']:
            np.testing.assert_array_equal(comp[r+'_'+k][:10],old[k][comp[r+'_row'][:10]])
    for row in small['row']:
        ids.append(dict(origin='stage55',row=int(row),run=int(old['run'][row]),eventID=int(old['eventID'][row])))
    selected={k:old[k][small['row']] for k in ['truth_E_GeV','y_lepton','primary_valid','primary_candidates','primary_p_GeV']}
    lab=labels(selected); assert np.isfinite(lab['mu_truth_GeV'][lab['label_valid']]).all()
    for stage,n in [(70,2),(81,2),(82,3),(83,3)]:
        a=arrays(REPO/f'ntuples/energy_ml_stage{stage}/support.npz')
        take=np.flatnonzero(a['new_training_support'])[:n]; check_x(a['x'][take])
        for j in take: ids.append(dict(origin=f'stage{stage}',row=int(j),run=int(a['run'][j]),eventID=int(a['eventID'][j])))
        assert json.loads(str(a['metadata_json']))['features']==configuration()['features']
    assert len(ids)==40
    result=dict(passed=True,distinct_identities=40,identities=ids,features=62,zero_fits=True,zero_ROOT=True,zero_inference=True,
                original_role_counts={r:int((role==r).sum()) for r in ['train','cal','eval','unused']},
                input_logical_bytes=sum((REPO/p).stat().st_size for p in INPUTS),physical_IO_bytes='未测量',**resources(start))
    save(OUT/'identity_QA.json',result); print('40 cached identities and old prediction joins passed; zero fits',flush=True)


def response(x, raw, status, calo):
    return dict(input_missing=np.isnan(x).any(1),wave_invalid=((status&WAVE_INVALID)!=0).any(1),
                fit_failure=((status&(16|32))!=0).any(1),
                negative_valid_raw=((raw<0)&((status&WAVE_INVALID)==0)).any(1),
                calo_invalid=((calo&FIT_INVALID)!=0).any(1))


def assemble():
    old=arrays(REPO/INPUTS[0]); s=arrays(REPO/INPUTS[1]); x=build(old,s); check_x(x)
    rows=s['row']; role=roles(old,rows); comp=arrays(REPO/INPUTS[6]); base=arrays(REPO/INPUTS[7])
    bm=json.loads(str(base['metadata_json'])); off=json.loads((REPO/INPUTS[8]).read_text())['offset_log']
    keys=['truth_E_GeV','y_lepton','primary_valid','primary_candidates','primary_p_GeV','confirmed','incoming','group','component','run','eventID']
    datasets={}
    for r in ['train','cal','eval']:
        use=role==r; idx=rows[use]
        a={k:old[k][idx] for k in keys}; a.update(row=idx,pz=old['reco_pz_GeV'][idx],source=np.array(['stage55:'+str(i) for i in old['source'][idx]]))
        a.update(response(x[use],s['raw_charge'][use],s['status'][use],s['calo_status'][use]))
        if r!='train':
            np.testing.assert_array_equal(idx,comp[r+'_row']); np.testing.assert_array_equal(idx,base[r+'_row'])
            for k in ['truth_E_GeV','y_lepton','incoming','group','component','confirmed']:
                np.testing.assert_array_equal(a[k],comp[r+'_'+k])
            np.testing.assert_array_equal(a['input_missing'],comp[r+'_missing'])
            np.testing.assert_array_equal(comp[r+'_F7'],base[r+'_raw_log'].mean(0)+bm['offset_log'])
            a.update(F7=comp[r+'_F7'],stage84=comp[r+'_raw_log'].mean(0)+off)
        datasets[r]=a
    new=[]; newkeys=[]; missingnew=[]
    for stage in [70,81,82,83]:
        z=arrays(REPO/f'ntuples/energy_ml_stage{stage}/support.npz'); check_x(z['x']); m=z['new_training_support']
        a={k:z[k][m] for k in keys}; a.update(row=np.flatnonzero(m),pz=z['reco_pz_GeV'][m],
           source=np.array([f'stage{stage}:'+str(i) for i in z['source_index'][m]]))
        a.update(response(z['x'][m],z['raw_charge'][m],z['status'][m],z['calo_status'][m])); new.append(a)
        newkeys.extend(map(tuple,a['incoming'])); missingnew.append(dict(stage=stage,N=int(m.sum()),missing=int(a['input_missing'].sum())))
    assert len(newkeys)==len(set(newkeys))==7720
    assert not set(newkeys)&set(map(tuple,old['incoming']))
    pool={k:np.concatenate([a[k] for a in new]) for k in new[0]}
    assert len(np.unique(pool['group']))==26 and (pool['component']=='k').sum()==1016
    datasets['new_support']=pool
    datasets['pooled_train']={k:np.concatenate([datasets['train'][k],pool[k]]) for k in pool}
    for a,b in [('train','cal'),('train','eval'),('cal','eval')]:
        assert not set(datasets[a]['group'])&set(datasets[b]['group'])
        assert not set(map(tuple,datasets[a]['incoming']))&set(map(tuple,datasets[b]['incoming']))
    assert set(pool['group'])<=set(datasets['train']['group'])
    lineage=[]
    for r,a in datasets.items():
        assert (a['pz']>50).all()
        a.update(labels(a)); a['traditional']=np.log(a['pz']/.8)
        lineage.append(dict(role=r,N=len(a['pz']),canonical_groups=len(np.unique(a['group'])),source_records=len(np.unique(a['source'])),
           unique_incoming=len(np.unique(a['incoming'],axis=0)),input_missing=int(a['input_missing'].sum())))
    table(OUT/'lineage.tsv',lineage)
    save(OUT/'joins.json',dict(original_roles={r:int((role==r).sum()) for r in ['train','cal','eval','unused']},
         original_missing={r:int((np.isnan(x).any(1)&(role==r)).sum()) for r in ['train','cal','eval','unused']},
         new=missingnew,new_unique_keys=7720,disjoint_all_original_exposed_rows=len(old['incoming']),
         canonical_train_cal_eval_disjoint=True,exact_incoming_disjoint=True,
         full_upstream_independence='未认证: parent/subfile/entry/generation seed complete mapping absent',
         unused_payload_evaluated=False,historical_test_payload_evaluated=False,existing_predictions_exact=True))
    return datasets


def strata(a):
    e,p,f=a['truth_E_GeV'],a['pz'],a['fraction']; physical=a['label_physical']
    es={'E50_100':(e>=50)&(e<100),'E100_200':(e>=100)&(e<200),'E200_inf':e>=200}
    ts={'f0_01':physical&(f<.1),'f01_05':physical&(f>=.1)&(f<.5),
        'f05_08':physical&(f>=.5)&(f<.8),'f08_1':physical&(f>=.8),'label_unknown':~physical}
    rs={k:a[k] for k in ['input_missing','wave_invalid','fit_failure','negative_valid_raw','calo_invalid']}
    rs['response_nominal']=~(a['wave_invalid']|a['fit_failure']|a['calo_invalid']|a['input_missing'])
    low=(p>=50)&(p<100)
    out=dict(all=np.ones(len(e),bool),**es,**ts,**rs,pz50_100=low,pz100_inf=p>=100,
             high_y=physical&(f>=.8),unconfirmed=~a['confirmed'],
             confirmed_low_transfer=a['confirmed']&physical&(f<.2),E3200_6400=(e>=3200)&(e<6400),E6400_inf=e>=6400)
    for name,m in es.items():
        for t,v in dict(ts,confirmed_low_transfer=out['confirmed_low_transfer'],unconfirmed=out['unconfirmed'],**rs).items():
            out[name+'__'+t]=m&v
        out['pz50_100__'+name]=low&m
        for t,v in ts.items():out['pz50_100__'+name+'__'+t]=low&m&v
    for t,v in dict(ts,unconfirmed=out['unconfirmed'],**rs).items():out['pz50_100__'+t]=low&v
    return out


def summary_values(error, weights=None):
    rel=np.expm1(error)
    if weights is None:
        return np.array([np.sqrt(np.mean(error**2)),np.median(rel)*100,(rel>.5).mean()*100,(rel<-.5).mean()*100,(abs(rel)>.5).mean()*100])
    total=weights.sum(1); good=total>0; result=np.full((len(total),5),np.nan)
    result[good,0]=np.sqrt((weights[good]@(error**2))/total[good])
    result[good,2:]=((weights[good]@np.column_stack([rel>.5,rel<-.5,abs(rel)>.5]))/total[good,None])*100
    order=np.argsort(rel,kind='stable'); cw=np.cumsum(weights[good][:,order],axis=1)
    # Exact median of the event multiset from integer source multiplicities.
    lo=(total[good]-1)//2+1; hi=total[good]//2+1
    il=(cw>=lo[:,None]).argmax(1); ih=(cw>=hi[:,None]).argmax(1)
    result[good,1]=50*(rel[order][il]+rel[order][ih])
    return result


def exposure():
    plan=json.loads((REPO/'workbook/stage81_energy_ml/source_plan.json').read_text())['roles_by_canonical_group']
    rr=[]
    for g,roleset in sorted(plan.items()):
        rr.append(dict(group=g,historical_roles=','.join(roleset),certified_unexposed=False,
                       status='used_development_or_stage34_35_exposed; upstream lineage not certified'))
    table(OUT/'source_exposure.tsv',rr)
    hist={}
    for stage,part in [(34,'test'),(34,'challenge'),(35,'test')]:
        v=json.loads((REPO/f'workbook/stage{stage}_energy_ml/{part}_summary.json').read_text())
        hist[f'stage{stage}_{part}']={k:v[k] for k in ['events','groups','created_utc']}
    save(OUT/'holdout_audit.json',dict(metadata_groups=len(plan),role_memberships={r:sum(r in v for v in plan.values()) for r in ['train','validation','calibration','test','challenge']},
        certified_unused_locked_groups=0,claim_scope='only supplied metadata/cache registry; not all EOS or future productions',
        historical_exposure=hist,exposure_evidence='roadmap section16 and lines35/410; stage34/35 actual summaries',
        new_independent_parent_seed_mapping_available=False,holdout_payload_read=False,
        training_execution_blocked=True,minimal_input='externally reserved previously unstudied production/source, full GENIE parent/subfile/entry/seed lineage and exposure ledger, canonical group/incoming-disjoint split; compatible audited62/raw/status/01-LG PHYS or selected scalar cache'))


def diagnose():
    start=begin(); assert not (OUT/'diagnostics.npz').exists(); OUT.mkdir(parents=True,exist_ok=True)
    p=json.loads((OUT/'protocol.json').read_text()); assert p['energy_fits']==p['new_ROOT_reads']==p['new_inference']==0
    data=assemble(); exposure(); counts=[]; risks=[]; audits=[]; retained={}; draws={}
    for role,a in data.items():
        lab=a['label_physical']; delta=a['mass_shell_delta_GeV']; valid=a['label_valid']
        audits.append(dict(role=role,N=len(lab),unique_vertex_candidate=int(a['primary_valid'].sum()),
            candidate0=int((a['primary_candidates']==0).sum()),candidate_multiple=int((a['primary_candidates']>1).sum()),
            truth_mu_valid=int(valid.sum()),physical_transfer=int(lab.sum()),unknown_or_nonphysical=int((~lab).sum()),
            negative_transfer=int((valid&(a['transfer_GeV']<0)).sum()),fraction_ge1=int((valid&(a['fraction']>=1)).sum()),
            confirmed=int(a['confirmed'].sum()),unconfirmed_valid_label=int((~a['confirmed']&lab).sum()),
            min_transfer_GeV=float(np.nanmin(a['transfer_GeV'])) if valid.any() else '未测量',
            exact_zero_transfer=int((lab&(a['transfer_GeV']==0)).sum()),
            max_abs_mass_shell_delta_GeV=float(np.nanmax(abs(delta[valid]))) if valid.any() else '未测量'))
        gs,gid,w=boot_weights(a,2026110386,500); draws[role+'_groups']=gs; draws[role+'_weights']=w
        for k,v in a.items():retained[role+'_'+k]=v
        for name,m in strata(a).items():
            n=int(m.sum()); ng=len(np.unique(a['group'][m])); ns=len(np.unique(a['source'][m])); nv=int((m&lab).sum())
            counts.append(dict(role=role,stratum=name,N=n,groups=ng,source_records=ns,valid_transfer_N=nv,
                 confirmed_N=int((m&a['confirmed']).sum()),missing_N=int((m&a['input_missing']).sum()),
                 support='empty' if n==0 else 'sparse' if n<30 or ng<5 else 'supported',
                 transfer_median_GeV=float(np.median(a['transfer_GeV'][m&lab])) if nv else '未测量',
                 fraction_median=float(np.median(a['fraction'][m&lab])) if nv else '未测量'))
            # Training predictions not retained: do not create them or fabricate OOF.
            policies=['traditional'] if role in ['train','new_support','pooled_train'] else ['traditional','F7','stage84']
            if not n:
                for policy in policies:
                    risks.append(dict(role=role,stratum=name,policy=policy,N=0,groups=0,metric='all',value='未测量',lo95='未测量',hi95='未测量',valid_draws=0))
                continue
            ew=w[:,gid[m]]
            for policy in policies:
                err=a[policy][m]-np.log(a['truth_E_GeV'][m]); value=summary_values(err); b=summary_values(err,ew)
                for j,key in enumerate(METRICS):
                    bval=b[:,j]; bval=bval[np.isfinite(bval)]; ci=np.quantile(bval,[.025,.975]) if len(bval) else ['未测量']*2
                    risks.append(dict(role=role,stratum=name,policy=policy,N=n,groups=ng,metric=key,value=float(value[j]),lo95=float(ci[0]) if len(bval) else ci[0],hi95=float(ci[1]) if len(bval) else ci[1],valid_draws=len(bval)))
        print(f'{role}: {len(a["pz"])} cached identities diagnosed',flush=True)
    table(OUT/'state_counts.tsv',counts); table(OUT/'risk_intervals.tsv',risks); table(OUT/'truth_audit.tsv',audits)
    np.savez_compressed(OUT/'diagnostics.npz',**retained); np.savez_compressed(OUT/'bootstrap.npz',**draws)
    from validate_latent_transfer import validate
    validate()
    plot()
    save(OUT/'resources.json',dict(energy_fits=0,new_ROOT_reads=0,new_inference=0,new_generation=0,
         unique_logical_input_file_bytes=sum((REPO/s).stat().st_size for s in INPUTS),primary_analysis_input_passes=1,
         independent_validation_additional_original_NPZ_bytes=(REPO/INPUTS[0]).stat().st_size,
         physical_EOS_network_IO_bytes='未测量',cache_event_rows=49167+8440+14057,
         bootstrap_draws_per_role=500,OS_input_blocks=resource.getrusage(resource.RUSAGE_SELF).ru_inblock,**resources(start)))


def plot():
    import csv
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rr=list(csv.DictReader((OUT/'risk_intervals.tsv').open(),delimiter='\t'))
    cc=list(csv.DictReader((OUT/'state_counts.tsv').open(),delimiter='\t'))
    layers=['pz50_100__E50_100','pz50_100__E100_200','pz50_100__E200_inf']
    fig,ax=plt.subplots(1,2,figsize=(10,3.7),layout='constrained')
    names=['true E 50–100','true E 100–200','true E ≥200']
    for j,policy in enumerate(['traditional','F7','stage84']):
        a=[next(v for v in rr if v['role']=='eval' and v['stratum']==s and v['policy']==policy and v['metric']=='log_RMSE') for s in layers]
        y=np.array([float(v['value']) for v in a]); lo=np.array([float(v['lo95']) for v in a]); hi=np.array([float(v['hi95']) for v in a]); xx=np.arange(3)+(j-1)*.16
        ax[0].errorbar(xx,y,yerr=np.array([y-lo,hi-y]),fmt='o',capsize=3,label=policy)
    ax[0].set(xticks=np.arange(3),xticklabels=names,ylabel='log-RMSE',title='Developed eval; reconstructed pz 50–100 GeV'); ax[0].legend()
    ts=['f0_01','f01_05','f05_08','f08_1','label_unknown']
    for j,role in enumerate(['pooled_train','cal','eval']):
        nn=[int(next(v for v in cc if v['role']==role and v['stratum']==s)['N']) for s in ts]
        ax[1].bar(np.arange(5)+(j-1)*.25,np.array(nn)/sum(nn),width=.25,label=role)
    ax[1].set(xticks=np.arange(5),xticklabels=['<0.1','0.1–0.5','0.5–0.8','≥0.8','unknown'],ylabel='Event fraction',xlabel='Truth transfer fraction',title='Truth-state support; unknowns retained'); ax[1].legend()
    path=OUT/'latent_states.svg'; fig.savefig(path); plt.close(fig)
    path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')


def submit():
    start=begin(); assert not (OUT/'submission.json').exists()
    qa()
    paths=['ml/latent_transfer_diagnostics.py','ml/validate_latent_transfer.py','ml/audited_features.py','ml/support_augmentation.py','ml/configs/audited_features.json',
           'workbook/stage86_energy_ml/protocol.json','workbook/stage86_energy_ml/posterior_contract.json']+INPUTS
    archive=REPO/'software/energy-ml-latent-stage86.tar.gz'
    with tarfile.open(archive,'w:gz',compresslevel=1) as t:
        for path in paths:t.add(REPO/path,arcname=path)
    with tempfile.TemporaryDirectory(prefix='latent86_package_') as td:
        with tarfile.open(archive) as t:t.extractall(td,filter='data')
        result=subprocess.check_output([sys.executable,'ml/latent_transfer_diagnostics.py','qa'],cwd=td,text=True)
    save(OUT/'package_QA.json',dict(passed=True,actual_payload=result,distinct_identities=40,repeated_same_identity_QA=True,
         archive_bytes=archive.stat().st_size,energy_fits=0,**resources(start)))
    (SPOOL/'logs').mkdir(parents=True,exist_ok=True)
    worker=SPOOL/'worker_v1.sh'; assert not worker.exists()
    worker.write_bytes((REPO/'AnalysisZipFramework/submission/run_ml_latent_transfer.sh').read_bytes())
    sub=REPO/'AnalysisZipFramework/submission/ml_latent_transfer.sub'
    dry=subprocess.check_output(['condor_submit','-dry-run',str(SPOOL/'dryrun.ads'),str(sub)],text=True)
    result=subprocess.check_output(['condor_submit','-terse',str(sub)],text=True); cluster=int(result.split('.')[0])
    actual=json.loads(subprocess.check_output(['condor_q',str(cluster),'-json','-attributes','ClusterId,ProcId,RequestCpus,RequestMemory,MaxRuntime'],text=True))
    save(OUT/'submission.json',dict(cluster=cluster,result=result,dryrun=dry,actual_ads=actual,paths=paths))
    assert len(actual)==1 and all(a['RequestCpus']==1 and a['RequestMemory']==3000 and 1100<=a['MaxRuntime']<=1800 for a in actual)
    print(result,flush=True)


def collect():
    sub=json.loads((OUT/'submission.json').read_text()); log=SPOOL/'logs'/f'diagnostics.{sub["cluster"]}.log'
    history=json.loads(subprocess.check_output(['condor_history','-userlog',str(log),'-json'],text=True,timeout=30))
    assert len(history)==1 and history[0]['JobStatus']==4 and history[0]['ExitCode']==0 and history[0]['NumJobStarts']==1
    assert history[0]['RemoteUserCpu']+history[0]['RemoteSysCpu']<=1800
    save(OUT/'history.json',history)
    (OUT/'condor_events.txt').write_text('\n'.join(line.rstrip() for line in log.read_text().splitlines())+'\n')
    with tarfile.open(CACHE/'result.tar.gz') as t:
        for m in t.getmembers():
            if m.isdir():continue
            assert m.isfile() and m.name.startswith('workbook/stage86_energy_ml/') and '..' not in m.name
            path=REPO/m.name; value=t.extractfile(m).read()
            if path.exists():assert path.read_bytes()==value
            else:path.write_bytes(value)
    print('one diagnostics job, once exit0, collected',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['qa','diagnose','submit','collect'])
    globals()[p.parse_args().action]()
