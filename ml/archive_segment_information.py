#!/usr/bin/env python3
"""Remove exact source/fold duplicates and payloads; retain reproducible compact QA."""
import json
import numpy as np
from segment_information import REPO,OUT,CACHE,configuration
cfg=configuration();assert not (OUT/'storage.json').exists(),'Do not overwrite archive record'
v=json.loads((OUT/'validation.json').read_text());assert v['formal_fits']==9 and v['full_feature_pilot_replay_exact_events']==40
with np.load(CACHE/'features.npz') as z:features={k:z[k] for k in z.files}
with np.load(CACHE/'predictions.npz') as z:pred={k:z[k] for k in z.files}
removed=[]
for index in cfg['indices']:
    p=CACHE/'shards'/f'{index}.npz'
    with np.load(p) as z:
        ids=z['cache_row']
        for key in features:np.testing.assert_array_equal(z[key],features[key][ids])
    removed.append(dict(path=str(p.relative_to(REPO)),bytes=p.stat().st_size));p.unlink()
for f in range(3):
    p=REPO/f'ml/artifacts/stage51/formal/{f}/predictions.npz'
    with np.load(p) as z:
        md=json.loads(str(z['metadata_json']));ids=z['cache_row']
        for name in cfg['candidates']:np.testing.assert_array_equal(z[name],pred[name][ids])
    (p.parent/'metadata.json').write_text(json.dumps(md,indent=2)+'\n');removed.append(dict(path=str(p.relative_to(REPO)),bytes=p.stat().st_size));p.unlink()
payloads=[]
for mode in ['extract','train']:
    p=REPO/f'software/energy-ml-segment-information-stage51-{mode}.tar.gz';payloads.append(dict(path=str(p.relative_to(REPO)),bytes=p.stat().st_size));p.unlink()
# Raw pilot vectors stay in the ignored cache for independent QA replay, not in Git.
p=OUT/'pilot.json';pilot=json.loads(p.read_text());(CACHE/'pilot.json').write_text(p.read_text())
summary={k:v for k,v in pilot.items() if k!='event_records'};summary['raw_replay_cache']='ntuples/energy_ml_stage51/pilot.json';summary['raw_vectors_committed']=False
p.write_text(json.dumps(summary,indent=2)+'\n')
files=sorted([p for p in CACHE.rglob('*') if p.is_file()]+[p for p in (REPO/'ml/artifacts/stage51').rglob('*') if p.is_file()])
md=dict(removed_duplicates=removed,removed_duplicate_bytes=sum(r['bytes'] for r in removed),removed_payloads=payloads,exact_rejoin_before_deletion=True,
    retained_files=len(files),retained_bytes=sum(p.stat().st_size for p in files),retained=[dict(path=str(p.relative_to(REPO)),bytes=p.stat().st_size) for p in files])
(OUT/'storage.json').write_text(json.dumps(md,indent=2)+'\n');print(json.dumps({k:v for k,v in md.items() if k not in ['removed_duplicates','retained']}))
