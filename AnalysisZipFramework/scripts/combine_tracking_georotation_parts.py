#!/usr/bin/env python3
"""Combine disjoint RDO slices after validating complete ranges and identical physics settings."""
import argparse
import json
from pathlib import Path
import re

import numpy as np
import uproot


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--audit',type=Path,required=True)
    p.add_argument('--events',type=int,required=True)
    p.add_argument('--slice-events',type=int,default=1000)
    p.add_argument('--rdo',required=True)
    args=p.parse_args()
    assert args.events%args.slice_events==0
    n=args.events//args.slice_events
    with uproot.open(args.rdo) as f:
        input_ids=f['CollectionTree']['xAOD::EventAuxInfo_v3_EventInfoAuxDyn.mcEventNumber'].array(library='np')
    assert len(input_ids)==args.events and len(np.unique(input_ids))==args.events
    parts=[];audit=[];performance={};root_bytes={}
    for i in range(n):
        path=args.directory/f'part{i}.npz'
        with np.load(path) as source:part={k:source[k] for k in source.files}
        assert np.all(part['counts'][:,0]==args.slice_events)
        assert int(part['manifest_index'])==53
        expected_ids=input_ids[i*args.slice_events:(i+1)*args.slice_events]
        assert np.isin(part['event_eventID'],expected_ids).all()
        assert np.isin(part['tracks'][:,1],expected_ids).all()
        for key in ('effective_reco_json','software_provenance_json','track_fields','pair_fields',
                    'fiducial_index','tracking_index','nontrack_columns','manifest_index'):
            if parts:assert np.array_equal(part[key],parts[0][key]),key
        for key in ('tracks','pairs'):
            ids=part[key][:,:2]
            for previous in parts:
                old=previous[key][:,:2]
                assert not np.intersect1d(ids[:,0].astype(np.int64)*1000000000+ids[:,1].astype(np.int64),
                                         old[:,0].astype(np.int64)*1000000000+old[:,1].astype(np.int64)).size
        perf=json.loads(str(part['performance_json']))
        for step,line in perf.items():
            row=performance.setdefault(step,{})
            for key,value in re.findall(r'(\w+)=([0-9.]+)',line):
                v=float(value);row[key]=max(row.get(key,0),v) if key=='max_rss_kib' else row.get(key,0)+v
        sizes=json.loads(str(part['root_file_bytes_json']))
        for key,value in sizes.items():root_bytes[key]=root_bytes.get(key,0)+value
        audit.append(dict(part=i,input_skip=i*args.slice_events,input_events=args.slice_events,
            input_first_event=int(expected_ids[0]),input_last_event=int(expected_ids[-1]),
            events=int(part['counts'][0,0]),truth=int(part['counts'][0,6]),final=part['counts'][:,-1].tolist(),
            raw_tracks=part['raw_counts'].tolist(),nonfinite_raw_chi2=part['nonfinite_raw_chi2'].tolist(),
            host=str(part['host']),performance=perf,root_file_bytes=sizes,summary_bytes=path.stat().st_size))
        parts.append(part)
    sums=('counts overlaps nonfinite_leading_quality energy_den energy_pass radius_den radius_pass z_den z_pass '
          'raw_counts raw_long nonfinite_raw_chi2 truth_matches_checked measurement_length_mismatches').split()
    output={k:parts[0][k] for k in ('fiducial_index','tracking_index','nontrack_columns',
                                   'existing_merge_verified','manifest_index','track_fields','pair_fields',
                                   'effective_reco_json','software_provenance_json')}
    output.update({k:sum(part[k] for part in parts) for k in sums})
    for key in parts[0]:
        if key.startswith('event_') or key in ('tracks','pairs','migrations'):
            output[key]=np.concatenate([part[key] for part in parts])
    ids=output['event_run'].astype(np.int64)*1000000000+output['event_eventID'].astype(np.int64)
    assert len(np.unique(ids))==len(ids)
    order=np.argsort(ids)
    for key in output:
        if key.startswith('event_'):output[key]=output[key][order]
    output['performance_json']=json.dumps({step:step+' '+ ' '.join(f'{k}={v:.2f}' for k,v in row.items())
                                            for step,row in performance.items()})
    output['root_file_bytes_json']=json.dumps(root_bytes)
    output['host']=';'.join(sorted({str(part['host']) for part in parts}))
    output['split_job_metadata_json']=json.dumps(audit)
    np.savez_compressed(args.output,**output)
    with np.load(args.output) as saved:
        for key,value in output.items():
            if isinstance(value,np.ndarray):
                assert np.array_equal(value,saved[key],equal_nan=value.dtype.kind in 'fc'),key
            else:
                assert str(value)==str(saved[key]),key
    result=dict(manifest_index=53,range_convention='[input_skip,input_skip+input_events)',
                original_same_input_failures=[9717383,9717416],recovery_cluster=9717429,
                input_events=args.events,parts=audit,output_bytes=args.output.stat().st_size,
                input_rdo=args.rdo,input_event_ids_unique=True,
                validation='all disjoint slices complete; same software/config; no event discarded; exact NPZ readback')
    args.audit.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(events=int(output['counts'][0,0]),truth=int(output['counts'][0,6]),
                          final=output['counts'][:,-1].tolist(),output_bytes=args.output.stat().st_size)))


if __name__=='__main__':
    main()
