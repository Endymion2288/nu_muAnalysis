#!/usr/bin/env python3
"""Validate rerun cuts and raw candidates against stage17 before retaining truth only."""

import argparse
import gzip
import json
from pathlib import Path

import awkward as ak
import numpy as np
import uproot

from compare_tracking import extract, raw_nontrack_check


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--run', type=int, required=True)
    parser.add_argument('--event', type=int, required=True)
    parser.add_argument('--bits', type=int, nargs=3, required=True)
    parser.add_argument('--existing-merge', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with gzip.open(args.repo/'reference.json.gz','rt') as source:
        reference = next(e for e in json.load(source) if (e['run'],e['event']) == (args.run,args.event))
    assert reference['expected_bits'] == args.bits
    raw_truth = json.loads(Path('raw_truth.json').read_text())
    output = dict(run=args.run, event=args.event, expected_bits=args.bits, raw_truth=raw_truth,
                  stage17_verified=True, modes={})
    paths = ['forward.root','backward.root','merge.root']
    assert raw_nontrack_check(paths) == 17
    for m,(mode,path) in enumerate(zip(('forward','backward','merge'),paths)):
        values, cumulative = extract(Path(path),args.repo)
        assert len(cumulative) == 1 and int(values['run'][0]) == args.run and int(values['eventID'][0]) == args.event
        bits = sum(int(value) << j for j,value in enumerate(cumulative[0,7:]))
        assert bits == args.bits[m]
        with uproot.open(path) as source:
            tree = source['nt']; columns = [key for key in tree.keys() if key.startswith(('Track_','t_','truth_'))]
            arrays = tree.arrays(columns,library='ak')
            raw = {key:ak.to_list(arrays[key][0]) for key in columns}
        for key,old in reference['modes'][mode]['raw'].items():
            if key in raw:
                a,b = np.asarray(raw[key]),np.asarray(old)
                assert np.array_equal(a,b,equal_nan=a.dtype.kind in 'fc'), (mode,key)
        old_tracks = reference['measurements'][mode]
        assert len(old_tracks) == len(raw_truth[mode])
        for i,(old,new) in enumerate(zip(old_tracks,raw_truth[mode])):
            assert old['chi2'] == new['chi2'] or (np.isnan(old['chi2']) and np.isnan(new['chi2']))
            assert old['ndof'] == new['ndof'] and len(old['hits']) == new['measurements']
            assert np.array_equal(old['states'][0],new['first'],equal_nan=True), (mode,i)
        for key in raw:
            if key.startswith('t_'):
                assert len(raw[key]) == len(raw['Track_pz0']), (mode,key)
        output['modes'][mode] = {key: value for key,value in raw.items() if key.startswith('t_')}
    args.output.write_text(json.dumps(output,allow_nan=True,separators=(',',':')))
    print(f'verified truth run={args.run} event={args.event} bytes={args.output.stat().st_size}')


if __name__ == '__main__':
    main()
