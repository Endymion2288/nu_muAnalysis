"""All666 scalar counters and all1134 filename declarations, not event efficiency."""
import json
import resource
import time
from stage169_common import OUT,COUNTS,load,source_row,claim,union_length,aggregate,table,write

cpu,wall=time.process_time(),time.perf_counter()
assert json.loads((OUT/'admission.json').read_text())['admitted']
data=load();rows=[source_row(i,data) for i in data['frozen']['completed_sources']]
pilot=json.loads((OUT/'pilot_summary.json').read_text());lookup={r['index']:r for r in rows}
assert all(lookup[r['index']]==r for r in pilot['records'])
table('source_accounting.tsv',rows)
groups={label:aggregate(rows,keys) for label,keys in
        [('run',['run']),('component',['component']),('role',['role'])]}
for key,value in groups.items():table('by_'+key+'.tsv',value)
write('grouped_counters.json',groups)
coverage=[]
completed=set(data['frozen']['completed_sources'])
for inv in data['original']['inventory']:
    n=data['headers'][inv['EVNT']];original=[data['original']['sources'][i] for i in inv['source_indices']]
    assert all(s['run']==inv['run'] and s['EVNT']==inv['EVNT'] for s in original)
    allclaims=[claim(s,n) for s in original]
    doneclaims=[claim(s,n) for s in original if s['index'] in completed]
    intervals=lambda claims:[(r['claim_start'],min(n,r['claim_stop_exclusive'])) for r in claims]
    allunion=union_length(intervals(allclaims));doneunion=union_length(intervals(doneclaims))
    coverage.append(dict(run=inv['run'],nominal=inv['nominal'],EVNT=inv['EVNT'],generator_N=n,
        historical_sources=len(original),completed_sources=len(doneclaims),
        historical_claim_union_N=allunion,completed_claim_union_N=doneunion,
        historical_unclaimed_generator_N=n-allunion,completed_unclaimed_generator_N=n-doneunion,
        nominal_sources=sum(s['nominal'] for s in original),
        eligible_alternative_sources=sum(s['eligible'] and not s['nominal'] for s in original),
        alternative_ineligible_sources=sum(not s['eligible'] and not s['nominal'] for s in original),
        old_locked_sources=sum(s['old_locked'] for s in original),
        filename_claims_only=True,actual_all_event_processing_certified=False))
table('range_claims_by_run.tsv',coverage);write('range_claims.json',coverage)
sums={key:sum(r[key] for r in rows) for key in COUNTS+['claim_requested_N','claim_available_N']}
checks=['counts_nonnegative','count_hierarchy','parent_full_equal','parent_qa_equal',
        'parent_claim_available_equal','selected_table_equal','selected_link_count_equal']
write('full_summary.json',dict(passed=True,source_N=len(rows),historical_source_N=len(data['original']['sources']),
    pilot16_exact=True,counters=sums,check_pass_N={key:sum(r[key] for r in rows) for key in checks},
    discrepancies=[r for r in rows if not all(r[key] for key in checks)],
    EOF_clipped_completed_sources=[r['index'] for r in rows if r['claim_clipped_at_EOF']],
    native_scan_N=sum(r['native_scanned_N'] for r in rows if r['actual_log_bounds']),
    native_available_exact_N=sum(r['native_available_equal'] is True for r in rows),
    saved_total_checks=dict(parent=sums['parent_N']==data['totals']['PHYS_parent_N'],
        selected=sums['selected_N']==data['totals']['selected_records_N']),
    original_role_component_run_counts=groups,load_resources=data['load_resources'],
    CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-wall,
    RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    full_generated_acceptance_certified=False,normalization_certified=False,
    complete_unselected_identity_proven=False,energy_fits=0,model_forward=0,new_G4=0,
    overall_complete=False,promotion=False))
