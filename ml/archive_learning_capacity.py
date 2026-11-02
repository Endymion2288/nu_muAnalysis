#!/usr/bin/env python3
"""Keep final models and compact summaries; remove duplicate fold predictions and payload."""
import json
import numpy as np
from learning_capacity import REPO,CACHE,OUT

assert not (OUT/'storage.json').exists(),'Do not overwrite an archive record'
v=json.loads((OUT/'validation.json').read_text());assert v['formal_fits']==9 and v['models_reloaded']
with np.load(CACHE/'predictions.npz') as z:joined={k:z[k] for k in z.files}
removed=[];bytes_removed=0
for f in range(3):
    path=REPO/f'ml/artifacts/stage50/formal/{f}/predictions.npz'
    with np.load(path) as z:
        md=json.loads(str(z['metadata_json']));rows=z['cache_row']
        for r in md['records']:np.testing.assert_array_equal(z[r['model']],joined[r['model']][rows])
    (path.parent/'metadata.json').write_text(json.dumps(md,indent=2)+'\n')
    bytes_removed+=path.stat().st_size;removed.append(str(path.relative_to(REPO)));path.unlink()
payload=REPO/'software/energy-ml-learning-capacity-stage50.tar.gz';payload_bytes=payload.stat().st_size;payload.unlink()
files=sorted([p for p in CACHE.rglob('*') if p.is_file()]+[p for p in (REPO/'ml/artifacts/stage50').rglob('*') if p.is_file()])
md=dict(removed_duplicate_prediction_files=removed,removed_duplicate_prediction_bytes=bytes_removed,removed_payload_bytes=payload_bytes,
        exact_fold_rejoin_before_deletion=True,retained_files=len(files),retained_bytes=sum(p.stat().st_size for p in files),
        retained=[dict(path=str(p.relative_to(REPO)),bytes=p.stat().st_size) for p in files])
(OUT/'storage.json').write_text(json.dumps(md,indent=2)+'\n');print(json.dumps(md))
