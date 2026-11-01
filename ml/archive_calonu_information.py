#!/usr/bin/env python3
"""Remove duplicate extraction shards only after exact summary rejoin/readback."""
import json
import tarfile
from pathlib import Path
import numpy as np

repo=Path(__file__).resolve().parents[1]; out=repo/'workbook/stage42_energy_ml'; cache=repo/'ntuples/energy_ml_stage42'
validation=json.loads((out/'final_validation.json').read_text()); assert validation['valid']
with np.load(cache/'sensitive.npz') as z: final={k:z[k] for k in ['cache_row','eventID','hit_energy_MeV','hit_count']}
removed=[]; before=0
for path in sorted((cache/'hits').glob('*.npz')):
    with np.load(path) as z:
        pos=np.searchsorted(final['cache_row'],z['cache_row'])
        for k in final: np.testing.assert_array_equal(final[k][pos],z[k])
    before+=path.stat().st_size; removed.append(path)
# Retain original compact requests as provenance, compressed once, without duplicating the HITS arrays.
archive=cache/'requests.tar.gz'
requests=sorted((cache/'requests').glob('*.json'))
with tarfile.open(archive,'w:gz') as tar:
    for path in requests: tar.add(path,arcname=path.name)
with tarfile.open(archive) as tar:
    assert len(tar.getmembers())==len(requests)
    for path in requests: assert tar.extractfile(path.name).read()==path.read_bytes()
for path in requests: before+=path.stat().st_size; removed.append(path)
for pattern in ['*smoke.json','*smoke.npz','located_*.json']:
    for path in cache.glob(pattern): before+=path.stat().st_size; removed.append(path)
for path in removed: path.unlink()
files=[dict(path=str(p.relative_to(repo)),bytes=p.stat().st_size) for p in sorted(cache.glob('*')) if p.is_file()]
summary=dict(removed_duplicate_files=len(removed),removed_bytes=before,retained=files,
             retained_bytes=sum(r['bytes'] for r in files),exact_HITS_rejoin=True,requests_archive_readback=True)
(out/'storage.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
