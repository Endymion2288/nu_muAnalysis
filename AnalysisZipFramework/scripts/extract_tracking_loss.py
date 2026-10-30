#!/usr/bin/env python3
"""Validate one rerun against cached paired cuts; retain only compact event diagnostics."""

import argparse
import json
from pathlib import Path

import awkward as ak
import numpy as np
import uproot

from compare_tracking import extract, raw_nontrack_check


def locate(path, run, event):
    with uproot.open(path) as source:
        tree = source['nt']
        ids = tree.arrays(['run', 'eventID'], library='np')
        entry = np.flatnonzero((ids['run'] == run) & (ids['eventID'] == event)).item()
    return entry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--run', type=int, required=True)
    parser.add_argument('--event', type=int, required=True)
    parser.add_argument('--bits', type=int, nargs=3, required=True)
    parser.add_argument('--existing-merge', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    paths = ['forward.root', 'backward.root', 'merge.root']
    assert raw_nontrack_check(paths) == 17
    output = dict(run=args.run, event=args.event, expected_bits=args.bits,
                  measurements=json.loads(Path('measurements.json').read_text()), modes={})
    for m, (mode, path) in enumerate(zip(('forward', 'backward', 'merge'), paths)):
        values, cumulative = extract(Path(path), args.repo)
        assert len(values['eventID']) == 1
        assert int(values['eventID'][0]) == args.event and int(values['run'][0]) == args.run
        bits = int(sum(int(value) << j for j, value in enumerate(cumulative[0, 7:])))
        assert bits == args.bits[m], (mode, bits, args.bits[m])
        with uproot.open(path) as source:
            tree = source['nt']
            columns = [key for key in tree.keys() if key.startswith(('Track_', 'SpacePoint_', 'truth_'))]
            columns += ['longTracks', 'SpacePoints']
            arrays = tree.arrays(columns, library='ak')
            raw = {key: ak.to_list(arrays[key][0]) for key in columns}
        output['modes'][mode] = dict(scalars={key: float(value[0]) for key, value in values.items()
                                            if not key.startswith('comparison_cut_')}, raw=raw)
    # Compare every persisted Track_* field and the retained truth columns to the published merge.
    entry = locate(args.existing_merge, args.run, args.event)
    with uproot.open(args.existing_merge) as source:
        tree = source['nt']
        columns = [key for key in output['modes']['merge']['raw'] if key in tree.keys()]
        arrays = tree.arrays(columns, entry_start=entry, entry_stop=entry+1, library='ak')
        for key in columns:
            a, b = np.asarray(ak.to_list(arrays[key][0])), np.asarray(output['modes']['merge']['raw'][key])
            assert np.array_equal(a, b, equal_nan=a.dtype.kind in 'fc'), key
    output['existing_merge_verified'] = True
    args.output.write_text(json.dumps(output, allow_nan=True, separators=(',', ':')))
    print(f'verified event={args.run}/{args.event} bits={args.bits} bytes={args.output.stat().st_size}')


if __name__ == '__main__':
    main()
