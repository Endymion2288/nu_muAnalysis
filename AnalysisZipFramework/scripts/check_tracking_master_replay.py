#!/usr/bin/env python3
"""Compare a short frozen-runtime replay with the full-process event cache."""
import argparse
import json
from pathlib import Path
import resource
import time

import numpy as np
from report_tracking_ablation import event_key, load_cache, ordered, subset
from report_tracking_station import EVENT_KEYS, TRACK_KEYS


def compare(left, right):
    rows = {}
    for key in EVENT_KEYS + TRACK_KEYS:
        a, b = left[key], right[key]
        row = dict(left_shape=list(a.shape), right_shape=list(b.shape))
        row['exact'] = bool(np.array_equal(a, b, equal_nan=a.dtype.kind in 'fc'))
        if a.shape == b.shape:
            equal = a == b
            if a.dtype.kind in 'fc':
                equal |= np.isnan(a) & np.isnan(b)
            row['different_cells'] = int((~equal).sum())
        rows[key] = row
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--replay', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    start = time.monotonic()
    short = ordered(load_cache(args.replay))
    ids = event_key(short)
    result = dict(replay=str(args.replay), events=[dict(run=int(r), eventID=int(e))
        for r, e in zip(short['run'], short['eventID'])], comparisons={})
    for version, path in [
        ('latest_full', 'workbook/stage208_master_integration/full/latest.npz'),
        ('strict_full', 'workbook/stage205_material/full/strict.npz')]:
        reference = subset(load_cache(args.repo / path), ids)
        assert np.array_equal(ids, event_key(reference)), version
        result['comparisons'][version] = compare(reference, short)
    with np.load(args.replay) as source:
        result['runtime_source'] = json.loads(str(source['integration_provenance_json']))
        result['performance'] = json.loads(str(source['performance_json']))
    result.update(wall_s=time.monotonic()-start,
                  max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({v: [k for k, x in rows.items() if not x['exact']]
        for v, rows in result['comparisons'].items()}), flush=True)


if __name__ == '__main__':
    main()
