#!/usr/bin/env python3
"""Rejoin every requested HITS event; never replace a failed read with zero."""
import json
import time
from pathlib import Path
import numpy as np
from train_bdt import write_table

repo=Path(__file__).resolve().parents[1]; out=repo/'workbook/stage42_energy_ml'; cache=repo/'ntuples/energy_ml_stage42'
cfg=json.loads((repo/'ml/configs/calonu_information.json').read_text()); tick=time.perf_counter()
with np.load(cache/'development.npz') as z: d={k:z[k] for k in z.files}
sets=[]; resources=[]; schemas=[]
for i in cfg['indices']:
    with np.load(cache/f'hits/{i}.npz') as z: s={k:z[k] for k in z.files}
    m=json.loads(str(s['metadata_json'])); rows=s['cache_row']; expected=np.flatnonzero(d['manifest_index']==i)
    np.testing.assert_array_equal(rows,expected); np.testing.assert_array_equal(s['eventID'],d['eventID'][rows])
    assert m['events']==len(expected) and m['index']==i and m['channel_hit_ids']==[9,1,11,3]
    sets.append(s); schemas += m.pop('schemas')
    resources.append(m)
order=np.argsort(np.concatenate([s['cache_row'] for s in sets])); joined={}
for key in ['cache_row','eventID','hit_energy_MeV','hit_count']:
    joined[key]=np.concatenate([s[key] for s in sets])[order]
np.testing.assert_array_equal(joined['cache_row'],np.flatnonzero(d['selected']))
assert len(np.unique(joined['cache_row']))==len(joined['cache_row'])
metadata=dict(events=len(joined['cache_row']),sources=len(sets),identity_failures=0,resources=resources,wall_s=time.perf_counter()-tick)
np.savez_compressed(cache/'sensitive.npz',**joined,metadata_json=np.array(json.dumps(metadata)))
with np.load(cache/'sensitive.npz') as z:
    for k,v in joined.items(): np.testing.assert_array_equal(z[k],v)
write_table(out/'HITS_resources.tsv',resources)
(out/'HITS_schema_checks.json').write_text(json.dumps(schemas,indent=2)+'\n')
(out/'HITS_collection.json').write_text(json.dumps(metadata,indent=2)+'\n')
print(json.dumps({k:v for k,v in metadata.items() if k!='resources'}))
