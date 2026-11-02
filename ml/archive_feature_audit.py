#!/usr/bin/env python3
"""Validate scalar supplements before removing duplicated transport/shards."""
import json
import re
from pathlib import Path

import numpy as np

from audited_features import REPO
from train_bdt import write_table

out=REPO/'workbook/stage56_energy_ml';cache=REPO/'ntuples/energy_ml_stage56'
assert json.loads((out/'validation.json').read_text())['formal_fits']==3
with np.load(cache/'readout.npz') as z:d={k:z[k] for k in z.files if k!='metadata_json'}
removed=[]
for i in range(6):
    path=cache/f'shards/{i}.npz'
    with np.load(path) as z:
        take=np.searchsorted(d['row'],z['row'])
        for k in z.files:
            if k!='metadata_json':np.testing.assert_array_equal(z[k],d[k][take])
    removed.append(path)
pilot=cache/'pilot.npz'
with np.load(pilot) as z:
    take=np.searchsorted(d['row'],z['row'])
    for k in z.files:
        if k!='metadata_json':np.testing.assert_array_equal(z[k],d[k][take])
    pilot_metadata=json.loads(str(z['metadata_json']))
(out/'readout_pilot.json').write_text(json.dumps(pilot_metadata,indent=2)+'\n');removed.append(pilot)
sub=json.loads((out/'submissions.json').read_text());spool=Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage56/logs')
records=[]
for phase,count in [('read',6),('training',1)]:
    cluster=sub[phase]['cluster'];mode='train' if phase=='training' else 'read'
    for proc in range(count):
        stderr=(spool/f'{mode}.{cluster}.{proc}.err').read_text()
        m=re.search(r'(read|train) wall_s=([\d.]+) user_s=([\d.]+) system_s=([\d.]+) rss_KiB=(\d+)',stderr);assert m
        records.append(dict(phase=mode,cluster=cluster,proc=proc,wall_s=float(m[2]),user_s=float(m[3]),system_s=float(m[4]),peak_rss_KiB=int(m[5])))
write_table(out/'pipeline_resources.tsv',records)
for path in [cache/'models.tar.gz',REPO/'software/energy-ml-feature-audit-stage56.tar.gz']:
    if path.exists():removed.append(path)
removed_bytes=sum(p.stat().st_size for p in removed)
for p in removed:p.unlink()
final=json.loads((out/'condor_resources.json').read_text());lookup={(r['ClusterId'],r['ProcId']):r for r in final}
early=out/'read_condor_resources.json'
for r in json.loads(early.read_text()):
    now=lookup[(r['ClusterId'],r['ProcId'])]
    for k in ['ExitCode','RemoteUserCpu','RemoteSysCpu','RemoteWallClockTime']:assert r.get(k)==now.get(k)
early.unlink()
paths=[p for root in [cache,REPO/'ml/artifacts/stage56'] for p in root.rglob('*') if p.is_file()]
result=dict(source_shards_verified=6,pilot_verified=True,duplicate_bytes_removed=removed_bytes,
            retained_bytes=sum(p.stat().st_size for p in paths),retained_files=len(paths),files=[dict(path=str(p.relative_to(REPO)),bytes=p.stat().st_size) for p in paths])
(out/'storage.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='files'}))
