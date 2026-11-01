#!/usr/bin/env python3
"""Require every requested event; archive located entries once and retain compact sums."""
import io
import json
import tarfile
import time
from pathlib import Path
import numpy as np
from coarse_depth import REPO,load_inputs
from train_bdt import write_table

tick=time.perf_counter();cfg=json.loads((REPO/'ml/configs/ordinary_calo_information.json').read_text())
rows,d,x=load_inputs();cache=REPO/'ntuples/energy_ml_stage47';out=REPO/'workbook/stage47_energy_ml'
sets=[];resources=[];schemas=[];located=[]
with tarfile.open(REPO/'ntuples/energy_ml_stage42/requests.tar.gz') as original:
    for i in cfg['indices']:
        with np.load(cache/f'hits/{i}.npz') as z: part={k:z[k] for k in z.files}
        md=json.loads(str(part['metadata_json']));expected=rows[d['manifest_index']==i]
        np.testing.assert_array_equal(part['cache_row'],expected)
        np.testing.assert_array_equal(part['eventID'],d['eventID'][d['manifest_index']==i])
        assert md['events']==len(expected) and md['index']==i and md['channel_hit_ids']==cfg['hit_ids']
        assert np.isfinite(part['hit_energy_MeV']).all() and (part['hit_energy_MeV']>=0).all()
        schemas+=md.pop('schemas');resources.append(md);sets.append(part)
        request=json.load(original.extractfile(f'request_{i}.json'))
        cases=json.loads(str(part['cases_json']));assert len(cases)==len(request['cases'])
        for new,old in zip(cases,request['cases']):
            for key,value in old.items():assert new[key]==value
        request.update(cases=cases,locate_wall_s=md['locate_wall_s'],locate_bytes_read=md['phys_bytes_read'])
        located.append((f'request_{i}.json',json.dumps(request).encode()))
order=np.argsort(np.concatenate([p['cache_row'] for p in sets]))
joined={key:np.concatenate([p[key] for p in sets])[order] for key in ['cache_row','eventID','hit_energy_MeV','hit_count']}
np.testing.assert_array_equal(joined['cache_row'],rows)
for key in ['run','group','fold']:joined[key]=d[key]
for i in [0,46]:
    with np.load(cache/f'pilot/{i}.npz') as z:
        positions=np.searchsorted(rows,z['cache_row'])
        for key in ['eventID','hit_energy_MeV','hit_count']:np.testing.assert_array_equal(joined[key][positions],z[key])
metadata=dict(events=len(rows),sources=len(sets),hit_ids=cfg['hit_ids'],identity_failures=0,
              module_row_pairs=cfg['module_row_pairs'],energy_definition='production-corrected sensitive deposit, MeV, all particles',
              hits_files=sum(m['files'] for m in resources),hits_bytes_read=sum(m['bytes_read'] for m in resources),
              phys_bytes_read=sum(m['phys_bytes_read'] for m in resources),
              hits_wall_s=sum(m['wall_s'] for m in resources),locate_wall_s=sum(m['locate_wall_s'] for m in resources),
              hits_cpu_s=sum(m['cpu_s'] for m in resources),peak_rss_MiB=max(m['peak_rss_MiB'] for m in resources),
              pilot_exact_rejoin=True,wall_s=time.perf_counter()-tick)
np.savez_compressed(cache/'sensitive.npz',**joined,metadata_json=np.array(json.dumps(metadata)))
with np.load(cache/'sensitive.npz') as z:
    for key in joined:np.testing.assert_array_equal(z[key],joined[key])
with tarfile.open(cache/'located_requests.tar.gz','w:gz') as t:
    for name,data in located:
        info=tarfile.TarInfo(name);info.size=len(data);t.addfile(info,io.BytesIO(data))
with tarfile.open(cache/'located_requests.tar.gz') as t:
    for name,data in located:assert t.extractfile(name).read()==data
unique={}
for s in schemas:
    key=(s['branch'],s['loaded'],tuple(s['saved']))
    unique.setdefault(key,set()).add(s['file'])
schema_summary=[dict(branch=k[0],loaded=k[1],saved=list(k[2]),files=len(v)) for k,v in unique.items()]
write_table(out/'HITS_resources.tsv',resources)
(out/'schema_checks.json').write_text(json.dumps(schema_summary,indent=2)+'\n')
(out/'extraction.json').write_text(json.dumps(metadata,indent=2)+'\n');print(json.dumps(metadata))
