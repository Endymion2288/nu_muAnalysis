#!/usr/bin/env python3
"""Exactly compare consolidated station arrays with each source shard before cleanup."""
import argparse
import json
from pathlib import Path
import resource
import time

import numpy as np
from report_tracking_station import EVENT_KEYS, TRACK_KEYS
from extract_tracking_station import TRACK_FIELDS


def equal(left,right,label):
    assert np.array_equal(left,right,equal_nan=left.dtype.kind in 'fc'),label


def main():
    start=time.monotonic();p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--combined',type=Path,required=True)
    p.add_argument('--previous-candidates',type=Path)
    p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    records=[r.split('\t') for r in args.manifest.read_text().splitlines()]
    audit=json.loads((args.combined/'source_audit.json').read_text())
    configurations=json.loads((args.combined/'effective_reco_configurations.json').read_text())
    metadata={(r['version'],r['index'],r['skip']):r for r in audit};rows=[];previous={};recovery_checked=0
    if args.previous_candidates:
        recovery_indices=sorted({int(r[0]) for r in records if r[1]=='new' and int(r[3])==1000})
        with np.load(args.previous_candidates) as f:
            assert f['track_fields'][6:].tolist()==TRACK_FIELDS[5:]
            indices=f['manifest_indices'];offsets=f['track_file_offsets'];source=f['tracks']
            for index in recovery_indices:
                j=np.flatnonzero(indices==index).item();previous[index]=source[offsets[j]:offsets[j+1]].copy()
        del source
        previous={i:{tuple(row[:4].astype(int)):row[6:] for row in values} for i,values in previous.items()}
    for version in ['old','new']:
        with np.load(args.combined/(version+'.npz')) as source:a={k:source[k] for k in source.files}
        keys=list(zip(a['run'].tolist(),a['eventID'].tolist()));lookup={key:i for i,key in enumerate(keys)}
        track_event=a['tracks'][:,0].astype(int)
        order=np.argsort(track_event,kind='stable');sorted_events=track_event[order]
        seen=np.zeros(len(keys),bool);seen_tracks=np.zeros(len(track_event),bool);all_ids=[]
        for r in records:
            if r[1]!=version:continue
            with np.load(r[5]) as f:
                event_indices=np.array([lookup[key] for key in zip(f['run'].tolist(),f['eventID'].tolist())],dtype=int)
                assert not seen[event_indices].any();seen[event_indices]=True
                for name in EVENT_KEYS:equal(a[name][event_indices],f[name],(r[0],version,name))
                t=f['tracks'].copy();t[:,0]=event_indices[t[:,0].astype(int)]
                local_order=np.lexsort((t[:,2],t[:,1],t[:,0]));t=t[local_order]
                positions=np.concatenate([order[np.searchsorted(sorted_events,i,'left'):np.searchsorted(sorted_events,i,'right')]
                                          for i in np.sort(event_indices)]) if len(event_indices) else np.array([],int)
                assert not seen_tracks[positions].any();seen_tracks[positions]=True
                equal(a['tracks'][positions],t,(r[0],version,'tracks'))
                for name in TRACK_KEYS[1:]:equal(a[name][positions],f[name][local_order],(r[0],version,name))
                if version=='new' and int(r[0]) in previous:
                    run_ids=f['run'];event_ids=f['eventID']
                    for row in f['tracks']:
                        event_index=int(row[0]);key=(int(run_ids[event_index]),int(event_ids[event_index]),int(row[1]),int(row[2]))
                        equal(row[5:],previous[int(r[0])][key],('previous production recovered long',key))
                        recovery_checked+=1
                if 'all_run' in f:all_ids.append(np.column_stack([f['all_run'],f['all_eventID']]))
                row=metadata[version,int(r[0]),int(r[4])]
                assert row['summary_bytes']==Path(r[5]).stat().st_size
                for name in ['performance','root_bytes']:
                    assert row[name]==json.loads(str(f[name+'_json']))
                assert row['host']==str(f['host'])
                assert configurations[row['effective_reco_key']]==str(f['effective_reco_json'])
                assert row['prior_cut_bits_verified']==bool(f['prior_cut_bits_verified'])
                assert row['official_long_matches_checked']==int(f['official_long_matches_checked'])
                assert row['events']==int(f['counts'][0,0])
                assert row['final_FBM']==f['counts'][:,-1].tolist()
                rows.append(dict(version=version,index=int(r[0]),skip=int(r[4]),source_path=row['source_path'],
                    bytes=row['summary_bytes'],truth_events=len(event_indices),tracks=len(t),exact=True))
        assert seen.all() and seen_tracks.all()
        if all_ids:
            ids=np.concatenate(all_ids);ids=ids[np.lexsort((ids[:,1],ids[:,0]))]
            equal(ids,np.column_stack([a['all_run'],a['all_eventID']]),(version,'all IDs'))
    result=dict(exact=True,shards=len(rows),source_bytes=sum(r['bytes'] for r in rows),rows=rows,
        previous_production_recovered_long_tracks_exact=recovery_checked,
        wall_s=time.monotonic()-start,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='rows'}))


if __name__=='__main__':main()
