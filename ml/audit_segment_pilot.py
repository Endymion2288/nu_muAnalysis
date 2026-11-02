#!/usr/bin/env python3
"""Identity-fixed 40-event schema/physics pilot; no energy residuals or fits."""
import json
import resource
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
import awkward as ak
import numpy as np
import uproot
from calonu_inputs import manifest
from local_activity import TRACKS

repo=Path(__file__).resolve().parents[1];out=repo/'workbook/stage51_energy_ml';out.mkdir(parents=True,exist_ok=True)
assert not (out/'pilot.json').exists(),'Do not silently repeat completed pilot'
with np.load(repo/'ntuples/energy_ml_stage42/development.npz') as z:d={k:z[k] for k in ['run','eventID','component','manifest_index']}
chosen=[]
for comp,n in [('pi',7),('k',7),('charm',6)]:
    indices=sorted(set(map(int,d['manifest_index'][d['component']==comp])))
    for index in [indices[0],indices[-1]]:
        ids=np.flatnonzero(d['manifest_index']==index);chosen.extend(sorted(ids,key=lambda i:(int(d['run'][i]),int(d['eventID'][i])))[:n])
assert len(chosen)==40
(out/'pilot_protocol.json').write_text(json.dumps(dict(frozen_utc=datetime.now(timezone.utc).isoformat(),starting_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
    selection='first and last manifest index in each component; first run/eventID; 7 pi, 7 k, 6 charm per source; schema/physics only',
    cache_rows=list(map(int,chosen)),energy_labels_used=False),indent=2)+'\n')
fields=['x','y','z','px','py','pz','Chi2','nDoF'];centers=np.array([-1860.15,47.4,1237.4,2427.4]);files=manifest(repo)
tick,cpu=time.perf_counter(),time.process_time();records=[];events=[]
for index in sorted(set(map(int,d['manifest_index'][chosen]))):
    rows=np.array([i for i in chosen if d['manifest_index'][i]==index]);start=time.perf_counter()
    with uproot.open(files[index]['input']) as f:
        t=f['nt'];keys=t.arrays(['run','eventID'],library='np');lookup={int(e):j for j,e in enumerate(keys['eventID'])};entries=np.array([lookup[int(e)] for e in d['eventID'][rows]])
        np.testing.assert_array_equal(keys['run'][entries],d['run'][rows]);lo,hi=int(entries.min()),int(entries.max())+1
        cols=['run','eventID']+[prefix+s for prefix in ['TrackSegment_','GhostBustedTrackSegment_'] for s in fields]+['TrackSegments','GhostBustedTrackSegments']+['Track_'+s for s in TRACKS]
        present=[c for c in cols if c in t];arr=t.arrays(present,entry_start=lo,entry_stop=hi)[entries-lo]
        rec=dict(index=index,N=len(rows),input=files[index]['input'],entry_range=[lo,hi],missing_columns=sorted(set(cols)-set(present)),bytes_read=int(f.file.source.num_requested_bytes),wall_s=time.perf_counter()-start)
    for j,row in enumerate(ak.to_list(arr)):
        event=dict(cache_row=int(rows[j]),index=index,run=row['run'],eventID=row['eventID'],collections={})
        for prefix,count in [('TrackSegment_','TrackSegments'),('GhostBustedTrackSegment_','GhostBustedTrackSegments')]:
            if prefix+'x' not in row:continue
            assert all(len(row[prefix+s])==row[count] for s in fields)
            a=np.array([row[prefix+s] for s in fields],float).T
            dist=abs(a[:,2,None]-centers);st=dist.argmin(axis=1)
            event['collections'][prefix]=dict(N=len(a),station_N=np.bincount(st,minlength=4).tolist(),max_station_distance_mm=float(dist.min(axis=1).max()) if len(a) else None,
                momentum_magnitude_MeV=np.linalg.norm(a[:,3:6],axis=1).tolist(),unique_z_mm=np.unique(a[:,2]).tolist(),nonfinite_rows=int((~np.isfinite(a).all(axis=1)).sum()),
                nonpositive_pz_N=int((a[:,5]<=0).sum()),nonpositive_DoF_N=int((a[:,7]<=0).sum()),exact_duplicate_N=len(a)-len(np.unique(a,axis=0)),raw=a.tolist())
        event['tracks']={c:row[c] for c in row if c.startswith('Track_')};events.append(event)
    records.append(rec)
md=dict(events=40,sources=6,records=records,event_records=events,wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
(out/'pilot.json').write_text(json.dumps(md,indent=2)+'\n')
print(json.dumps({k:v for k,v in md.items() if k!='event_records'}))
for prefix in ['TrackSegment_','GhostBustedTrackSegment_']:
    es=[e['collections'][prefix] for e in events if prefix in e['collections']]
    print(json.dumps(dict(collection=prefix,events=len(es),segments=sum(e['N'] for e in es),station_N=np.sum([e['station_N'] for e in es],axis=0).tolist(),nonempty=sum(e['N']>0 for e in es),nonfinite_rows=sum(e['nonfinite_rows'] for e in es),exact_duplicate_N=sum(e['exact_duplicate_N'] for e in es))))
