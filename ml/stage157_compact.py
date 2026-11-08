"""Worker-only compact RNG transport, preserving actual prefix comparisons first."""
import copy
import gzip
import json
import math
import sys
from pathlib import Path

OUT=Path('workbook/stage157_energy_ml');CACHE=Path('ntuples/energy_ml_stage157')
group=int(sys.argv[1].removeprefix('batch_'))


def load(path):
    with gzip.open(path,'rt') as stream:return json.load(stream)


def exact(a,b):
    if isinstance(a,dict) and isinstance(b,dict):return a.keys()==b.keys() and all(exact(a[k],b[k]) for k in a)
    if isinstance(a,list) and isinstance(b,list):return len(a)==len(b) and all(exact(x,y) for x,y in zip(a,b))
    if isinstance(a,float) and isinstance(b,float) and math.isnan(a) and math.isnan(b):return True
    return a==b


def canonical(record):
    row=copy.deepcopy(record);row.pop('execute_end_CPU_s',None);row.pop('geometry_QA',None)
    row['geometry'].pop('same_process_native_repeat_exact',None)
    return row


ref=load(CACHE/'pilot_reference.json.gz') if group==0 else None
for chunk in range(4*group,4*group+4):
    label=f'chunk_{chunk:02d}';path=OUT/f'chains/{label}/seeds.json'
    seeds=json.loads(path.read_text());records=load(CACHE/f'chains/{label}/native.json.gz')['records']
    pairs=load(CACHE/f'chains/{label}/paired.json.gz')
    proof=[]
    if ref is not None and chunk<2:
        for index,(r,p,s) in enumerate(zip(records,pairs,seeds['records'])):
            entry=64*chunk+index
            check=dict(entry=entry,native_geometry_exact=exact(canonical(r),canonical(ref['native']['records'][entry])),
                paired_exact=exact(p,ref['pairs'][entry]),
                RNG_exact=all(exact(s[k],ref['seeds']['records'][entry][k]) for k in ['run','event','roots','seeds','before','after']))
            assert all(v for k,v in check.items() if k!='entry'),check
            if r['geometry_QA'] is not None:assert exact(r['geometry_QA'],ref['native']['records'][entry]['geometry_QA'])
            proof.append(check)
    retained=[]
    for index,row in enumerate(seeds['records']):
        assert row['entry']==64*chunk+index
        row['each_detector_private_state_changed']={k:row['before'][k]!=row['after'][k] for k in row['seeds']}
        row['full_private_state_retained']=index in [0,63]
        if row['full_private_state_retained']:retained.append(row['entry'])
        else:
            row.pop('before');row.pop('after')
    seeds['transport_scope']='Full private state only first/last of each chunk; actual pilot-prefix exact comparisons made before discarding. Other parents retain explicit seeds and observed changed flags, not a claim of exact replay.'
    path.write_text(json.dumps(seeds,separators=(',',':'))+'\n')
    (OUT/f'chains/{label}/transport_proof.json').write_text(json.dumps(dict(passed=True,prefix_comparisons=proof,
        full_RNG_retained_entries=retained,raw_native_parent_N=len(records)),indent=2)+'\n')
