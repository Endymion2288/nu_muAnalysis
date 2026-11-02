#!/usr/bin/env python3
"""Read only scalar raw charges/status from complete existing nominal PHYS files."""
import argparse
import csv
import json
import resource
import time
from pathlib import Path

import numpy as np
import uproot

from audited_features import REPO, SCINTILLATORS


def extract(batch, output, smoke=False):
    tick, cpu = time.perf_counter(), time.process_time()
    cfg = json.loads((REPO/'ml/configs/audited_features.json').read_text())
    manifest = list(csv.DictReader((REPO/'ml/configs/low_energy_files.tsv').open(),delimiter='\t'))
    rows = [r for r in manifest if r['family']=='nominal'][batch::6]
    if smoke: rows=rows[:1]
    with np.load(REPO/'ntuples/energy_ml_stage55/dataset.npz') as z:
        source=z['source']; events=z['eventID']; runs=z['run']; old=z['x'];names=json.loads(str(z['metadata_json']))['features']
    branches=['run','eventID']+[s+'_'+suffix for s in SCINTILLATORS for suffix in ['charge','raw_charge','status','baseline_rms']]+[f'Calo{i}_status' for i in range(4)]
    parts=[]; records=[]
    expected = {int(r['index']):int(r['expected_events']) for r in csv.DictReader((REPO/'ml/configs/files.tsv').open(),delimiter='\t')}
    for row in rows:
        start=time.perf_counter();take=np.flatnonzero(source==int(row['index']))
        with uproot.open(row['input']) as f:
            t=f['nt']; assert t.num_entries==expected[int(row['old_index'])]
            arr=t.arrays(branches,library='np'); requested=int(f.file.source.num_requested_bytes)
        assert np.all(arr['run']==int(row['run']))
        lookup={int(e):i for i,e in enumerate(arr['eventID'])};assert len(lookup)==len(arr['eventID'])
        order=np.array([lookup[int(e)] for e in events[take]])
        np.testing.assert_array_equal(arr['run'][order],runs[take])
        for s in SCINTILLATORS:
            v=arr[s+'_charge'][order].astype('float32');v[~np.isfinite(v)]=np.nan
            np.testing.assert_array_equal(v,old[take,names.index(s+'_charge')])
        part=dict(row=take,raw_charge=np.column_stack([arr[s+'_raw_charge'][order] for s in SCINTILLATORS]),
                  status=np.column_stack([arr[s+'_status'][order] for s in SCINTILLATORS]),
                  baseline_rms=np.column_stack([arr[s+'_baseline_rms'][order] for s in SCINTILLATORS]),
                  calo_status=np.column_stack([arr[f'Calo{i}_status'][order] for i in range(4)]))
        parts.append(part)
        records.append(dict(source=int(row['index']),run=int(row['run']),raw_N=len(arr['run']),selected_N=len(take),requested_bytes=requested,wall_s=time.perf_counter()-start))
    data={k:np.concatenate([p[k] for p in parts]) for k in parts[0]}
    md=dict(batch=batch,smoke=smoke,files=records,selected_N=len(data['row']),features_version=cfg['version'],
            raw_N=sum(r['raw_N'] for r in records),requested_bytes=sum(r['requested_bytes'] for r in records),
            wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    output.parent.mkdir(parents=True,exist_ok=True);assert not output.exists()
    np.savez_compressed(output,**data,metadata_json=np.array(json.dumps(md)))
    print(json.dumps(md),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--batch',type=int,required=True,choices=range(6));p.add_argument('--output',type=Path,required=True);p.add_argument('--smoke',action='store_true')
    a=p.parse_args();extract(a.batch,a.output,a.smoke)
