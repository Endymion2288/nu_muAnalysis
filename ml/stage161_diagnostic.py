"""Condor-only independent scalar audit of existing pilot records; no ROOT input."""
import csv
import gzip
import json
import math
import struct
from collections import defaultdict
from pathlib import Path
OUT=Path('workbook/stage161_energy_ml');CACHE=Path('ntuples/energy_ml_stage161')
def read(name):
    with gzip.open(CACHE/name,'rt') as stream:return json.load(stream)
raw=read('pilot_raw.json.gz');native=read('pilot_native.json.gz');old=read('pilot3_raw.json.gz')
assert old==raw
rows=[]
for n,r in zip(native,raw):
    assert (n['PHYS_entry'],n['run'],n['event'])==(r['PHYS_entry'],r['run'],r['event'])
    primary=defaultdict(list)
    for w in r['waves']:
        assert w['status']==0 or w['localtime_ns'] is None
        if not w['secondary']:primary[w['channel']].append(w)
    for channel,kind,compact,id32 in n['cable_mapping']:
        if int(channel) not in primary:continue
        assert len(primary[int(channel)])==1
        w=primary[int(channel)][0]
        rows.append(dict(PHYS_entry=n['PHYS_entry'],event=n['event'],channel=int(channel),kind=kind,
            detector=w['detector'],stored_id32=w['id32'],stored_hex=hex(w['id32']),map_id32=int(id32),
            map_hex=hex(int(id32)),map_compact=compact,equal=w['id32']==int(id32),status=w['status']))
with (OUT/'identity_diagnostic.tsv').open('w') as stream:
    writer=csv.DictWriter(stream,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n');writer.writeheader();writer.writerows(rows)
with (OUT/'pilot_raw_comparison.tsv').open() as stream:comparisons=list(csv.DictReader(stream,delimiter='\t'))
exact=0
for r in comparisons:
    value=float(r['native']);target=float(r['PHYS']);scalar=struct.unpack('f',struct.pack('f',value))[0]
    assert scalar==target and r['exact_float32']=='True';exact+=1
summary=dict(passed=True,N=len(raw),old_raw4_exact=True,independent_float32_checks=exact,
    mapped_rows=len(rows),identifier_equal_N=sum(r['equal'] for r in rows),
    identifiers=[dict(channel=c,kind=rs[0]['kind'],stored=sorted({r['stored_id32'] for r in rs}),
        current=sorted({r['map_id32'] for r in rs}),equal_N=sum(r['equal'] for r in rs),N=len(rs))
        for c,rs in sorted((c,[r for r in rows if r['channel']==c]) for c in {r['channel'] for r in rows})],
    ROOT_reads=0,new_parents=0,energy_fits=0,gate_changed=False)
(OUT/'identity_diagnostic_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(summary)
