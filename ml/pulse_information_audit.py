"""Stage79: bounded, train-only pulse semantics/variation audit; no energy fit."""
import argparse
import csv
import json
import resource
import time
from pathlib import Path

import awkward as ak
import numpy as np
import uproot

from audited_features import REPO, SCINTILLATORS, FIT_INVALID, WAVE_INVALID, build, configuration, load
from track_response import TRACK_BRANCHES, derive, configuration as track_configuration

OUT = REPO/'workbook/stage79_energy_ml'
DATA = REPO/'ntuples/energy_ml_stage79'
SUFFIXES = ['raw_charge', 'raw_peak', 'width', 'localtime', 'triggertime', 'bcidtime', 'baseline', 'baseline_rms', 'status']


def strong_shape_validity(data):
    """Conservative joint diagnostic mask, leaving signed raw integrals untouched.

    localtime is the nonnegative acquisition-window coordinate, not a signed
    corrected time. In particular bcid=-1 and MC trigger=0 are never timing data.
    The 5-sigma requirement is an audit convention, not a certified production cut.
    """
    status=np.asarray(data['status'],dtype=np.int64)
    valid=((status&(FIT_INVALID|1))==0)&np.isfinite(data['width'])&(data['width']>0)
    valid &= np.isfinite(data['localtime'])&(data['localtime']>0)
    valid &= np.isfinite(data['raw_peak'])&np.isfinite(data['baseline_rms'])&(data['baseline_rms']>0)
    return valid&(data['raw_peak']>=5*data['baseline_rms'])


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def prepare():
    """Freeze sources and QA identities before any new pulse values are read."""
    d, s, x = load()
    pool = s['row'][d['train_eligible'][s['row']]]
    assert len(pool) == 41447
    manifest = list(csv.DictReader((REPO/'ml/configs/low_energy_files.tsv').open(), delimiter='\t'))
    rng = np.random.default_rng(2026110379)
    selected = []
    source_pool = []
    for run in sorted(np.unique(d['run'][pool])):
        available = np.unique(d['source'][pool[d['run'][pool] == run]])
        chosen = sorted(rng.choice(available, 2, replace=False).tolist())
        source_pool.append(dict(run=int(run), eligible_sources=available.tolist(), selected=chosen, probability=2/len(available)))
        selected.extend(chosen)
    qa = []
    for source in selected:
        rows = pool[d['source'][pool] == source]
        for low, high in [(50,100), (100,250), (250,np.inf)]:
            candidates = rows[(d['reco_pz_GeV'][rows] >= low) & (d['reco_pz_GeV'][rows] < high)]
            if len(candidates):
                qa.append(int(rng.choice(candidates)))
    candidates = pool[np.isin(d['source'][pool], selected) & ~np.isin(pool, qa)]
    qa.extend(rng.choice(candidates, 40-len(qa), replace=False).tolist())
    assert len(set(qa)) == 40
    plan = dict(stage=79, seed=2026110379, original_train_N=len(pool), source_pool=source_pool,
                selected_sources=[manifest[i] for i in selected], qa_rows=sorted(qa),
                family=SUFFIXES, observed_new_values=False,
                sampling='two sources without replacement per run; balanced source x reco-pz strata; no truth/outcome/new-field selection',
                timing='local/triggertime retained as uncorrected diagnostic; no physical corrected relative time until actual clock/offset/path evidence',
                fit_valid='status & (FIT_INVALID|THRESHOLD_FAILED)==0; finite width>0; finite time; raw peak>0; baseline RMS>0',
                weak_signal='THRESHOLD_FAILED or raw_peak<=0 or raw_peak<5*baseline_rms; 5 is pinned primary threshold default, actual production threshold unverified',
                no_energy_training=True)
    assert not (OUT/'qa_plan.json').exists()
    save(OUT/'qa_plan.json', plan)
    print(json.dumps(dict(sources=selected, qa_N=len(qa), pool_N=len(pool))))


def intervals(tree, branches, entries):
    """Coalesce selected entries by the union of requested branch basket boundaries."""
    edges = sorted(set([0, tree.num_entries]+[int(e) for b in branches for e in tree[b].entry_offsets]))
    bins = np.searchsorted(edges, entries, side='right')-1
    parts = []
    calls = 0
    for key in np.unique(bins):
        take = entries[bins == key]
        # Basket decoding is transient; retain only the frozen identity rows.
        start, stop = int(take.min()), int(take.max())+1
        arr = tree.arrays(branches, entry_start=start, entry_stop=stop)
        parts.append(arr[take-start]); calls += 1
    joined = ak.concatenate(parts)
    order = np.argsort(np.concatenate([entries[bins == k] for k in np.unique(bins)]))
    return joined[order], calls


def original62(arr, d, s, rows):
    """Recompute original scalar/track definitions, then reuse the frozen typed policy."""
    names = json.loads(str(d['metadata_json']))['features']
    track = derive(arr, track_configuration(REPO)['features'], diagnostic=False)
    lead = ak.argmax(arr.Track_pz0, axis=1, keepdims=True)
    def leading(branch):
        return ak.to_numpy(ak.flatten(arr[branch][lead]))
    v = {k:track[k] for k in track_configuration(REPO)['features']}
    v.update(ML_mu_p_GeV=leading('Track_p0')/1000.0,
             ML_mu_px0_GeV=leading('Track_px0')/1000.0,
             ML_mu_py0_GeV=leading('Track_py0')/1000.0)
    for key in ['x0','y0','z0','X_atVetoNu','Y_atVetoNu','X_atCalo','Y_atCalo']:
        v['ML_mu_'+key+'_mm'] = leading('Track_'+key)
    for key in ['charge','nDoF','nLayers','r_atMaxRadius']:
        v['LeadTrack_'+key] = leading('Track_'+key)
    # Mirror ROOT vector element arithmetic before SafeAt promotes to double.
    px, py, pz = [leading('Track_'+k) for k in ['px0','py0','pz0']]
    v['LeadTrack_Theta'] = np.arctan(np.sqrt(px*px+py*py)/pz).astype(float)*1000
    xx, yy = [leading('Track_'+k) for k in ['X_atVetoNu','Y_atVetoNu']]
    v['LeadTrack_rVetoNu'] = np.sqrt(xx*xx+yy*yy)
    v['LeadTrack_Chi2_NDF'] = leading('Track_Chi2').astype(float)/leading('Track_nDoF')
    for key in ['nClusters0','nClusters1','nClusters2','nClusters3','SpacePoints','TrackSegments','longTracks']:
        v[key] = ak.to_numpy(arr[key])
    for scint in SCINTILLATORS:
        v[scint+'_charge'] = ak.to_numpy(arr[scint+'_charge'])
    for i in range(2):
        v[f'VetoNu{i}_reduced_charge'] = ak.to_numpy(arr[f'VetoNu{i}_reduced_charge'])
    for i in range(4):
        v[f'ML_calo{i}_E_EM_GeV'] = ak.to_numpy(arr[f'Calo{i}_E_EM'])/1000
    v['ML_calo_total_E_EM_GeV'] = sum(v[f'ML_calo{i}_E_EM_GeV'] for i in range(4))
    # ROOT VecOps::Mean uses a double accumulator; products retain element type.
    for axis in ['x','y']:
        means, rms = [], []
        for values in arr['SpacePoint_'+axis]:
            a = ak.to_numpy(values)
            m = sum(map(float,a))/len(a) if len(a) else np.nan
            sq = sum(map(float,a*a))/len(a) if len(a) else np.nan
            means.append(m); rms.append(np.sqrt(max(0,sq-m*m)) if len(a) else np.nan)
        v['ML_sp_mean_'+axis+'_mm'] = means
        v['ML_sp_rms_'+axis+'_mm'] = rms
    new = np.column_stack([v[n] for n in names]).astype('float32')
    new[~np.isfinite(new)] = np.nan
    temp = dict(x=new, reco_pz_GeV=leading('Track_pz0').astype(float)/1000,
                reco_p_GeV=track['reco_p_GeV'], metadata_json=d['metadata_json'])
    supplement = dict(row=np.arange(len(rows)),
        raw_charge=np.column_stack([ak.to_numpy(arr[k+'_raw_charge']) for k in SCINTILLATORS]),
        status=np.column_stack([ak.to_numpy(arr[k+'_status']) for k in SCINTILLATORS]),
        calo_status=np.column_stack([ak.to_numpy(arr[f'Calo{i}_status']) for i in range(4)]))
    actual = build(temp, supplement)
    expected = build(d, s)[np.searchsorted(s['row'],rows)] if np.all(np.diff(s['row'])>=0) else build(d,s)[[np.flatnonzero(s['row']==r)[0] for r in rows]]
    np.testing.assert_array_equal(actual, expected)
    np.testing.assert_array_equal(supplement['raw_charge'], s['raw_charge'][[np.flatnonzero(s['row']==r)[0] for r in rows]])
    return actual


def extract(mode, job=0):
    start, cpu = time.perf_counter(), time.process_time()
    d, s, _ = load()
    plan = json.loads((OUT/'qa_plan.json').read_text())
    if mode == 'qa':
        rows = np.array(plan['qa_rows'])
        sources = plan['selected_sources']
    else:
        frozen = json.loads((OUT/'measurement_plan.json').read_text())
        rows = np.array(frozen['rows']); sources = plan['selected_sources'][job::4]
        resource.setrlimit(resource.RLIMIT_CPU,(1700,1750))
    records, parts = [], []
    for source in sources:
        source_id = int(source['index'])
        take = rows[d['source'][rows] == source_id]
        if not len(take): continue
        tick, cputick = time.perf_counter(), time.process_time()
        with uproot.open(source['input'], array_cache=None) as f:
            t = f['nt']
            # Scalar eventID is only a transient identity index, no nonselected physics retained.
            ids = t['eventID'].array(library='np')
            assert len(np.unique(ids)) == len(ids)
            lookup = {int(e):i for i,e in enumerate(ids)}
            entries = np.array([lookup[int(e)] for e in d['eventID'][take]])
            order = np.argsort(entries); entries = entries[order]; take = take[order]
            branches = ['run','eventID','Track_PropagationError']+TRACK_BRANCHES
            branches += ['Track_'+k for k in ['nDoF','nLayers','Chi2','r_atMaxRadius','X_atVetoNu','Y_atVetoNu','X_atCalo','Y_atCalo']]
            branches += ['nClusters0','nClusters1','nClusters2','nClusters3','SpacePoints','TrackSegments','longTracks','SpacePoint_x','SpacePoint_y']
            branches += [k+'_'+suffix for k in SCINTILLATORS for suffix in SUFFIXES+['charge']]
            branches += [f'VetoNu{i}_reduced_charge' for i in range(2)]
            branches += [f'Calo{i}_{suffix}' for i in range(4) for suffix in ['E_EM','status']]
            branches += ['truth_'+k for k in ['pdg','px','py','pz']]
            arr, calls = intervals(t, branches, entries)
            requested = int(f.file.source.num_requested_bytes)
            schema = {k:t[k].typename for k in branches}
        assert requested < 2_000_000_000
        np.testing.assert_array_equal(ak.to_numpy(arr.run), d['run'][take])
        np.testing.assert_array_equal(ak.to_numpy(arr.eventID), d['eventID'][take])
        incoming = np.column_stack([ak.to_numpy(ak.firsts(arr['truth_'+k])) for k in ['pdg','px','py','pz']])
        np.testing.assert_array_equal(incoming,d['incoming'][take])
        x = original62(arr,d,s,take)
        part = dict(row=take, entry=entries, x=x)
        for suffix in SUFFIXES:
            part[suffix] = np.column_stack([ak.to_numpy(arr[k+'_'+suffix]) for k in SCINTILLATORS])
        parts.append(part)
        records.append(dict(source=source_id,N=len(take),input_entries=len(ids),requested_bytes=requested,
            array_calls=calls,wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cputick,
            identity_incoming_exact=True,original62_exact=True,raw_exact=True,schema=schema if mode=='qa' and not records else None))
    data = {k:np.concatenate([p[k] for p in parts]) for k in parts[0]}
    DATA.mkdir(exist_ok=True,parents=True)
    destination = DATA/('qa.npz' if mode=='qa' else f'part{job}.npz')
    assert not destination.exists()
    np.savez_compressed(destination,**data)
    stats = dict(mode=mode,job=job,N=len(data['row']),files=records,wall_s=time.perf_counter()-start,
        cpu_s=time.process_time()-cpu,peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
        requested_bytes=sum(r['requested_bytes'] for r in records),output_bytes=destination.stat().st_size,
        no_energy_fit=True,all_original62_exact=True)
    if mode=='qa':
        status=data['status'].astype(np.int64)
        assert np.all(status>=0) and np.all(status<1024)
        assert np.all(data['raw_peak'][np.isfinite(data['raw_peak'])]>=0)
        unique,counts=np.unique(status,return_counts=True)
        stats['pulse_QA']=dict(status_counts=dict(zip(map(str,unique),map(int,counts))),
            signed_negative_raw_N=int((data['raw_charge']<0).sum()),
            trigger_all_zero=bool(np.all(data['triggertime']==0)),bcid_all_zero=bool(np.all(data['bcidtime']==0)),
            physical_corrected_relative_time_available=False,
            units='raw_charge pC; raw_peak/baseline/baseline_rms mV; width/localtime ns',
            unknown_actual_upstream_AdvancedTiming_and_payload=True,
            permits='bounded diagnostic shape/localtime only; not certified new physical information')
    save(OUT/('qa_results.json' if mode=='qa' else f'extraction{job}.json'),stats)
    print(json.dumps({k:v for k,v in stats.items() if k!='files'}),flush=True)


def freeze():
    qa = json.loads((OUT/'qa_results.json').read_text())
    assert qa['N']==40 and qa['all_original62_exact']
    d,s,_ = load(); plan=json.loads((OUT/'qa_plan.json').read_text())
    rng=np.random.default_rng(plan['seed'])
    pool=s['row'][d['train_eligible'][s['row']]]
    strata=[]
    for source in plan['selected_sources']:
        source_id=int(source['index']);rows=pool[d['source'][pool]==source_id]
        source_p=next(r['probability'] for r in plan['source_pool'] if r['run']==int(source['run']))
        for lo,hi in [(50,100),(100,250),(250,np.inf)]:
            candidates=rows[(d['reco_pz_GeV'][rows]>=lo)&(d['reco_pz_GeV'][rows]<hi)]
            strata.append(dict(source=source_id,run=int(source['run']),component=source['component'],pz_low=lo,
                pz_high=None if np.isinf(hi) else hi,pool=candidates.tolist(),source_probability=source_p,n=0))
    target=min(2048,sum(len(r['pool']) for r in strata))
    for i in range(target):
        available=[j for j,r in enumerate(strata) if r['n']<len(r['pool'])]
        j=min(available,key=lambda j:(strata[j]['n'],j));strata[j]['n']+=1
    sample=[]
    for r in strata:
        chosen=rng.choice(r['pool'],r['n'],replace=False).tolist();sample.extend(chosen)
        r['N']=len(r.pop('pool'));r['within_probability']=r['n']/r['N'] if r['N'] else None
        r['inclusion_probability']=r['source_probability']*r['within_probability'] if r['N'] else None
    assert len(set(sample))==target
    measured=qa['requested_bytes']
    # Conservative full measured selected-source basket estimate, no assumed prefix rate.
    frozen=dict(stage=79,seed=plan['seed'],rows=sorted(sample),strata=strata,N=target,
        QA_passed=True,formal_value_access_before_freeze=False,
        jobs=4,CPUs_each=1,memory_MB_each=3000,CPU_total_limit_s=7200,wall_each_limit_s=3600,
        worker_CPU_soft_hard_s=[1700,1750],input_limit_bytes=10_000_000_000,retained_limit_bytes=10_000_000,
        QA_requested_bytes=measured,QA_wall_s=qa['wall_s'],QA_CPU_s=qa['cpu_s'],
        mechanism_limitation='actual upstream AdvancedTiming/payload not certified; bounded diagnostic measurement only, no corrected relative time or information gain claim')
    assert not (OUT/'measurement_plan.json').exists()
    save(OUT/'measurement_plan.json',frozen)
    print(json.dumps(dict(N=target,source_N=len(plan['selected_sources']),strata_N=len(strata))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['prepare','qa','freeze','extract']);p.add_argument('--job',type=int,default=0,choices=range(4));a=p.parse_args()
    if a.mode=='prepare':prepare()
    elif a.mode=='freeze':freeze()
    else:extract(a.mode,a.job)
