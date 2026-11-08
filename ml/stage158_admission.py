"""Batch-only original-reference and independent-prefix verification, then CPU admission."""
import gzip
import json
import re
from pathlib import Path

OUT=Path('workbook/stage158_energy_ml');CACHE=Path('ntuples/energy_ml_stage158')
plan=json.loads((OUT/'protocol.json').read_text())
account=json.loads((OUT/'scheduler_accounting.json').read_text())


def load(path):
    with gzip.open(path,'rt') as stream:return json.load(stream)


def canonical(row):
    row=row.copy()
    for key in ['execute_CPU_s','same_process_native_repeat_exact','old_counts_exact']:row.pop(key,None)
    return row


pilot=load(CACHE/'pilot.json.gz');repeat=load(CACHE/'repeat.json.gz')
reference=load(plan['input_geometry_reference'])
prior=json.loads(reference['ntuples/energy_ml_stage155/full.json.gz'])
original=[r for r in pilot['records'] if r['source_index']==0]
assert len(original)==len(prior['records'])==40
assert all(canonical(a['geometry'])==canonical(b) for a,b in zip(original,prior['records']))
assert all(canonical(a['geometry'])==canonical(b['geometry']) and a['old_counts']==b['old_counts']
    for a,b in zip(original,repeat['records']))
assert len(repeat['records'])==4 and pilot['QA']==repeat['QA']==prior['QA']
known=[r for r in pilot['records'] if r['row']==40738]
assert len(known)==1 and not known[0]['leading_match'] and not known[0]['geometry']['leading_identity_known']
assert all(s['candidate_N'] is None for s in known[0]['geometry']['stations'])
summary=json.loads((OUT/'pilot_summary.json').read_text())
assert all(r['schema']['verified'] for r in summary['metadata'])
assert summary['first_parent_native_repeat_exact']
assert summary['valid_geometry_parent_N']>0
for record in pilot['records']:
    g=record['geometry']
    assert all(g[k] is None or g[k]<=1e-8 for k in ['max_state_roundtrip_mm','max_PRD_roundtrip_mm','independent_dx_max_delta_mm','max_candidate_roundtrip_mm'])
text=(OUT/'pilot_time.txt').read_text()
GNU=sum(float(re.search(r'(?m)^\s*'+re.escape(k)+r': (\S+)',text).group(1)) for k in ['User time (seconds)','System time (seconds)'])
times=summary['event_CPU_s']
steady={key:sum(values[1:])/(len(values)-1) for key,values in times.items() if len(values)>=2}
assert steady
# Include every source's first event, not just the first process event, in the base.
startup=GNU-sum(sum(values[1:]) for values in times.values())
assert startup>0
projection=3*(37*startup+71376*max(steady.values()))
result=dict(admitted=bool(projection+1000<30000-account['total_CPU_s']),physical_passed=True,
    pilot_N=len(pilot['records']),repeat_N=4,reference40_exact=True,independent_prefix4_exact=True,
    known_leading_mismatch_preserved=True,known_mismatch_row=40738,
    GNU_pilot_CPU_s=GNU,measured_startup_and_first_events_CPU_s=startup,
    steady_mean_event_CPU_s_by_request=steady,full37batch_3x_projected_CPU_s=projection,
    already_used_scheduler_CPU_s=account['total_CPU_s'],audit_fit_reserve_CPU_s=1000,
    CPU_budget_s=30000,remaining_CPU_s=30000-account['total_CPU_s'],new_G4=0,energy_fits=0,
    limitation='Prospective affine cost model, all source first events retained in base; no measured full runtime or energy risk. Singleton mismatch is not a steady-cost estimator.')
assert not (OUT/'full_admission.json').exists()
(OUT/'full_admission.json').write_text(json.dumps(result,indent=2)+'\n')
print('ADMISSION',result,flush=True)
