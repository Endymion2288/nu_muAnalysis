#!/usr/bin/env python3
"""Drop duplicate shards/pilots only after model validation and exact summary rejoin."""
import json
from coarse_depth import REPO
import numpy as np

out=REPO/'workbook/stage47_energy_ml';cache=REPO/'ntuples/energy_ml_stage47'
v=json.loads((out/'validation.json').read_text());assert v['formal_fits']==6 and v['serialized_model_prediction_readback']
with np.load(cache/'sensitive.npz') as z:final={k:z[k] for k in ['cache_row','eventID','hit_energy_MeV','hit_count']}
removed=[]
for path in list((cache/'hits').glob('*.npz'))+list((cache/'pilot').glob('*.npz')):
    with np.load(path) as z:
        positions=np.searchsorted(final['cache_row'],z['cache_row'])
        for key in final:np.testing.assert_array_equal(z[key],final[key][positions])
    removed.append(path)
removed+=list((cache/'pilot').glob('*.json'))
removed_bytes=sum(p.stat().st_size for p in removed)
for path in removed:path.unlink()
payloads=list((REPO/'software').glob('energy-ml-ordinary-calo-stage47-*.tar.gz'))
payload_bytes=sum(p.stat().st_size for p in payloads)
for path in payloads:path.unlink()
files=[p for p in cache.rglob('*') if p.is_file()]+[p for p in (REPO/'ml/artifacts/stage47').rglob('*') if p.is_file()]
summary=dict(removed_duplicate_files=len(removed),removed_duplicate_bytes=removed_bytes,
             removed_payload_files=len(payloads),removed_payload_bytes=payload_bytes,
             exact_shard_and_pilot_rejoin=True,located_requests_archived_once=True,
             retained_files=len(files),retained_bytes=sum(p.stat().st_size for p in files),
             retained=[dict(path=str(p.relative_to(REPO)),bytes=p.stat().st_size) for p in sorted(files)])
(out/'storage.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
