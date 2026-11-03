"""Independent persisted-table, event-role, status and resource checks for stage79."""
import csv
import json
import time

import numpy as np

from audited_features import configuration, load, SCINTILLATORS
from pulse_information_audit import OUT, DATA, save, strong_shape_validity


def main():
    start=time.perf_counter();d,s,x=load();plan=json.loads((OUT/'measurement_plan.json').read_text())
    with np.load(DATA/'measurements.npz') as data:z={k:data[k] for k in data.files}
    rows=z['row'];np.testing.assert_array_equal(rows,plan['rows']);assert len(set(rows))==2048
    assert np.all(d['train_eligible'][rows]) and np.all(d['nominal'][rows])
    index={int(r):i for i,r in enumerate(s['row'])};ix=np.array([index[int(r)] for r in rows])
    np.testing.assert_array_equal(z['x'],x[ix]);np.testing.assert_array_equal(z['raw_charge'],s['raw_charge'][ix])
    for key in ['status','baseline_rms']:np.testing.assert_array_equal(z[key],s[key][ix])
    # For these actual inputs the conservative diagnostic predicate reduces to status=0.
    np.testing.assert_array_equal(z['strong_shape_valid'],z['status']==0)
    test=dict(status=np.array([0,0,0,0,0,0,1,4,16,32,64,128,256]),width=np.ones(13)*3,
              localtime=np.ones(13)*820,raw_peak=np.ones(13)*10,baseline_rms=np.ones(13))
    test['width'][1]=-999;test['width'][2]=-1;test['localtime'][3]=-999;test['baseline_rms'][4]=-1;test['raw_peak'][5]=-1
    # CLOCK_INVALID alone does not invalidate a local acquisition coordinate; it
    # does preclude treating BCID as a physical common-clock time.
    np.testing.assert_array_equal(strong_shape_validity(test),[True,False,False,False,False,False,False,False,False,False,True,False,False])
    pairs=list(csv.DictReader((OUT/'conditional_pairs.tsv').open(),delimiter='\t'));where={int(r):i for i,r in enumerate(rows)}
    used={k:set() for k in SCINTILLATORS};names=configuration()['features'];geom=[names.index('ML_mu_'+k+'_mm') for k in ['x0','y0','z0','X_atVetoNu','Y_atVetoNu','X_atCalo','Y_atCalo']]
    for pair in pairs:
        a,b=[where[int(pair[k])] for k in ['row_a','row_b']];detector=pair['detector'];j=SCINTILLATORS.index(detector)
        assert a not in used[detector] and b not in used[detector];used[detector].update([a,b])
        assert d['source'][rows[a]]!=d['source'][rows[b]] and d['component'][rows[a]]==d['component'][rows[b]]
        assert z['strong_shape_valid'][a,j] and z['strong_shape_valid'][b,j]
        assert abs(np.arcsinh(float(z['raw_charge'][a,j]))-np.arcsinh(float(z['raw_charge'][b,j])))<=.1
        assert abs(np.log(d['reco_pz_GeV'][rows[a]]/d['reco_pz_GeV'][rows[b]]))<=.2
        assert np.all(np.abs(z['x'][a,geom].astype(float)-z['x'][b,geom].astype(float))<=np.array([20,20,100,20,20,20,20]))
        assert abs(float(z['baseline_rms'][a,j])-float(z['baseline_rms'][b,j]))<=.1
        for key in ['width','raw_peak','localtime']:
            assert float(pair['delta_'+key])==float(z[key][a,j])-float(z[key][b,j])
    summarized=list(csv.DictReader((OUT/'conditional_variation.tsv').open(),delimiter='\t'))
    for r in summarized:
        if r['kind']!='all':continue
        values=[p for p in pairs if p['detector']==r['detector']];assert int(r['disjoint_pairs_N'])==len(values)
        if values:
            for key in ['width','raw_peak','localtime']:
                assert float(r[key+'_abs_median'])==float(np.median([abs(float(p['delta_'+key])) for p in values]))
    evidence=json.loads((OUT/'source_evidence.json').read_text())
    assert len(evidence['records'])==12 and all(r['exact_output_name_present'] and len(r['scint_advanced_algorithms'])==4 for r in evidence['records'])
    assert all(r['identical'] for r in evidence['pinned_digitization_comparisons'])
    history=json.loads((OUT/'condor_history.json').read_text());assert len(history)==4
    assert all(r['ExitCode']==0 and r['NumJobStarts']==1 and r['RequestCpus']==1 and r['RequestMemory']==3000 and r['MaxRuntime']==3600 for r in history)
    keys=['ClusterId','ProcId','JobStatus','ExitCode','NumJobStarts','RequestCpus','RequestMemory','MaxRuntime','RemoteUserCpu','RemoteSysCpu','RemoteWallClockTime','MemoryUsage']
    save(OUT/'condor_history.json',[{k:r.get(k) for k in keys} for r in sorted(history,key=lambda r:r['ProcId'])])
    save(OUT/'validation.json',dict(N=len(rows),unique_sources=len(np.unique(d['source'][rows])),original62_raw_status_rms_exact=True,
        all_legal_nominal_train=True,status_sentinel_dependency_synthetic=True,all_saved_pairs_controls_and_deltas_exact=True,
        all_pair_medians_exact=True,production_logs_and_source_versions=True,four_Condor_jobs_exit0_one_start=True,
        remote_CPU_sum_s=sum(r['RemoteUserCpu']+r['RemoteSysCpu'] for r in history),remote_wall_sum_s=sum(r['RemoteWallClockTime'] for r in history),
        actual_negative_raw_N=int((z['raw_charge']<0).sum()),pair_channel_rows=len(pairs),unique_paired_event_N=len(set.union(*used.values())),
        wall_s=time.perf_counter()-start,no_energy_fit=True,no_new_ROOT=True))
    print('Persisted measurements, 62 features, sentinel dependencies, pairs, source evidence and ClassAds passed.')


if __name__=='__main__':main()
