"""Condor-only cost/measurement admission before any full extraction or energy fit."""
import json,time
from pathlib import Path
import numpy as np
from stage158_finalize import gnu
OUT=Path('workbook/stage163_energy_ml');CACHE=Path('ntuples/energy_ml_stage163')
def read(name):return json.loads((OUT/name).read_text())
def main():
 pilot,repeat=read('pilot_summary.json'),read('repeat_summary.json');assert pilot['passed'] and repeat['passed']
 with np.load(CACHE/'pilot.npz') as z:p={k:z[k] for k in z.files}
 with np.load(CACHE/'repeat.npz') as z:r={k:z[k] for k in z.files}
 lookup={int(row):i for i,row in enumerate(p['row'])}
 for k,v in r.items():np.testing.assert_array_equal(v,p[k][[lookup[int(row)] for row in r['row']]])
 sources=read('source_manifest.json')['records'];measured=[s for s in pilot['sources'] if s['identity_exact_N']>0]
 assert measured and len(r['row'])==4 and repeat['identity_exact_N']==4
 # New amplitude is a separate source getter from calibrated fitted E; measured range/support is necessary.
 ratio_support=[]
 for source in measured:
  parent_rows={c['row'] for r in sources if r['index']==source['index'] for c in r['cases']}
  selected=np.asarray([int(row) in parent_rows for row in p['row']])
  for module in range(4):
   use=selected&np.isfinite(p['raw'][:,module])&np.isfinite(p['fit_E'][:,module])&(p['fit_E'][:,module]!=0)
   # Same exact source and channel: do not confuse inter-file calibration with amplitude content.
   ratio=p['raw'][use,module]/p['fit_E'][use,module]
   spread=float(np.ptp(ratio)) if len(ratio) else 0.
   round_bound=float(64*np.finfo('float32').eps*float(np.max(abs(ratio)))) if len(ratio) else 0.
   ratio_support.append(dict(source_index=source['index'],module=module,N=len(ratio),ratio_span=spread,float_rounding_bound=round_bound,nonproportional=bool(spread>round_bound)))

 independent_amplitude=pilot['raw_valid_fitted_missing_N']>0 or any(r['nonproportional'] for r in ratio_support)
 physical=bool(pilot['valid_raw_module_N']>0 and pilot['raw_dynamic_range'] and independent_amplitude)
 available=[s for s in sources if s['exists'] and s['active_N']]
 payload_per_entry=max(s['payload_CPU_s']/s['read_entries'] for s in measured)
 payload_per_byte=max(s['payload_CPU_s']/s['ROOT_read_bytes'] for s in measured)
 selected_fraction=max(s['branch_compressed_bytes']/next(r['file_bytes'] for r in sources if r['index']==s['index']) for s in measured)
 projected_bytes=sum(s['file_bytes'] for s in available)*min(1.,selected_fraction)
 # Actual N for full sources is read at execution; planned range no larger than source file.
 planned_entries=sum(max(c['entry'] for c in s['cases'])-min(c['entry'] for c in s['cases'])+1 for s in available)
 process_start=max(0.,gnu(OUT/'pilot_time.txt')['CPU_s']-sum(s['CPU_s'] for s in pilot['sources']))
 startup=8*process_start+len(available)*max(s['startup_CPU_s'] for s in measured)
 payload=max(planned_entries*payload_per_entry,projected_bytes*payload_per_byte)
 projected=3*(startup+payload);used=read('scheduler_accounting.json')['total_CPU_s']
 allowed=int((12000-used-1500)/8);admitted=bool(physical and used+projected+1500<=12000 and allowed>0)
 wall_per_byte=max(s['wall_s']/s['ROOT_read_bytes'] for s in measured)
 result=dict(passed=True,amplitude_nonproportional_support=ratio_support,additional_amplitude_supported=independent_amplitude,admitted=admitted,measurement_support=physical,independent4_exact=True,pilot_N=pilot['N'],
  measured_pilot_source_N=len(measured),available_active_sources=len(available),all_active_sources=sum(s['active_N']>0 for s in sources),
  known_unavailable_active_rows=sum(s['active_N'] for s in sources if not s['exists']),projected_branch_bytes=projected_bytes,
  projected_IO_wall_s=3*projected_bytes*wall_per_byte,projected_full_3x_CPU_s=projected,already_used_scheduler_CPU_s=used,
  per_batch_CPU_allowance_s=allowed,audit_fit_reserve_CPU_s=1500,CPU_budget_s=12000,
  cost_model=dict(process_start_CPU_s=process_start,max_source_start_CPU_s=max(s['startup_CPU_s'] for s in measured),
   max_payload_CPU_per_entry=payload_per_entry,max_payload_CPU_per_requested_byte=payload_per_byte,max_selected_branch_file_fraction=selected_fraction),
  caveat='3x source-pilot throughput projection, not hard I/O or completion guarantee for unmeasured compression/latency. Fixed disjoint per-job CPU caps enforce aggregate budget; no redefined source fields.')
 (OUT/'admission.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
if __name__=='__main__':main()
