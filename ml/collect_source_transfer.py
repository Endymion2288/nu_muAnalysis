#!/usr/bin/env python3
"""Rejoin every frozen identity, require exact pilot agreement, collect I/O once."""
import json
import time
import numpy as np
from source_transfer import REPO,CACHE,OUT,configuration
from train_bdt import write_table

cfg=configuration();tick=time.perf_counter();parts=[];records=[]
with np.load(CACHE/'selection.npz') as z:selection={k:z[k] for k in z.files}
for i in cfg['indices']:
    with np.load(CACHE/f'shards/{i}.npz') as z:part={k:z[k] for k in z.files}
    md=json.loads(str(part.pop('metadata_json')));mask=selection['manifest_index']==i
    assert not md['pilot'] and md['index']==i and md['identity_failures']==0
    for k in ['cache_row','run','eventID']:np.testing.assert_array_equal(part[k],selection[k][mask])
    assert part['local'].shape==(mask.sum(),22);parts.append(part);records.append(md)
order=np.argsort(np.concatenate([p['cache_row'] for p in parts]))
joined={k:np.concatenate([p[k] for p in parts])[order] for k in parts[0]}
for k in ['cache_row','run','eventID']:np.testing.assert_array_equal(joined[k],selection[k])
for i in [1,47]:
    with np.load(CACHE/f'pilot/{i}.npz') as z:
        at=np.searchsorted(joined['cache_row'],z['cache_row'])
        for k in joined:np.testing.assert_array_equal(z[k],joined[k][at])
np.savez_compressed(CACHE/'features.npz',**joined)
with np.load(CACHE/'features.npz') as z:
    for k in joined:np.testing.assert_array_equal(z[k],joined[k])
write_table(OUT/'extraction_resources.tsv',records)
md=dict(events=len(joined['cache_row']),sources=len(records),identity_failures=0,pilot_exact_rejoin=True,original_F6_fingerprint_all_verified=True,
        raw_entries=sum(r['raw_entries'] for r in records),decoded_entries=sum(r['decoded_entries'] for r in records),
        bytes_read=sum(r['bytes_read'] for r in records),wall_s=sum(r['wall_s'] for r in records),cpu_s=sum(r['cpu_s'] for r in records),
        peak_rss_MiB=max(r['peak_rss_MiB'] for r in records),total_points=sum(r['points_N'] for r in records),
        lead_index_nonzero_N=sum(r['lead_index_nonzero_N'] for r in records),nonfinite_points=sum(r['nonfinite_points'] for r in records),
        max_layer_distance_mm=max(r['max_layer_distance_mm'] for r in records),max_local_dz_mm=max(r['max_local_dz_mm'] for r in records),
        axis_missing_N=np.sum([r['axis_missing_N'] for r in records],axis=0).tolist(),
        local_missing_N=(~np.isfinite(joined['local'])).sum(axis=0).tolist(),collection_wall_s=time.perf_counter()-tick)
assert md['events']==4000 and md['sources']==60
(OUT/'extraction.json').write_text(json.dumps(md,indent=2)+'\n');print(json.dumps(md))
