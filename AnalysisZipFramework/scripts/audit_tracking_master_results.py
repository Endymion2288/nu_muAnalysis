#!/usr/bin/env python3
"""Locate strict/latest drift and quantify momentum tails without dropping outliers."""
import argparse
import json
from pathlib import Path
import time

import numpy as np
from compare_tracking import MODES
from extract_tracking_station import SCALARS, TRACK_FIELDS
from report_tracking_material import truth_masks
from report_tracking_station import derived, table


def load(path):
    with np.load(path) as source:
        return {k: source[k] for k in source.files}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    start = time.monotonic()
    data = dict(old=load(args.repo / 'workbook/stage203_station_truth/old.npz'),
                strict=load(args.repo / 'workbook/stage205_material/full/strict.npz'),
                latest=load(args.report / 'latest.npz'))
    a, b = data['strict'], data['latest']
    n = len(a['run'])
    counts = [np.bincount(d['tracks'][:, 0].astype(int), minlength=n) for d in [a, b]]
    starts = [np.r_[0, np.cumsum(c)] for c in counts]
    changed = []
    track_fields = ['tracks', 'reco_station', 'reco_at_primary_station',
                    'matched_truth_station', 'nearest_state_dz_mm', 'station_method']
    for i in np.flatnonzero(counts[0] + counts[1]):
        diffs = []
        for key in track_fields:
            x, y = [d[key][s[i]:s[i+1]] for d, s in zip([a, b], starts)]
            if not np.array_equal(x, y, equal_nan=True):
                diffs.append(key)
        if diffs:
            changed.append(dict(run=int(a['run'][i]), eventID=int(a['eventID'][i]), event_index=int(i),
                strict_tracks=int(counts[0][i]), latest_tracks=int(counts[1][i]), fields=diffs,
                strict_track_rows=a['tracks'][starts[0][i]:starts[0][i+1], 1:].tolist(),
                latest_track_rows=b['tracks'][starts[1][i]:starts[1][i+1], 1:].tolist(),
                strict_final=(a['event_cut_bits'][i] == 16383).tolist(),
                latest_final=(b['event_cut_bits'][i] == 16383).tolist()))
    scalar_rows = []
    for j, name in enumerate(SCALARS):
        equal = (a['event_scalars'][:, :, j] == b['event_scalars'][:, :, j])
        equal |= np.isnan(a['event_scalars'][:, :, j]) & np.isnan(b['event_scalars'][:, :, j])
        for m, mode in enumerate(MODES):
            for i in np.flatnonzero(~equal[:, m]):
                scalar_rows.append(dict(run=int(a['run'][i]), eventID=int(a['eventID'][i]), mode=mode,
                    scalar=name, strict=a['event_scalars'][i, m, j], latest=b['event_scalars'][i, m, j]))
    table(args.report / 'strict_changed_scalars.tsv', scalar_rows)
    (args.report / 'strict_changed_track_events.json').write_text(json.dumps(changed, indent=2) + '\n')
    masks = truth_masks(data['old'])
    tails, extreme = [], []
    for version, d in data.items():
        der = derived(d)
        leader = der['leaders'][:, 2]
        li = np.maximum(leader, 0)
        correct = (leader >= 0) & der['primary'][li] & (der['purity'][li] >= .7)
        for st in range(3):
            t = d['primary_station'][:, st, 5]
            p = d['reco_at_primary_station'][li, st, 5]
            with np.errstate(invalid='ignore', divide='ignore'):
                x = abs(p / t - 1)
            valid = correct & np.isfinite(x) & (t > 0)
            scopes = dict(truth_accepted=valid & masks['truth_station_acceptance'],
                          final=valid & der['final'][:, 2])
            for scope, selected in scopes.items():
                y = x[selected]
                tails.append(dict(version=version, mode='merge', station=st+1, scope=scope, pairs=len(y),
                    median=float(np.median(y)), q95=float(np.quantile(y, .95)), q99=float(np.quantile(y, .99)),
                    mean=float(y.mean()), maximum=float(y.max()), error_gt_half=int((y > .5).sum()),
                    error_gt_one=int((y > 1).sum()), error_gt_ten=int((y > 10).sum()),
                    error_gt_thousand=int((y > 1000).sum())))
                for i in np.flatnonzero(selected & (x > 1000)):
                    extreme.append(dict(version=version, station=st+1, scope=scope, run=int(d['run'][i]),
                        eventID=int(d['eventID'][i]), truth_pz_gev=t[i]/1000, reco_pz_gev=p[i]/1000,
                        absolute_relative_error=x[i], ndof=der['col']['ndof'][li[i]],
                        chi2=der['col']['chi2'][li[i]], final=bool(der['final'][i, 2])))
    table(args.report / 'momentum_tail_audit.tsv', tails)
    table(args.report / 'extreme_momentum_events.tsv', extreme)
    record = dict(strict_latest_changed_long_track_events=len(changed),
        strict_latest_changed_event_scalar_cells=len(scalar_rows),
        strict_latest_long_track_delta=len(b['tracks'])-len(a['tracks']),
        unchanged_long_track_events=int(((counts[0]+counts[1]) > 0).sum())-len(changed),
        track_columns=TRACK_FIELDS[1:], wall_s=time.monotonic()-start)
    (args.report / 'residual_audit.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record), flush=True)


if __name__ == '__main__':
    main()
