"""Independent stage81 key ownership, support tables, NaNs, roles and budgets."""
import csv
import json
import numpy as np
from audited_features import REPO,configuration,load,SCINTILLATORS,WAVE_INVALID,FIT_INVALID
from support_augmentation import arrays,save,begin,resources

OUT=REPO/'workbook/stage81_energy_ml';CACHE=REPO/'ntuples/energy_ml_stage81'


def main():
    start=begin();d=arrays(CACHE/'support.npz');summary=json.loads((OUT/'summary.json').read_text());cfg=configuration()
    old,s,x=load();prev=arrays(REPO/'ntuples/energy_ml_stage70/support.npz');prev=prev['incoming'][prev['new_training_support']]
    # Independent row IDs and membership via numpy; no collector Python-key sets.
    known=np.vstack([old['incoming'],prev]);_,ix=np.unique(np.vstack([known,d['incoming']]),axis=0,return_inverse=True)
    n=len(known);knownmask=np.isin(ix[n:],ix[:n]);first=np.sort(np.unique(ix[n:],return_index=True)[1]);repeat=np.ones(len(d['run']),bool);repeat[first]=False
    expected=~knownmask&~repeat;np.testing.assert_array_equal(expected,d['new_training_support'])
    assert expected.sum()==742 and len(np.unique(d['incoming'][expected],axis=0))==742
    assert len(d['run'])==797 and np.all(d['reco_pz_GeV']>50) and np.all(d['incoming'][:,3]>50000)
    assert np.array_equal(d['source_index'],np.repeat([0,1],[415,382]))
    assert int(np.sum(knownmask&repeat))==1
    for i in [0,1]:
        a=arrays(CACHE/f'qa{i}.npz');m=(d['source_index']==i)&(d['input_entry']<10)
        for k in a:np.testing.assert_array_equal(d[k][m],a[k])
    for j,name in enumerate(cfg['features']):
        v=d['x'][:,j];r=cfg['rules'][name];f=v[np.isfinite(v)]
        assert not np.isin(f,r.get('sentinels',[])).any()
        if r['domain']=='positive':assert (f>0).all()
        if r['domain'] in ['nonnegative','count']:assert (f>=0).all()
    for j,name in enumerate(SCINTILLATORS):
        v=d['x'][:,cfg['features'].index(name+'_raw_charge')];st=d['status'][:,j].astype(int)
        keep=(st&WAVE_INVALID)==0
        np.testing.assert_array_equal(v[keep],d['raw_charge'][keep,j].astype('float32'))
        assert np.isnan(v[~keep]).all()
    calo=np.column_stack([d['x'][:,cfg['features'].index(f'ML_calo{i}_E_EM_GeV')] for i in range(4)])
    total=d['x'][:,cfg['features'].index('ML_calo_total_E_EM_GeV')]
    np.testing.assert_array_equal(np.isnan(total),np.isnan(calo).any(1))
    np.testing.assert_array_equal(total,calo.astype(float).sum(1).astype('float32'))
    role=np.full(len(s['row']),'unused',dtype='<U6');role[old['train_eligible'][s['row']]]='train';role[old['cal_eligible'][s['row']]]='cal';role[old['partition'][s['row']]=='validation']='eval'
    assert [int((role==r).sum()) for r in ['train','cal','eval']]==[41447,8440,14057]
    assert [int((np.isnan(x).any(1)&(role==r)).sum()) for r in ['train','cal','eval','unused']]==[21,3,7,11]
    p=json.loads((OUT/'source_plan.json').read_text())
    rng=np.random.default_rng(2026110377)
    for c in ['pi','k']:
        pool=sorted([a for a in p['candidates'] if a['component']==c],key=lambda a:a['input']);chosen=sorted(rng.choice(len(pool),size=2,replace=False).tolist())
        assert chosen==p['pools'][c]['selected_indices']
        assert all(not set(a['historical_roles'])&{'test','validation','calibration'} for a in pool)
    for i in [2,3]:
        qa=json.loads((OUT/f'qa{i}.json').read_text());assert not qa['compatible'] and qa['production']['ntuple_tracks']!='CKFTrackCollectionMergeWithoutIFT'
    rows=list(csv.DictReader((OUT/'support.tsv').open(),delimiter='\t'))
    for r in rows:
        if r['scope'] in ['k','source2','source3']:assert r['N']=='未测量' and r['measured']=='False'
    # Count the principal strata directly with numeric predicates, independent of masks().
    e=d['truth_E_GeV'];p0=d['reco_pz_GeV'];y=d['y_lepton']
    ms=dict(E50_100=(e>=50)&(e<100),E100_200=(e>=100)&(e<200),pz50_100_trueE200_inf=(p0>=50)&(p0<100)&(e>=200),
        pz50_100_high_y=(p0>=50)&(p0<100)&(y>=.8),pz50_100_unconfirmed=(p0>=50)&(p0<100)&~d['confirmed'],
        high_y=y>=.8,unconfirmed=~d['confirmed'],input_missing=np.isnan(d['x']).any(1),E3200_6400=(e>=3200)&(e<6400),E6400_inf=e>=6400)
    for key,m in ms.items():
        r=next(r for r in rows if r['scope']=='all' and r['state']=='new' and r['stratum']==key);assert int(r['N'])==int((m&expected).sum())
    h=json.loads((OUT/'history.json').read_text());assert len(h)==2 and all(a['ExitCode']==0 and a['NumJobStarts']==1 for a in h)
    qa=[json.loads((OUT/f'qa{i}.json').read_text()) for i in range(4)];pack=json.loads((OUT/'package_QA.json').read_text())
    measured_bytes=summary['requested_uproot_bytes']+sum(a['scalar_requested_bytes'] for a in qa)+sum(a.get('ROOT_clone_requested_bytes',0)+a.get('extraction',{}).get('requested_uproot_bytes',0) for a in qa)
    measured_bytes+=sum(a['ROOT_clone_requested_bytes']+a['Uproot_requested_bytes'] for a in pack['records'])
    measured_cpu=summary['remote_CPU_s']+sum(a['CPU_s']+a.get('measured_child_CPU_s',0) for a in qa)+pack['CPU_s']+sum(a['child_CPU_s'] for a in pack['records'])
    assert measured_cpu<7200 and measured_bytes<10000000000
    result=dict(passed=True,independent_key_veto_and_stable_ownership=True,known_repeat_overlap_N=1,new_unique_N=742,
        QA_same_identity_full_source_arrays_exact=True,all62_domains_raw_and_Calo_NaNs_exact=True,
        original_roles_and_42_missing_unchanged=True,source_draw_reproduced=True,K_incompatibility_explicit_no_yield_zero=True,
        principal_strata_independently_counted=len(ms),two_formal_jobs_once_exit0=True,energy_model_fits=0,
        measured_ROOT_Uproot_requests_including_repeat_QA_bytes=measured_bytes,
        measured_QA_plus_Condor_CPU_s=measured_cpu,analysis_ROOT_requested_bytes='未测量',physical_EOS_network_IO='未测量',
        input_limit_scope='logical formal PHYS 61,408,284 bytes; measured requests include QA repeats, C++ analysis requests unmeasured',
        **resources(start))
    save(OUT/'validation.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    labels=['E50–100','E100–200','low pz, E≥200','high-y','unconfirmed','E3200–6400']
    keys=['E50_100','E100_200','pz50_100_trueE200_inf','high_y','unconfirmed','E3200_6400']
    fig,axes=plt.subplots(1,2,figsize=(10,3.8))
    for ax,scope in zip(axes,['source0','source1']):
        nums=[int(next(r['N'] for r in rows if r['scope']==scope and r['state']=='new' and r['stratum']==k)) for k in keys]
        b=ax.bar(range(6),nums);ax.bar_label(b);ax.set_xticks(range(6),labels,rotation=40,ha='right');ax.set_ylabel('New unique incoming keys');ax.set_title(scope+' (pi)')
    fig.suptitle('Stage81: actual development support; overlapping strata; K unmeasured')
    fig.tight_layout();fig.savefig(OUT/'support.png',dpi=150);fig.savefig(OUT/'support.pdf');plt.close(fig)


if __name__=='__main__':main()
