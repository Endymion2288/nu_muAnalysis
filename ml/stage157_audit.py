"""Batch-only partition invariance, root/current pairing and frozen CPU admission."""
import copy
import gzip
import json
import math
import re
import resource
import time
from pathlib import Path

OUT=Path('workbook/stage157_energy_ml');CACHE=Path('ntuples/energy_ml_stage157')
cpu,tick=time.process_time(),time.perf_counter()
plan=json.loads((OUT/'protocol.json').read_text())
account=json.loads((OUT/'scheduler_accounting.json').read_text())


def load(path):
    with gzip.open(path,'rt') as stream:return json.load(stream)


def exact(a,b):
    if isinstance(a,dict) and isinstance(b,dict):return a.keys()==b.keys() and all(exact(a[k],b[k]) for k in a)
    if isinstance(a,list) and isinstance(b,list):return len(a)==len(b) and all(exact(x,y) for x,y in zip(a,b))
    if isinstance(a,float) and isinstance(b,float) and math.isnan(a) and math.isnan(b):return True
    return a==b


def timing(path):
    text=path.read_text()
    return sum(float(re.search(r'(?m)^\s*'+re.escape(k)+r': (\S+)',text).group(1))
               for k in ['User time (seconds)','System time (seconds)'])


def canonical(record,geometry=True,qa=True):
    row=copy.deepcopy(record);row.pop('execute_end_CPU_s',None)
    if not geometry:row.pop('geometry',None)
    elif 'geometry' in row:row['geometry'].pop('same_process_native_repeat_exact',None)
    if not qa:row.pop('geometry_QA',None)
    return row


seq=load(CACHE/'chains/pilot_seq/native.json.gz');suffix=load(CACHE/'chains/pilot_suffix/native.json.gz')
pairs=load(CACHE/'chains/pilot_seq/paired.json.gz');suffix_pairs=load(CACHE/'chains/pilot_suffix/paired.json.gz')
seeds=json.loads((OUT/'chains/pilot_seq/seeds.json').read_text())
suffix_seeds=json.loads((OUT/'chains/pilot_suffix/seeds.json').read_text())
reference=load(plan['reference_current'])
old_native=json.loads(reference['ntuples/energy_ml_stage156/full/native.json.gz'])
old_pairs=json.loads(reference['ntuples/energy_ml_stage156/full/paired.json.gz'])
old_seeds=json.loads(reference['workbook/stage156_energy_ml/full/seeds.json'])
assert len(seq['records'])==128 and len(suffix['records'])==64
checks=[]
for i in range(64):
    a,b,c=seq['records'][i],seq['records'][64+i],suffix['records'][i]
    result=dict(entry=i,prefix_current156_exact=exact(canonical(a,False,False),canonical(old_native['records'][i],False,False)),
        prefix_geometry_exact=exact(canonical(a,True,False)['geometry'],canonical(old_native['records'][i],True,False)['geometry']),
        prefix_paired_exact=exact(pairs[i],old_pairs[i]),prefix_RNG_exact=all(exact(seeds['records'][i][k],old_seeds['records'][i][k]) for k in ['run','event','roots','seeds','before','after']),
        overlap_entry=64+i,suffix_native_geometry_exact=exact(canonical(b,True,False),canonical(c,True,False)),
        suffix_available_QA_exact=c['geometry_QA'] is None or exact(b['geometry_QA'],c['geometry_QA']),
        suffix_paired_exact=exact(pairs[64+i],suffix_pairs[i]),
        suffix_RNG_exact=all(exact(seeds['records'][64+i][k],suffix_seeds['records'][i][k]) for k in ['run','event','roots','seeds','before','after']))
    checks.append(result)
    assert all(v for k,v in result.items() if k not in ['entry','overlap_entry']),result
schema=[]
for name in ['pilot_seq','pilot_suffix']:
    value=json.loads((OUT/f'chains/{name}/schema.json').read_text());assert value['verified']
    value.pop('REC');schema.append(value)
assert exact(*schema)
for record in seq['records']:
    g=record['geometry'];assert g['anchor_counts']['valid']<=g['anchor_counts']['total']
    assert all(g[k] is None or g[k]<=1e-8 for k in ['max_state_roundtrip_mm','max_PRD_roundtrip_mm','independent_dx_max_delta_mm','max_candidate_roundtrip_mm'])
    for s in g['stations']:
        assert s['clusters']==s['leadingOwned']+s['nonleading']
        assert s['nonleading']==s['offMeasuredWafer']+s['onMeasuredWafer']
        if not s['available']:assert s['candidate_N'] is None
assert any(s['eligibleWafers'] for r in seq['records'] for s in r['geometry']['stations'])
physical=dict(passed=True,prefix_current156_N=64,overlap_N=64,unique_pilot_parent_N=128,
    physical_parent_executions=320,duplicate_parent_executions=192,checks=checks,
    schema_exact_except_scratch_path=True,overlap_QA_parent_N=4,positive_candidate_required=False,
    leading_parent_N=sum(r['geometry']['leading_identity_known'] for r in seq['records']),
    anchor_N=sum(r['geometry']['anchor_counts']['total'] for r in seq['records']),
    valid_anchor_N=sum(r['geometry']['anchor_counts']['valid'] for r in seq['records']))
(OUT/'partition_validation.json').write_text(json.dumps(physical,indent=2)+'\n')
costs=[]
for name in ['pilot_seq','pilot_suffix']:
    values={step:timing(OUT/f'chains/{name}/{step}_time.txt') for step in ['digi','reco','native','extract']}
    costs.append(dict(label=name,child_GNU_CPU_s=values,total_child_GNU_CPU_s=sum(values.values())))
projected=3*64*max(row['total_child_GNU_CPU_s'] for row in costs)
admission=dict(admitted=bool(projected+500 < 60000-account['total_CPU_s']),physical_passed=True,
    costs=costs,full64chunks_factor3_CPU_s=projected,audit_reserve_CPU_s=500,
    already_used_scheduler_CPU_s=account['total_CPU_s'],remaining_CPU_s=60000-account['total_CPU_s'],
    independent_parent_cap=4096,chunk_N=64,job_N=16,CPUs_per_job=4,max_initial_active_jobs=4,
    scope='Includes first/lazyJIT; max actual complete128/suffix64 GNU child totals per64 chunk. Prospective cost, no measured4096 or parallel speedup claim.')
if not (OUT/'full_admission.json').exists():(OUT/'full_admission.json').write_text(json.dumps(admission,indent=2)+'\n')
report=dict(phase='pilot',passed=True,independent_parent_N=128,physical_parent_executions=320,
    partition_passed=True,admitted=admission['admitted'],new_G4=0,energy_fits=0,response_fits=0,
    population_FPR_measured=False,overall_complete=False,CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,
    RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
(OUT/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
print('ADMISSION',admission,'SUMMARY',report,flush=True)

with gzip.open(CACHE/'pilot_reference.json.gz','wt') as stream:
    json.dump(dict(native=seq,pairs=pairs,seeds=seeds),stream,separators=(',',':'))
if all((CACHE/f'chains/chunk_{i:02d}/native.json.gz').exists() for i in range(64)):
    from stage157_full import run
    run()
