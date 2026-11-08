"""Scalar source accounting from retained metadata; filename ranges remain claims."""
import csv
import gzip
import json
import re
import resource
import shlex
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage169_energy_ml'
COUNTS = ['parent_N','full_parent_N','truth_superset_N','selected_N']


def write(name,value):
    (OUT/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def load():
    cpu,wall = time.process_time(),time.perf_counter()
    plan = json.loads((OUT/'protocol.json').read_text())
    frozen = json.loads((OUT/'inputs.json').read_text())
    paths=plan['inputs']
    original=json.loads((ROOT/paths['source_manifest']).read_text())
    headers=json.loads((ROOT/paths['actual_EVNT_headers']).read_text())
    with gzip.open(ROOT/paths['source_accounting'],'rt') as f:
        evidence=json.load(f)
    assert len(evidence)==len({r['index'] for r in evidence})==666
    assert {r['index'] for r in evidence}==set(frozen['completed_sources'])
    native={int(i):json.loads((ROOT/path).read_text()) for i,path in frozen['native_summaries'].items()}
    with (ROOT/paths['source_selected_table']).open() as f:
        table=list(csv.DictReader(f,delimiter='\t'))
    proof=json.loads((ROOT/paths['actual_log_bounds']).read_text())['sources']
    result=dict(plan=plan,frozen=frozen,original=original,headers={r['path']:r['N'] for r in headers['records']},
        evidence={r['index']:r for r in evidence},native=native,
        selected_table={int(r['index']):r for r in table},proof={r['index']:r for r in proof},
        totals=json.loads((ROOT/paths['stage130_totals']).read_text()))
    assert len(result['selected_table'])==len(table)==666
    result['load_resources']=dict(CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-wall,
        input_metadata_bytes=sum((ROOT/p).stat().st_size for p in frozen['files']),
        RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return result


def claim(source,n):
    match=re.fullmatch(r'(\d{5})-(\d{5})',source['segment']); assert match
    lo,hi=int(match[1])*1000,(int(match[2])+1)*1000
    assert 0<=lo<hi
    return dict(claim_start=lo,claim_stop_exclusive=hi,claim_requested_N=hi-lo,
        claim_available_N=max(0,min(hi,n)-lo),claim_clipped_at_EOF=hi>n,
        generator_N=n,filename_claim_only=True)


def source_row(index,data):
    source=data['original']['sources'][index]
    assert source['index']==index
    meta=data['evidence'][index]['metadata']
    qa,request=meta['source_qa.json'],meta['request_summary.json']
    assert qa['index']==index and request['source']==source
    assert qa['inherited_role']==source['inherited_role']
    values=dict(parent_N=request['parent_N'],full_parent_N=request['full_parent_N'],
                truth_superset_N=qa['truth_superset_N'],selected_N=qa['selected_N'])
    assert all(isinstance(v,int) and not isinstance(v,bool) for v in values.values())
    n=data['headers'][source['EVNT']]
    span=claim(source,n)
    table=data['selected_table'][index]
    link=meta.get('parentmap.json')
    linked=link['eventID_entry_incoming_exact_N'] if link else int(table['actual_EVNT_entry_matches'])
    row=dict(index=index,run=source['run'],component=source['component'],role=source['inherited_role'],
        EVNT=source['EVNT'],**values,**span,qa_parent_N=qa['parent_N'],linked_selected_N=linked,
        counts_nonnegative=all(v>=0 for v in values.values()),
        count_hierarchy=0<=values['selected_N']<=values['truth_superset_N']<=values['parent_N'],
        parent_full_equal=values['parent_N']==values['full_parent_N'],
        parent_qa_equal=values['parent_N']==qa['parent_N'],
        parent_claim_available_equal=values['parent_N']==span['claim_available_N'],
        selected_table_equal=values['selected_N']==int(table['selected_N']),
        selected_link_count_equal=linked==values['selected_N'],actual_log_bounds=False,
        native_scanned_N=None,native_available_equal=None,native_selected_equal=None)
    if index in data['proof']:
        proof=data['proof'][index]; native=data['native'][index]
        commands=[shlex.split(r['command']) for r in proof['boundary_logs']]
        assert all(c[1]==source['EVNT'] for c in commands)
        skips=[int(c[c.index('--skip')+1]) for c in commands]
        nums=[int(c[c.index('-n')+1]) for c in commands]
        assert skips[0]==proof['skip']==span['claim_start']
        assert skips[-1]+nums[-1]==proof['skip']+proof['count']==span['claim_stop_exclusive']
        assert native['index']==index and native['EVNT']==source['EVNT']
        assert native['skip']==proof['skip'] and native['requested_N']==proof['count']
        row.update(actual_log_bounds=True,native_scanned_N=native['scanned_N'],
                   native_available_equal=native['scanned_N']==span['claim_available_N'],
                   native_selected_equal=native['selected_records_N']==values['selected_N'])
    return row


def union_length(intervals):
    total=0;left=right=None
    for lo,hi in sorted((a,b) for a,b in intervals if a<b):
        if left is None:left,right=lo,hi
        elif lo>right:total+=right-left;left,right=lo,hi
        else:right=max(right,hi)
    return total+(right-left if left is not None else 0)


def aggregate(rows,keys):
    groups={}
    for r in rows:
        key=tuple(r[k] for k in keys)
        target=groups.setdefault(key,dict(zip(keys,key),sources=0,**{k:0 for k in COUNTS+['claim_requested_N','claim_available_N']}))
        target['sources']+=1
        for k in COUNTS+['claim_requested_N','claim_available_N']:target[k]+=r[k]
    return list(groups.values())


def table(name,rows):
    with (OUT/name).open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n')
        writer.writeheader();writer.writerows({k:'NA' if v is None else v for k,v in r.items()} for r in rows)
