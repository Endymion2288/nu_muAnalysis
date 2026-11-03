"""Independent stage83 numpy key ownership, support census and feature audit."""
import csv
import json

import numpy as np

from audited_features import REPO, configuration, load, clean, SCINTILLATORS, WAVE_INVALID, FIT_INVALID
from support_augmentation import arrays, save, begin, resources

OUT = REPO/'workbook/stage83_energy_ml'
CACHE = REPO/'ntuples/energy_ml_stage83'


def read(name):
    return list(csv.DictReader((OUT/(name+'.tsv')).open(), delimiter='\t'))


def strata(d):
    """Direct numeric predicates, independent of the collector's masks()."""
    e, p, y = d['truth_E_GeV'], d['reco_pz_GeV'], d['y_lepton']
    lowp = (p >= 50) & (p < 100)
    valid = d['confirmed'] & np.isfinite(y) & (y >= 0) & (y <= 1)
    m = dict(all=np.ones(len(e), bool), E50_100=(e >= 50) & (e < 100),
             E100_200=(e >= 100) & (e < 200), E200_inf=e >= 200,
             pz50_100=lowp, high_y=y >= .8, unconfirmed=~d['confirmed'],
             input_missing=np.isnan(d['x']).any(1),
             pz50_100_trueE200_inf=lowp & (e >= 200),
             pz50_100_high_y=lowp & (y >= .8),
             pz50_100_unconfirmed=lowp & ~d['confirmed'])
    for key in ['E50_100', 'E100_200']:
        m[key+'_confirmed_low_transfer'] = m[key] & valid & (y < .2)
    for lo, hi in zip([50,75,100,150,200,400,800,1600,3200], [75,100,150,200,400,800,1600,3200,6400]):
        m[f'E{lo}_{hi}'] = (e >= lo) & (e < hi)
    m['E6400_inf'] = e >= 6400
    return m


def main():
    start = begin()
    d = arrays(CACHE/'support.npz'); md = json.loads(str(d.pop('metadata_json')))
    cfg = configuration(); names = cfg['features']
    summary = json.loads((OUT/'summary.json').read_text())
    p = json.loads((OUT/'source_plan.json').read_text())
    request = json.loads((REPO/'workbook/stage82_energy_ml/followup_input_request.json').read_text())
    prior_plan = json.loads((REPO/'workbook/stage81_energy_ml/source_plan.json').read_text())
    assert len(p['sources']) == 20 and p['shards'] == [list(range(i*5, (i+1)*5)) for i in range(4)]
    for a, b in zip(p['sources'], request['sources']):
        assert all(a[k] == v for k, v in b.items())
        assert set(a['historical_roles']) == set(prior_plan['roles_by_canonical_group'][a['group']])
        assert 'train' in a['historical_roles'] and not set(a['historical_roles']) & {'test','validation','calibration'}
        assert a['source_probability'] == a['conditional_event_probability'] == 1
    old, supplement, x = load()
    previous = []
    known = {55: old['incoming']}
    for stage, n in [(70,28), (81,742), (82,1016)]:
        a = arrays(REPO/f'ntuples/energy_ml_stage{stage}/support.npz')
        take = a['new_training_support']; assert take.sum() == n
        known[stage] = a['incoming'][take]
        previous.append({k: a[k][take] for k in ['x','incoming','truth_E_GeV','reco_pz_GeV','y_lepton','confirmed','group','component']})
    # Numpy inverse row IDs independently replace Python tuple-set membership.
    n = len(d['run']); reuse = np.zeros(n, bool)
    for stage, keys in known.items():
        _, inv = np.unique(np.vstack([keys, d['incoming']]), axis=0, return_inverse=True)
        expected = np.isin(inv[len(keys):], inv[:len(keys)])
        np.testing.assert_array_equal(expected, d[f'known_stage{stage}_reuse'])
        assert expected.sum() == summary['known_by_stage'][str(stage)]
        reuse |= expected
    unique, first, inv = np.unique(d['incoming'], axis=0, return_index=True, return_inverse=True)
    repeat = np.arange(n) != first[inv]
    same = repeat & (d['source_index'] == d['source_index'][first[inv]])
    cross = repeat & ~same
    keep = ~reuse & ~repeat
    for key, expected in [('known_reuse',reuse), ('internal_repeat',repeat), ('within_source_repeat',same), ('cross_source_repeat',cross), ('new_training_support',keep)]:
        np.testing.assert_array_equal(d[key], expected)
    assert len(unique) == summary['unique_selected_keys']
    assert keep.sum() == summary['new_unique_N'] and n == summary['selected_N']
    assert (reuse & repeat).sum() == summary['known_repeat_overlap_N']
    assert n - reuse.sum() - repeat.sum() + (reuse & repeat).sum() == keep.sum()
    assert np.all(d['incoming'][:,3] > 50000) and np.all(d['reco_pz_GeV'] > 50)
    np.testing.assert_allclose(d['truth_E_GeV'], np.linalg.norm(d['incoming'][:,1:],axis=1)/1000, rtol=1e-10)
    assert np.isfinite(d['incoming']).all() and np.all(~d['confirmed'] | (d['primary_valid'] & (d['primary_candidates'] == 1)))
    assert d['x'].shape == (n,62) and md['features'] == names and md['reference'] == 'WAVE-Calibration-01-LG'
    assert names[0] == 'ML_mu_pz0_GeV' and cfg['version'] == 'F7_pz0_raw_v1'
    assert not any(k in names for k in ['ML_mu_p_GeV','ML_track_p1_GeV','ML_track_pz1_GeV','ML_track_log_p1_over_p0','LeadTrack_p0','LeadTrack_p1','LeadTrack_pz1'])
    np.testing.assert_array_equal(d['x'][:,0], d['reco_pz_GeV'].astype('float32'))
    assert not np.isinf(d['x']).any()
    for j, name in enumerate(names):
        r = cfg['rules'][name]; v = d['x'][:,j]; f = v[np.isfinite(v)]
        assert not np.isin(f, r.get('sentinels',[])).any()
        if r['domain'] == 'positive': assert (f > 0).all()
        if r['domain'] in ['nonnegative','count']: assert (f >= 0).all()
        if r['domain'] == 'count': assert np.equal(f, np.floor(f)).all() and (f < 4294967295).all()
        allowed = r.get('allowed_values', [-1,1] if r['domain']=='charge_sign' else [0,1] if r['domain']=='boolean' else None)
        if allowed is not None: assert np.isin(f, allowed).all()
    for j, det in enumerate(SCINTILLATORS):
        st = d['status'][:,j].astype(int); raw = d['raw_charge'][:,j].astype('float32').copy()
        raw[((st & WAVE_INVALID) != 0) | ~np.isfinite(raw)] = np.nan
        np.testing.assert_array_equal(d['x'][:,names.index(det+'_raw_charge')], raw)
        assert det+'_charge' not in names
        if j < 2:
            assert np.isnan(d['x'][(st & WAVE_INVALID) != 0,names.index(det+'_reduced_charge')]).all()
    c = d['x'][:,[names.index(f'ML_calo{j}_E_EM_GeV') for j in range(4)]]
    total = d['x'][:,names.index('ML_calo_total_E_EM_GeV')]
    assert np.isnan(c[(d['calo_status'].astype(int) & FIT_INVALID) != 0]).all()
    np.testing.assert_array_equal(total,c.astype(float).sum(1).astype('float32'))
    np.testing.assert_array_equal(np.isnan(total),np.isnan(c).any(1))
    np.testing.assert_array_equal(clean([-999,-1,0,1],dict(domain='nonnegative')),[np.nan,np.nan,0,1])
    np.testing.assert_array_equal(clean([-999,-1,0],dict(domain='signed')),[-999,-1,0])
    np.testing.assert_array_equal(clean([-999,-1,1],dict(domain='charge_sign')),[np.nan,-1,1])
    np.testing.assert_array_equal(clean([-999,-1,1],dict(domain='signed',sentinels=[-999])),[np.nan,-1,1])
    rows = supplement['row']; role = np.full(len(rows),'unused',dtype='<U6')
    role[old['train_eligible'][rows]] = 'train'; role[old['cal_eligible'][rows]] = 'cal'
    role[old['partition'][rows] == 'validation'] = 'eval'
    assert [int((role==r).sum()) for r in ['train','cal','eval']] == [41447,8440,14057]
    assert [len(np.unique(old['group'][rows[role==r]])) for r in ['train','cal','eval']] == [91,16,22]
    assert [int((np.isnan(x).any(1) & (role==r)).sum()) for r in ['train','cal','eval','unused']] == [21,3,7,11]
    ex = json.loads((OUT/'extractions.json').read_text())
    qa = json.loads((OUT/'QA.json').read_text()) if (OUT/'QA.json').exists() else [json.loads((OUT/f'qa{i}.json').read_text()) for i in range(20)]
    flow = read('cutflow'); formula = read('calo_formula'); qa_selected = 0
    for i, source in enumerate(p['sources']):
        take = d['source_index'] == i; a = ex[i]
        assert a['source'] == source and a['raw_N'] == 10000 and a['selected_N'] == take.sum()
        assert a['cutflow_passed'][-1] == take.sum() and np.all(np.diff(a['cutflow_passed']) <= 0)
        assert np.all(d['group'][take] == source['group']) and np.all(d['run'][take] == source['run'])
        assert len(np.unique(d['eventID'][take])) == take.sum() and np.all(np.diff(d['input_entry'][take]) > 0)
        assert np.all(d['input_entry'][take] < 10000)
        b = arrays(CACHE/f'qa{i}.npz'); m = take & (d['input_entry'] < 2)
        for key, value in b.items(): np.testing.assert_array_equal(d[key][m], value)
        qa_selected += len(b['run'])
        ff = [r for r in flow if int(r['source']) == i]
        assert [int(r['passed']) for r in ff] == a['cutflow_passed'] and [r['cut'] for r in ff] == a['cutflow_names']
        assert a['calibration_QA']['reference'] == md['reference'] and not a['calibration_QA']['rescaled']
    assert qa_selected == 0 and sum(len(q['identities']) for q in qa) == 40
    unit_counts = [sum(int(r['N']) for r in formula if int(r['module'])==j) for j in range(4)]
    assert all(v > 0 for v in unit_counts)
    for r in formula:
        if int(r['N']): assert np.isclose(float(r['median_MeV_per_pC']),330/.07129999995231628,rtol=2e-6,atol=.001)
    mm = strata(d); checked = 0
    for key, value in {**summary['new_lowE'], **summary['new_difficult']}.items():
        assert value == int((mm[key] & keep).sum())
    for r in read('identities'):
        take = np.ones(n,bool) if r['scope']=='all' else d['source_index']==int(r['scope'][6:])
        for key, value in [('selected_N',take.sum()), ('known_reuse_N',(take & reuse).sum()),
                           ('within_source_repeat_N',(take & same).sum()), ('cross_source_repeat_N',(take & cross).sum()),
                           ('known_repeat_overlap_N',(take & reuse & repeat).sum()), ('new_N',(take & keep).sum())]:
            assert int(r[key]) == value
        for stage in known:
            assert int(r[f'stage{stage}_reuse_N']) == int((take & d[f'known_stage{stage}_reuse']).sum())
    for r in read('feature_validity'):
        take = keep if r['state']=='new' else np.ones(n,bool)
        v = d['x'][take,names.index(r['feature'])]; f = v[np.isfinite(v)]
        assert [int(r[k]) for k in ['N','missing_N','negative_N','minus1_N','minus999_N']] == [len(v),int(np.isnan(v).sum()),int((v<0).sum()),int((v==-1).sum()),int((v==-999).sum())]
        if len(f): assert float(r['minimum']) == f.min() and float(r['maximum']) == f.max()
    for r in read('raw_validity'):
        take = keep if r['state']=='new' else np.ones(n,bool); j = SCINTILLATORS.index(r['detector'])
        st = d['status'][take,j].astype(int); raw = d['raw_charge'][take,j]
        expected = [len(raw),int((raw<0).sum()),int(((st&WAVE_INVALID)!=0).sum()),int((((st&48)!=0)&((st&WAVE_INVALID)==0)&np.isfinite(raw)).sum())]
        assert [int(r[k]) for k in ['N','negative_raw_N','wave_invalid_N','fit_failure_raw_valid_N']] == expected
    for r in read('support'):
        take = np.ones(n,bool) if r['scope']=='all' else d['source_index']==int(r['scope'][6:])
        state = dict(selected=np.ones(n,bool), known=reuse, internal=repeat, new=keep)[r['state']]
        m = take & state & mm[r['stratum']]
        assert int(r['N']) == m.sum() and int(r['sources']) == len(np.unique(d['source_index'][m]))
        assert int(r['unique_incoming']) == len(np.unique(d['incoming'][m],axis=0))
        checked += 1
    pooled = {k:np.concatenate([a[k] for a in previous]+[d[k][keep]]) for k in previous[0]}
    assert len(pooled['incoming']) == summary['pooled_new_N'] == 7720
    assert len(np.unique(pooled['incoming'],axis=0)) == 7720
    assert len(np.unique(pooled['group'])) == summary['pooled_groups'] == 26
    tr = role == 'train'
    baseline = dict(x=x[tr], **{k:old[k][rows[tr]] for k in ['truth_E_GeV','reco_pz_GeV','y_lepton','confirmed']})
    bm, pm = strata(baseline), strata(pooled)
    for r in read('training_context'):
        key = r['stratum']; a,b,cnt = int(bm[key].sum()),int((mm[key]&keep).sum()),int(pm[key].sum())
        assert [int(r[k]) for k in ['old_train_N','new_stage83_N','previous_new_N','pooled_new_N']] == [a,b,cnt-b,cnt]
        if a:
            assert np.isclose(float(r['stage83_increment_pct']),100*b/a) and np.isclose(float(r['pooled_increment_pct']),100*cnt/a)
    h = json.loads((OUT/'history.json').read_text()); pack = json.loads((OUT/'package_QA.json').read_text())
    assert len(h)==4 and all(a['JobStatus']==4 and a['ExitCode']==0 and a['NumJobStarts']==1 and a['RequestCpus']==1 and a['RequestMemory']==3000 and a['RemoteWallClockTime'] <= a['MaxRuntime'] <= 1800 for a in h)
    assert summary['remote_CPU_s'] == sum(a['RemoteUserCpu']+a['RemoteSysCpu'] for a in h) < 1800
    # Child CPU is cumulative within each QA shard: count only its final value.
    qa_cpu = sum(q['CPU_s'] for q in qa) + sum(qa[i]['extraction']['child_user_s']+qa[i]['extraction']['child_system_s'] for i in [4,9,14,19])
    qa_bytes = sum(q['scalar_requested_bytes']+q['ROOT_clone_requested_bytes']+q['calibration']['requested_uproot_bytes']+q['extraction']['requested_uproot_bytes'] for q in qa)
    package_bytes = sum(r['ROOT_clone_requested_bytes']+r['Uproot_requested_bytes'] for r in pack['records'])
    accounted_cpu = summary['remote_CPU_s']+qa_cpu+pack['CPU_s']+sum(r['child_CPU_s'] for r in pack['records'])
    assert accounted_cpu < 1800 and sum(s['file_bytes'] for s in p['sources']) == 611988745 < 10000000000
    records = read('source_resources')
    assert np.isclose(sum(float(a['CPU_s']) for a in records),summary['subprocess_CPU_sum_s'])
    assert sum(int(a['Uproot_requested_bytes']) for a in records) == summary['formal_requested_Uproot_bytes']
    result = dict(passed=True,selected_N=n,new_unique_N=int(keep.sum()),independent_numpy_key_and_stable_source_ownership=True,
                  new_key_old_exposure_intersection_N=0,source_role_and_original_cohort_unchanged=True,
                  original_missing_train_cal_eval_unused=[21,3,7,11],principal_strata=len(mm),support_table_rows_checked=checked,
                  raw11_status_and_typed_domains_exact=True,signed_negative_new_raw_N=int((d['raw_charge'][keep]<0).sum()),
                  new62_nonempty_selected_checked=n,QA_new_identity_N=40,QA_selected_N=qa_selected,
                  QA_empty_limit='same-identity equality is empty; nonempty old-cache package audit occurred after submission',
                  full_source_valid_nonzero_Calo_formula_counts=unit_counts,calo_nan_total_exact=True,
                  measured_QA_wall_sum_s=sum(q['wall_s'] for q in qa),measured_QA_CPU_s=qa_cpu,
                  measured_ROOT_Uproot_request_bytes_including_repeat_QA=summary['formal_requested_Uproot_bytes']+qa_bytes+package_bytes,
                  measured_partial_QA_package_and_Condor_CPU_s=accounted_cpu,
                  CPU_accounting_limit='QA module import/startup, package child Python overhead and old-cache check CPU unmeasured; not a total session CPU measurement',
                  four_condor_once_exit0=True,energy_fits=0,F7_inference=0,physical_EOS_network_IO='未测量',**resources(start))
    save(OUT/'validation.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1,2,figsize=(12,4.3))
    counts = [int((keep & (d['source_index']==i)).sum()) for i in range(20)]
    ax[0].bar(range(20),counts); ax[0].set_xticks(range(20),[s['group'][3:8] for s in p['sources']],rotation=65)
    ax[0].set_ylabel('New unique incoming keys'); ax[0].set_title('Stage83: complete frozen pi sources')
    keys = ['E50_100','E100_200','pz50_100_trueE200_inf','high_y','unconfirmed','E3200_6400']
    labels = ['E 50–100','E 100–200','low pz, E≥200','high-y','unconfirmed','E 3200–6400']
    pos = np.arange(len(keys)); oldvals = [sum(strata(a)[k].sum() for a in previous) for k in keys]
    ax[1].bar(pos,oldvals,label='prior pi+K (1786 total)')
    newvals = [int((keep & mm[k]).sum()) for k in keys]
    ax[1].bar(pos,newvals,bottom=oldvals,label='stage83 pi (+5934 total)')
    ax[1].set_xticks(pos,labels,rotation=35,ha='right'); ax[1].set_ylabel('New unique incoming keys')
    ax[1].set_title('Pooled support: 7720 keys, 26 sources'); ax[1].legend(fontsize=8)
    for i,(a,b) in enumerate(zip(oldvals,newvals)): ax[1].text(i,a+b,str(a+b),ha='center',va='bottom')
    fig.suptitle('Development enrichment; energies in GeV; strata overlap; no energy fits')
    fig.tight_layout(); fig.savefig(OUT/'support.png',dpi=150); plt.close(fig)


if __name__ == '__main__':
    main()
