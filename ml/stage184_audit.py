"""Independent byte-free scalar/identity audit; executed only on batch."""
import csv
import json
from collections import defaultdict
from pathlib import Path
import numpy as np
OUT=Path('workbook/stage184_energy_ml')

def table(name):
    with (OUT/name).open() as stream:return list(csv.DictReader(stream,delimiter='\t'))

if __name__=='__main__':
    p=json.loads((OUT/'protocol.json').read_text())
    original=table('preflight_source_0_charges.tsv');reread=table('audit_source_0_charges.tsv')
    assert original==reread,'Independent original HITS/RDO reread differs'
    ref=table('reference_closure.tsv');authoritative=table('stage179_authoritative.tsv')
    for row in ref:
        known=next(r for r in authoritative if r['index']==row['index'] and r['detector']==row['detector'] and r['channel']==row['channel'])
        assert float(row['reference_pC'])==float(known['ideal_no_noise_no_clip_no_quantization_pC'])
        bound=32*np.finfo('float32').eps*max(1,abs(float(row['reference_pC'])))
        assert abs(float(row['fast_pC'])-float(row['reference_pC']))<=bound
    admitted=json.loads((OUT/'admission.json').read_text())['admitted']
    full=[];literal=[];identities=[];timing=[]
    sources=p['sources'] if admitted else p['sources'][:1]
    for source in sources:
        phases=(['preflight','full'] if source['index']==0 else ['full']) if admitted else ['preflight']
        observed=[]
        for phase in phases:
            prefix=f'{phase}_source_{source["index"]}';s=json.loads((OUT/f'{prefix}_summary.json').read_text())
            assert s['passed'] and sum(c['N'] for c in s['HITS_counts'])==source['parent_N']
            observed+=s['identities'];full+=table(prefix+'_charges.tsv');literal+=s['literal_checks']
            timing.append({k:s[k] for k in ['source_index','phase','parents_N','CPU_s','wall_s','RSS_KiB','ROOT_read_bytes']})
        expected_cases=source['cases'] if admitted else source['cases'][:4]
        assert len(observed)==len(expected_cases)
        for expected,actual in zip(expected_cases,observed):
            assert all(actual[k]==expected[k] for k in ['row','entry','run','event','role'])
            np.testing.assert_array_equal(np.asarray(actual['incoming'],dtype='float32'),np.asarray(expected['incoming'],dtype='float32'))
        identities+=observed
    parents_N=96 if admitted else 4
    assert len(full)==parents_N*15 and len({r['row'] for r in full})==parents_N
    assert len({r['row'] for r in identities})==parents_N and all(r['role']==1 for r in identities)
    for row in full:
        assert int(row['channel']) in p['channels']
        assert float(row['ideal_pC'])>=0 and np.isfinite(float(row['ideal_pC']))
        assert [int(row['window_start_ns']),int(row['window_end_ns'])]==([780,930] if row['detector']=='Calo' else [780,980])
        assert (row['ADC_present']=='True')==(row['raw_pC']!='')
    for row in literal:
        bound=32*np.finfo('float32').eps*max(1,abs(row['literal_pC']))
        assert abs(row['fast_pC']-row['literal_pC'])<=bound
    grouped=defaultdict(list)
    for row in full:grouped[row['detector']].append(row)
    summary=[]
    for detector,rr in grouped.items():
        present=[r for r in rr if r['ADC_present']=='True']
        delta=[abs(float(r['raw_pC'])-float(r['ideal_pC'])) for r in present]
        summary.append(dict(detector=detector,channels_N=len(rr),ADC_present_N=len(present),
            negative_signed_raw_N=sum(float(r['raw_pC'])<0 for r in present),
            status0_N=sum(int(r['status'])==0 for r in present),rail_channels_N=sum(int(r['rail_samples'])>0 for r in present),
            ideal_zero_N=sum(float(r['ideal_pC'])==0 for r in rr),
            raw_ideal_abs_sum_pC=sum(delta),raw_ideal_abs_median_pC=float(np.median(delta))))
    for name,rows in [('charges.tsv',full),('response_summary.tsv',summary),('source_resources.tsv',timing)]:
        with (OUT/name).open('w') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n');writer.writeheader();writer.writerows(rows)
    result=dict(passed=True,parents_N=parents_N,planned96_executed=admitted,cost_gate_preserved=True,original_train_only=True,channel_records_N=len(full),
        independent_reread_parents_N=4,independent_reread_channel_scalar_rows_N=len(original),
        original12_reference_checks_N=len(ref),new_literal_checks_N=len(literal),
        max_new_literal_abs_delta_pC=max(r['abs_delta_pC'] for r in literal),
        max_new_literal_tolerance_fraction=max(r['abs_delta_pC']/r['tolerance_pC'] for r in literal),
        selected_identity_and_incoming_exact=True,source_event_totals_exact=True,
        physical_io_bytes='unmeasured; ROOT requested bytes reported separately',new_G4=0,new_forward=0,energy_fits=0,
        no_energy_gain_claim=True,overall_complete=False)
    (OUT/'independent_validation.json').write_text(json.dumps(result,indent=2)+'\n');print(result,flush=True)
