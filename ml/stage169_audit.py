"""Independent scalar extraction, count flags, aggregation and interval sweeps."""
import csv
import gzip
import json
import re
import shlex
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage169_energy_ml'


def write(name,value):
    (OUT/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def sweep(intervals):
    events=defaultdict(int)
    for left,right in intervals:
        if left<right:events[left]+=1;events[right]-=1
    total=0;active=0;previous=0
    for x,change in sorted(events.items()):
        if active:total+=x-previous
        active+=change;previous=x
    assert active==0
    return total


p=json.loads((OUT/'protocol.json').read_text())['inputs']
frozen=json.loads((OUT/'inputs.json').read_text())
original=json.loads((ROOT/p['source_manifest']).read_text())
contract=json.loads((ROOT/p['completed_sources']).read_text())
assert contract['all_source_indices']==frozen['completed_sources'] and len(contract['all_source_indices'])==666
with gzip.open(ROOT/p['source_accounting'],'rt') as f:saved={r['index']:r for r in json.load(f)}
assert set(saved)==set(contract['all_source_indices'])
header=json.loads((ROOT/p['actual_EVNT_headers']).read_text())
lengths={r['path']:r['N'] for r in header['records']}
assert len(lengths)==22
oldpaths=json.loads((ROOT/p['frozen_run_paths']).read_text())
assert [r['EVNT'] for r in original['inventory']]==oldpaths['unique_paths']
with (ROOT/p['source_selected_table']).open() as f:previous={int(r['index']):r for r in csv.DictReader(f,delimiter='\t')}
with (OUT/'source_accounting.tsv').open() as f:reported=list(csv.DictReader(f,delimiter='\t'))
assert [int(r['index']) for r in reported]==contract['all_source_indices']
measured=json.loads((ROOT/p['actual_log_bounds']).read_text())['sources']
assert [r['index'] for r in measured]==frozen['pilot_sources']
proof={r['index']:r for r in measured}
actual=[];native_verified=[]
for display in reported:
    index=int(display['index']);s=original['sources'][index];meta=saved[index]['metadata']
    qa,request=meta['source_qa.json'],meta['request_summary.json']
    assert request['source']==s
    count={name:int(qa[name]) for name in ['truth_superset_N','selected_N']}
    count['parent_N']=int(request['parent_N'])
    count['full_parent_N']=int(request['full_parent_N'])
    parts=s['segment'].split('-');left=int(parts[0])*1000;right=(int(parts[1])+1)*1000
    available=len(range(left,min(right,lengths[s['EVNT']])))
    linked=int(meta['parentmap.json']['eventID_entry_incoming_exact_N']) if 'parentmap.json' in meta else int(previous[index]['actual_EVNT_entry_matches'])
    expected=dict(index=index,run=s['run'],component=s['component'],role=s['inherited_role'],EVNT=s['EVNT'],
        **count,claim_start=left,claim_stop_exclusive=right,claim_requested_N=right-left,
        claim_available_N=available,claim_clipped_at_EOF=right>lengths[s['EVNT']],generator_N=lengths[s['EVNT']],
        filename_claim_only=True,qa_parent_N=int(qa['parent_N']),linked_selected_N=linked,
        counts_nonnegative=all(v>=0 for v in count.values()),
        count_hierarchy=0<=count['selected_N']<=count['truth_superset_N']<=count['parent_N'],
        parent_full_equal=count['parent_N']==count['full_parent_N'],parent_qa_equal=count['parent_N']==qa['parent_N'],
        parent_claim_available_equal=count['parent_N']==available,
        selected_table_equal=count['selected_N']==int(previous[index]['selected_N']),
        selected_link_count_equal=linked==count['selected_N'],actual_log_bounds=index in proof,
        native_scanned_N=None,native_available_equal=None,native_selected_equal=None)
    if index in proof:
        item=proof[index];native=json.loads((ROOT/frozen['native_summaries'][str(index)]).read_text())
        commands=[shlex.split(r['command']) for r in item['boundary_logs']]
        first=int(commands[0][commands[0].index('--skip')+1])
        stop=int(commands[-1][commands[-1].index('--skip')+1])+int(commands[-1][commands[-1].index('-n')+1])
        assert all(c[1]==s['EVNT'] for c in commands)
        assert first==item['skip']==left and stop==item['skip']+item['count']==right
        assert native['EVNT']==s['EVNT'] and native['skip']==left and native['requested_N']==right-left
        expected.update(native_scanned_N=native['scanned_N'],native_available_equal=native['scanned_N']==available,
                        native_selected_equal=native['selected_records_N']==count['selected_N'])
        native_verified.append(index)
    assert {k:'NA' if v is None else str(v) for k,v in expected.items()}==display,(index,expected,display)
    actual.append(expected)
full=json.loads((OUT/'full_summary.json').read_text())
fields=['parent_N','full_parent_N','truth_superset_N','selected_N','claim_requested_N','claim_available_N']
assert full['counters']=={k:sum(r[k] for r in actual) for k in fields}
checks=list(full['check_pass_N'])
assert full['check_pass_N']=={k:sum(bool(r[k]) for r in actual) for k in checks}
assert full['discrepancies']==[r for r in actual if not all(r[k] for k in checks)]
assert full['EOF_clipped_completed_sources']==[r['index'] for r in actual if r['claim_clipped_at_EOF']]
assert full['native_scan_N']==sum(r['native_scanned_N'] for r in actual if r['actual_log_bounds'])
assert full['native_available_exact_N']==sum(r['native_available_equal'] is True for r in actual)
assert next(r for r in actual if r['index']==508)['native_scanned_N']==4877
savedtotals=json.loads((ROOT/p['stage130_totals']).read_text())
assert full['saved_total_checks']==dict(parent=full['counters']['parent_N']==savedtotals['PHYS_parent_N'],
                                     selected=full['counters']['selected_N']==savedtotals['selected_records_N'])
grouped=json.loads((OUT/'grouped_counters.json').read_text())
for field,groups in grouped.items():
    for g in groups:
        take=[r for r in actual if r[field]==g[field]]
        assert g==dict(**{field:g[field]},sources=len(take),**{k:sum(r[k] for r in take) for k in fields})
    with (OUT/('by_'+field+'.tsv')).open() as f:tab=list(csv.DictReader(f,delimiter='\t'))
    assert tab==[{k:str(v) for k,v in r.items()} for r in groups]
assert full['original_role_component_run_counts']==grouped
ranges=json.loads((OUT/'range_claims.json').read_text());done=set(contract['all_source_indices'])
for row in ranges:
    subset=[s for s in original['sources'] if s['run']==row['run']]
    n=row['generator_N'];assert lengths[row['EVNT']]==n
    intervals=[];chosen=[]
    for s in subset:
        lo,hi=[int(x) for x in s['segment'].split('-')]
        span=(lo*1000,min((hi+1)*1000,n));intervals.append(span)
        if s['index'] in done:chosen.append(span)
    assert row['historical_sources']==len(subset) and row['completed_sources']==len(chosen)
    assert row['historical_claim_union_N']==sweep(intervals)
    assert row['completed_claim_union_N']==sweep(chosen)
    assert row['historical_unclaimed_generator_N']==n-sweep(intervals)
    assert row['completed_unclaimed_generator_N']==n-sweep(chosen)
    assert row['nominal_sources']==sum(s['nominal'] for s in subset)
    assert row['eligible_alternative_sources']==sum(s['eligible'] and not s['nominal'] for s in subset)
    assert row['alternative_ineligible_sources']==sum(not s['eligible'] and not s['nominal'] for s in subset)
    assert row['old_locked_sources']==sum(s['old_locked'] for s in subset)
with (OUT/'range_claims_by_run.tsv').open() as f:tab=list(csv.DictReader(f,delimiter='\t'))
assert tab==[{k:str(v) for k,v in r.items()} for r in ranges]
write('independent_validation.json',dict(passed=True,scalar_source_rows_exact=len(actual),
    native_summaries_and_logged_bounds_exact=len(native_verified),interval_sweep_runs_exact=len(ranges),
    grouped_tables_exact=True,all_reported_counts_and_flags_exact=True,source508_actual_scanned_N=4877,
    no_ROOT_or_event_array_access=True,physical_acceptance_certified=False))
write('accounting_evidence.json',dict(completed_source_N=len(actual),historical_source_N=len(original['sources']),
    actual_counters=full['counters'],counter_checks=full['check_pass_N'],
    EOF_completed_source_N=len(full['EOF_clipped_completed_sources']),
    EOF_actual_parent_N=sum(r['parent_N'] for r in actual if r['claim_clipped_at_EOF']),
    EOF_nominal_requested_N=sum(r['claim_requested_N'] for r in actual if r['claim_clipped_at_EOF']),
    source508=next(r for r in actual if r['index']==508),
    original_native_scanned_sum=full['native_scan_N'],native_available_exact=full['native_available_exact_N'],
    historical_claim_union_sum=sum(r['historical_claim_union_N'] for r in ranges),
    completed_claim_union_sum=sum(r['completed_claim_union_N'] for r in ranges),
    generated_record_sum=sum(r['generator_N'] for r in ranges),
    completed_unclaimed_generator_sum=sum(r['completed_unclaimed_generator_N'] for r in ranges),
    historical_unclaimed_generator_sum=sum(r['historical_unclaimed_generator_N'] for r in ranges),
    historical_nominal_sources=sum(r['nominal_sources'] for r in ranges),
    historical_eligible_alternative_sources=sum(r['eligible_alternative_sources'] for r in ranges),
    historical_ineligible_alternative_sources=sum(r['alternative_ineligible_sources'] for r in ranges),
    original_roles=[r for r in grouped['role']],
    complete_unselected_identity_proven=False,weighted_normalization_certified=False,
    full_generation_acceptance_certified=False,data_exposure_certified=False,
    interpretation='Counter closure and range declarations are measured; they do not prove unselected event identity or complete generator processing. No selected/N acceptance ratio computed.',
    missing=['actual per-generated-event success/filter/failure identity accounting and producer definitions',
             'named generator weights and physical normalization/exposure with correlated auxiliary information',
             'matched data DAQ/luminosity,background and independent confirmation'],overall_complete=False,promotion=False))
