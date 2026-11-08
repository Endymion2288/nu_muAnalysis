"""Independent original4 reread and source/PMT/scalar verification on batch."""
import csv,json,subprocess,sys
from pathlib import Path
import numpy as np
OUT=Path('workbook/stage185_energy_ml')

def read(path):
    with path.open() as stream:return list(csv.DictReader(stream,delimiter='\t'))

if __name__=='__main__':
    with (OUT/'audit_native.log').open('w') as stream:
        result=subprocess.run(['/usr/bin/time','-v','-o',str(OUT/'audit_native_time.txt'),sys.executable,'-u','ml/stage185_native.py','audit'],stdout=stream,stderr=subprocess.STDOUT)
    if result.returncode:
        print((OUT/'audit_native.log').read_text()[-8000:]);raise RuntimeError(result.returncode)
    batch=read(OUT/'charges.tsv');repeated=read(OUT/'audit_charges.tsv');p=json.loads((OUT/'protocol.json').read_text())
    first=[r for r in batch if r['source_index']=='0'];assert first==repeated
    old=read(Path('workbook/stage184_energy_ml/preflight_source_0_charges.tsv'))
    cached=json.loads(Path('workbook/stage184_energy_ml/audit_source_0_summary.json').read_text())
    controls=['source_index','row','run','event','entry','detector','channel','ADC_present','status','raw_pC','rail_samples','window_start_ns','window_end_ns']
    assert len(first)==len(old)==60 and len(batch)==180
    changed=[]
    for now,previous in zip(first,old):
        assert all(now[k]==previous[k] for k in controls)
        if now['channel']!='14':assert float(now['ideal_pC'])==float(previous['ideal_pC'])
        else:
            candidate=next(r for r in cached['mapping_diagnostics'] if str(r['row'])==now['row'] and r['channel']==14)
            assert float(now['ideal_pC'])==candidate['all_Veto_current_physical_Q_pC']['15']
            assert now['current_physical_cable_channel']=='15'
            changed.append(dict(row=int(now['row']),old_current_channel14_Q_pC=float(previous['ideal_pC']),
                certified_same_PMT_Q_pC=float(now['ideal_pC']),raw_pC=float(now['raw_pC'])))
    summary=json.loads((OUT/'batch_summary.json').read_text());identity=json.loads((OUT/'identity_summary.json').read_text())
    observed=summary['identities'];expected=[(source,c) for source in p['sources'] for c in source['cases']]
    assert len(observed)==len(expected)==12 and len({r['row'] for r in observed})==12
    for (source,case),actual in zip(expected,observed):
        assert all(case[k]==actual[k] for k in ['row','entry','run','event','role']) and actual['role']==1
        assert source['index']==actual['source_index']
        np.testing.assert_array_equal(np.asarray(case['incoming'],dtype='float32'),np.asarray(actual['incoming'],dtype='float32'))
    assert sum(r['N'] for r in summary['HITS_counts'])==sum(s['parent_N'] for s in p['sources'])
    original_physical={(r['detector'],r['channel']):(r['station'],r['plate'],r['pmt']) for r in identity['channels']}
    for r in summary['mappings']:
        if r['detector']=='Calo':
            if r['stored_id32'] is not None:assert r['stored_id32']==r['current_id32']
        else:assert tuple(r['physical'])==original_physical[r['detector'],r['channel']]
    for r in summary['literal_checks']:
        assert abs(r['fast_pC']-r['literal_pC'])<=32*np.finfo('float32').eps*max(1,abs(r['literal_pC']))
    for r in batch:
        assert np.isfinite(float(r['ideal_pC'])) and float(r['ideal_pC'])>=0
        assert (r['ADC_present']=='True')==(r['raw_pC']!='')
    for name,records in [('channel14_physical_correction.tsv',changed),('event_resources.tsv',summary['event_resources'])]:
        with (OUT/name).open('w') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(records[0]),delimiter='\t',lineterminator='\n');writer.writeheader();writer.writerows(records)
    # Diagnostic errors are not a population noise model or calibrated interval.
    comparisons=[]
    for channel in p['channels']:
        rr=[r for r in batch if int(r['channel'])==channel];present=[r for r in rr if r['ADC_present']=='True']
        delta=np.array([float(r['raw_pC'])-float(r['ideal_pC']) for r in present])
        comparisons.append(dict(channel=channel,N=len(rr),ADC_present_N=len(present),negative_raw_N=sum(float(r['raw_pC'])<0 for r in present),
            rail_channels_N=sum(int(r['rail_samples'])>0 for r in present),
            raw_minus_ideal_median_pC=float(np.median(delta)) if len(delta) else None,
            raw_minus_ideal_abs_max_pC=float(np.max(abs(delta))) if len(delta) else None))
    with (OUT/'response_summary.tsv').open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(comparisons[0]),delimiter='\t',lineterminator='\n');writer.writeheader();writer.writerows(comparisons)
    result=dict(passed=True,parents_N=12,source_N=3,channels_N=180,original_train_only=True,independent_reread_parents_N=4,
        raw_status_availability_original60_exact=True,unaffected_original56_ideal_exact=True,physical_correction_original4_exact=True,
        literal_checks_N=len(summary['literal_checks']),max_abs_literal_delta_pC=max(r['abs_delta_pC'] for r in summary['literal_checks']),
        max_literal_tolerance_fraction=max(r['abs_delta_pC']/r['tolerance_pC'] for r in summary['literal_checks']),
        historical_physical_mapping_independent_of_charge=True,all_identity_incoming_and_totalN_exact=True,
        new_G4=0,new_forward=0,energy_fits=0,no_energy_gain_claim=True,overall_complete=False)
    result['performance']=dict(internal_complete_CPU_s=summary['CPU_s'],internal_complete_wall_s=summary['wall_s'],
        startup_to_first_execute_CPU_s=summary['startup_CPU_s'],startup_to_first_execute_wall_s=summary['startup_wall_s'],
        all_execute_CPU_s=sum(r['CPU_s'] for r in summary['event_resources']),
        literal_reference_CPU_s=sum(r['literal_CPU_s'] for r in summary['event_resources']),
        ROOT_requested_B=summary['ROOT_read_bytes'],RSS_KiB=summary['RSS_KiB'],
        allocated_CPUs=4,actual_Athena_process_N=1,process_initialization_N=1,
        controlled_serial_speedup='unmeasured; source content and literal-check count differ fromStage184')
    (OUT/'independent_validation.json').write_text(json.dumps(result,indent=2)+'\n');print(result,flush=True)
