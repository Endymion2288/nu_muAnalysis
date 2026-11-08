"""Batch-only measured complete-cost admission, before new cal/test fields."""
import json
from pathlib import Path
from stage158_finalize import gnu
OUT=Path('workbook/stage186_energy_ml')
if __name__=='__main__':
 p=json.loads((OUT/'protocol.json').read_text());validation=json.loads((OUT/'pilot_validation.json').read_text());assert validation['passed'] and validation['input_controls_passed']
 s=json.loads((OUT/'pilot_0_summary.json').read_text());events=s['event_resources'];cost=gnu(OUT/'pilot_0_time.txt')
 useful=[r for r in events if not r['first_source_event']];globalmean=sum(r['CPU_s']-r['literal_CPU_s'] for r in useful)/len(useful)
 means={}
 for source in s['sources']:
  vals=[r['CPU_s']-r['literal_CPU_s'] for r in useful if r['source_index']==source['index']]
  means[source['index']]=max(globalmean,sum(vals)/len(vals)) if vals else globalmean
 requests=json.loads(Path('workbook/stage129_energy_ml/extraction_contract.json').read_text())['requests'];per_event=sum(sum(c['role']>0 for c in q['cases'])*means.get(q['index'],max(means.values())) for q in requests)
 # Additional conservative transition allowance covers eight sources/group vs seven in pilot.
 extra_transition=35*max(r['CPU_s']-r['literal_CPU_s'] for r in events if r['first_source_event'])
 production=3*(35*cost['CPU_s']+per_event+extra_transition)
 used=json.loads((OUT/'scheduler_accounting.json').read_text())['total_CPU_s'];pending_pilot_reserve=1000;total=used+pending_pilot_reserve+production+8000
 memory_projection=8*cost['RSS_KiB']*1.25/1024
 result=dict(admitted=production<=168000 and total<=180000 and memory_projection<=24000,conservative_8reader_RSS_projection_MB=memory_projection,memory_cap_MB=24000,complete_main_GNU=cost,startup_before_first_execute_CPU_s=s['startup_CPU_s'],first_execute_including_cold_JIT_CPU_s=events[0]['CPU_s'],source_subsequent_mean_CPU_s={str(k):v for k,v in means.items()},global_subsequent_mean_CPU_s=globalmean,per_event_full_projection_CPU_s=per_event,extra_transition_CPU_s=extra_transition,triple_production_projection_CPU_s=production,already_used_scheduler_CPU_s=used,pending_pilot_audit_CPU_reserve_s=pending_pilot_reserve,fit_audit_reserved_CPU_s=8000,total_projection_CPU_s=total,CPU_budget_s=180000,pilot_ROOT_requested_B=s['ROOT_requested_B'],event_ROOT_requested_B=sum(r['ROOT_requested_B'] for r in events),full_ROOT_requested_B_projection=35*s['ROOT_requested_B']+71376/s['N']*sum(r['ROOT_requested_B'] for r in events),wall_IO_projection='provisional; source/file/cache variation not controlled',energy_fits=0,new_cal_test_fields=0,overall_complete=False)
 (OUT/'admission.json').write_text(json.dumps(result,indent=2)+'\n');print(result,flush=True)
