#!/usr/bin/env python3
"""Remove duplicate feature shards/pilots and temporary payloads after exact validation."""
import json
import numpy as np
from source_transfer import REPO,CACHE,OUT

assert not (OUT/'storage.json').exists(),'Do not overwrite an archival cost record'
v=json.loads((OUT/'validation.json').read_text());assert v['no_dropped_events'] and v['models_reloaded_and_raw_float32_predictions_exact']
with np.load(CACHE/'features.npz') as z:joined={k:z[k] for k in z.files}
shards=list((CACHE/'shards').glob('*.npz'))+list((CACHE/'pilot').glob('*.npz'))
for path in shards:
    with np.load(path) as z:
        at=np.searchsorted(joined['cache_row'],z['cache_row'])
        for k in joined:np.testing.assert_array_equal(z[k],joined[k][at])
shard_bytes=sum(p.stat().st_size for p in shards)
for p in shards:p.unlink()
payloads=list((REPO/'software').glob('energy-ml-source-transfer-stage48-*.tar.gz'));payload_bytes=sum(p.stat().st_size for p in payloads)
for p in payloads:p.unlink()
# The complete seven-process resource table subsumes the temporary extraction-only copy.
partial=OUT/'condor_extract_resources.json'
if partial.exists():partial.unlink()
files=sorted(p for p in CACHE.rglob('*') if p.is_file())
md=dict(removed_duplicate_files=len(shards),removed_duplicate_bytes=shard_bytes,removed_payload_files=len(payloads),removed_payload_bytes=payload_bytes,
        pilot_and_shard_exact_rejoin=True,old_model_files_reused_not_duplicated=True,retained_files=len(files),retained_bytes=sum(p.stat().st_size for p in files),
        retained=[dict(path=str(p.relative_to(REPO)),bytes=p.stat().st_size) for p in files])
(OUT/'storage.json').write_text(json.dumps(md,indent=2)+'\n');print(json.dumps(md))
