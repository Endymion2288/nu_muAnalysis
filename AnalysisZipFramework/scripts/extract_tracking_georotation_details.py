#!/usr/bin/env python3
"""Validate targeted reruns against full-production candidates and retain spatial diagnostics."""
import argparse
import gzip
import json
from pathlib import Path

import awkward as ak
import numpy as np
import uproot

from compare_tracking import MODES, extract, raw_nontrack_check
from extract_tracking_georotation import TRACK_FIELDS


def normalize(raw):
    # Only Acts track/t_* coordinates rotate. Detector spacepoints and SiHit truth
    # remain in the original frame; scintillator X is stored as internal z'.
    for x, z in [('Track_x0', 'Track_z0'), ('Track_px0', 'Track_pz0'),
                 ('Track_x1', 'Track_z1'), ('Track_px1', 'Track_pz1'),
                 ('Track_x_atMaxRadius', 'Track_z_atMaxRadius'), ('t_px', 't_pz'),
                 ('t_prodVtx_x', 't_prodVtx_z'), ('t_decayVtx_x', 't_decayVtx_z')]:
        raw[x], raw[z] = [-v for v in raw[z]], raw[x]
    for key in raw:
        if key.startswith('Track_X_at'):
            raw[key] = [-v for v in raw[key]]
    return raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--run', type=int, required=True)
    parser.add_argument('--event', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--station-reference',action='store_true')
    args = parser.parse_args()
    key = (args.run, args.event)
    paths = [Path(mode+'.root') for mode in MODES]
    assert raw_nontrack_check(paths) == 17
    with gzip.open('detailed_tracks.jsonl.gz', 'rt') as source:
        detail = next(r for r in map(json.loads, source) if (r['run'],r['event']) == key)
    with gzip.open('raw_tracks.jsonl.gz', 'rt') as source:
        compact = next(r for r in map(json.loads, source) if tuple(r[:2]) == key)
    with np.load(args.reference) as source:
        runkey,eventkey=('run','eventID') if args.station_reference else ('event_run','event_eventID')
        positions = np.flatnonzero((source[runkey]==args.run)&(source[eventkey]==args.event))
        event_index = positions.item() if len(positions) else None
        expected = source['event_cut_bits'][event_index] if event_index is not None else np.zeros(3,dtype=np.uint16)
        reference = source['tracks'][source['tracks'][:,0]==event_index] if args.station_reference else source['tracks'][(source['tracks'][:,0]==args.run)&(source['tracks'][:,1]==args.event)]
        output = dict(run=args.run, event=args.event, expected_bits=expected.tolist(), modes={},
                      measurements=detail['tracks'], raw_truth=detail['tracks'],
                      production_verified=True, manifest_index=int(source['manifest_index']))
        output['reference_truth_fiducial']=event_index is not None
        for m, (mode,path) in enumerate(zip(MODES,paths)):
            current = np.asarray([t['values'] for t in compact[2][m]])
            if args.station_reference:
                from extract_tracking_station import SCALARS
                previous=reference[reference[:,1]==m,5:]
                long_current=np.asarray([v for v in current if v[12]]).reshape(previous.shape)
                assert np.array_equal(long_current,previous,equal_nan=True),(key,mode,'long candidates')
                primary=source['primary'][event_index]
                matched=(current[:,13]==primary[0])&(current[:,14]==primary[1])&(current[:,15]>=.7*current[:,9]) if len(current) and primary[2]==1 else np.zeros(len(current),bool)
                quality=(current[:,10]>=7)&(current[:,8]>=9)&np.isfinite(current[:,7])&(current[:,7]<15*current[:,8]) if len(current) else matched
                counts=[int(matched.sum()),int((matched&(current[:,12]>0)).sum()),int((matched&(current[:,12]>0)&quality).sum())] if len(current) else [0,0,0]
                assert counts==source['raw_primary_counts'][event_index,m].tolist(),(key,mode,'raw primary counts')
                output['long_candidates_verified']=True
                output['raw_primary_counts_verified']=True
                output['raw_all_candidate_values_verified']=False
            else:
                previous = reference[reference[:,2]==m,6:]
                assert np.array_equal(current.reshape(previous.shape),previous,equal_nan=True), (key,mode,'raw candidates')
            values, cumulative = extract(path,args.repo,rotated=True)
            i = np.flatnonzero((values['run']==args.run)&(values['eventID']==args.event)).item()
            bits = sum(int(v)<<j for j,v in enumerate(cumulative[i,7:]))
            assert bits == expected[m], (key,mode,bits,expected[m])
            if event_index is not None:
                for column in ('LeadTrack_Idx','LeadTrack_pz0','LeadTrack_Chi2_NDF','LeadTrack_r_atMaxRadius',
                               'LeadTrack_rIFT','LeadTrack_Theta','Lead_Track_Y_atTrig'):
                    previous_value=source['event_scalars'][event_index,m,SCALARS.index(column)] if args.station_reference else source['event_'+column][event_index,m]
                    assert np.isclose(values[column][i],previous_value,rtol=0,atol=0,equal_nan=True),column
            with uproot.open(path) as f:
                tree = f['nt']
                ids = tree.arrays(['run','eventID'],library='np')
                entry = np.flatnonzero((ids['run']==args.run)&(ids['eventID']==args.event)).item()
                columns = [k for k in tree.keys() if k.startswith(('Track_','SpacePoint_','truth_','t_'))]
                arrays = tree.arrays(columns,entry_start=entry,entry_stop=entry+1,library='ak')
                raw = normalize({k:ak.to_list(arrays[k][0]) for k in columns})
            output['modes'][mode] = dict(raw=raw,scalars={k:float(v[i]) for k,v in values.items()
                                                         if not k.startswith('comparison_cut_')})
            for t,v in zip(detail['tracks'][mode],current):
                assert np.allclose(t['first'],v[:6],rtol=0,atol=0,equal_nan=True)
                assert np.array_equal([t['charge'],t['chi2'],t['ndof'],t['measurements']],v[6:10],equal_nan=True)
    args.output.write_text(json.dumps(output,separators=(',', ':'),allow_nan=True))
    print(f'validated detailed event {args.run}/{args.event}; bytes={args.output.stat().st_size}',flush=True)


if __name__ == '__main__':
    main()
