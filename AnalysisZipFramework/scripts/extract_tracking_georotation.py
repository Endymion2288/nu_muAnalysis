#!/usr/bin/env python3
"""Validate paired modes and retain compact cuts, candidate truth, and overlap counts."""
import argparse
import gzip
import itertools
import json
from pathlib import Path

import awkward as ak
import numpy as np
import uproot

from compare_tracking import extract, raw_nontrack_check, selection, PAIRS, ENERGY_EDGES, RADIUS_EDGES, Z_EDGES
from run_tracking_georotation import FIELDS

TRACK_FIELDS = ['run', 'event', 'mode', 'raw_index', 'source_mode', 'source_index'] + FIELDS
PAIR_FIELDS = ['run', 'event', 'mode', 'left', 'right', 'exact_shared', 'merge_shared',
               'minimum_hits', 'same_truth', 'minimum_purity']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--index', type=int, required=True)
    args = parser.parse_args()
    paths = [Path(f'{m}.root') for m in ('forward', 'backward', 'merge')]
    data, masks = zip(*(extract(p, args.repo, rotated=True) for p in paths))
    assert raw_nontrack_check(paths) == 17
    for d in data[1:]:
        for key in ('run', 'eventID', 'truth_pz_nu', 'truth_dec_x_nu', 'truth_dec_y_nu', 'truth_dec_z_nu'):
            assert np.array_equal(data[0][key], d[key], equal_nan=True), key
    masks = np.stack(masks)
    cuts, _ = selection(args.repo)
    names = [name for name, _ in cuts]
    fi = names.index('Truth pz > 100 GeV') + 1
    ti = names.index('Leading track theta < 25 mrad') + 1
    assert np.array_equal(masks[:, :, :fi+1], np.broadcast_to(masks[:1, :, :fi+1], masks[:, :, :fi+1].shape))
    counts = masks.sum(axis=1, dtype=np.int64)
    overlaps = np.zeros((3, masks.shape[2], 4), dtype=np.int64)
    for i, (a, b) in enumerate(PAIRS):
        code = masks[a].astype(np.int8) + 2 * masks[b].astype(np.int8)
        overlaps[i] = np.array([(code == c).sum(axis=0) for c in range(4)]).T
    baseline = masks[0, :, fi]
    bits = np.zeros((int(baseline.sum()), 3), dtype=np.uint16)
    individual_bits = np.zeros_like(bits)
    for m in range(3):
        for j in range(masks.shape[2] - fi - 1):
            bits[:, m] |= masks[m, baseline, fi+1+j].astype(np.uint16) << j
            individual_bits[:, m] |= data[m][f'comparison_cut_{fi+j}'][baseline].astype(np.uint16) << j
    result = dict(counts=counts, overlaps=overlaps, fiducial_index=fi, tracking_index=ti,
                  nontrack_columns=17, existing_merge_verified=0, manifest_index=args.index,
                  nonfinite_leading_quality=np.array([np.count_nonzero(
                      (d['LeadTrack_Idx'] >= 0) & ~np.isfinite(d['LeadTrack_Chi2_NDF'])) for d in data]),
                  event_cut_bits=bits, event_reco_decision_bits=individual_bits)
    for key in ('run', 'eventID', 'truth_pz_nu', 'truth_dec_x_nu', 'truth_dec_y_nu', 'truth_dec_z_nu'):
        result['event_' + key] = data[0][key][baseline]
    for key in ('LeadTrack_Idx', 'LeadTrack_pz0', 'LeadTrack_Chi2_NDF', 'LeadTrack_r_atMaxRadius',
                'LeadTrack_rIFT', 'LeadTrack_Theta', 'Lead_Track_Y_atTrig'):
        result['event_' + key] = np.stack([d[key][baseline] for d in data], axis=1)
    for label, column, edges in [('energy', 'truth_pz_nu', ENERGY_EDGES),
                                  ('radius', 'truth_dec_r', RADIUS_EDGES),
                                  ('z', 'truth_dec_z_nu', Z_EDGES)]:
        result[label + '_den'] = np.histogram(data[0][column][baseline], edges)[0]
        result[label + '_pass'] = np.array([[np.histogram(data[0][column][masks[m, :, j]], edges)[0]
                                            for j in (fi+1, ti, masks.shape[2]-1)] for m in range(3)])
    nt = []
    branches = ['Track_px0', 'Track_py0', 'Track_pz0', 'Track_Chi2', 'Track_nDoF', 'Track_nLayers',
                'Track_isForward', 'Track_nMeasurements', 't_barcode', 't_pdg', 't_truthHitRatio']
    for path in paths:
        with uproot.open(path) as source:
            arrays = source['nt'].arrays(['run', 'eventID'] + branches, library='ak')
        nt.append({(int(r.run), int(r.eventID)): r for r in arrays})
    ids = {(int(r), int(e)): i for i, (r, e) in enumerate(zip(data[0]['run'], data[0]['eventID']))}
    raw_meta = json.loads(Path('raw_metadata.json').read_text())
    assert raw_meta['events'] == counts[0, 0] and raw_meta['fields'] == FIELDS
    track_rows, pair_rows, migration_rows = [], [], []
    mismatch_measurements = np.zeros(3, dtype=np.int64)
    raw_counts = np.zeros(3, dtype=np.int64)
    raw_long = np.zeros(3, dtype=np.int64)
    nonfinite_chi2 = np.zeros(3, dtype=np.int64)
    match_checked = np.zeros(3, dtype=np.int64)
    seen = set()
    with gzip.open('raw_tracks.jsonl.gz', 'rt') as source:
        for line in source:
            run, event, collections = json.loads(line)
            key = (run, event)
            assert key in ids and key not in seen
            seen.add(key)
            index = ids[key]
            origins = []
            for merged in collections[2]:
                found = [(m, i) for m in (0, 1) for i, t in enumerate(collections[m])
                         if t['hits'] == merged['hits'] and
                         np.array_equal(t['values'], merged['values'], equal_nan=True)]
                assert found, ('merge source missing', key)
                origins.append(found[0])
            leaders = []
            for m, collection in enumerate(collections):
                raw_counts[m] += len(collection)
                long_indices = [i for i, t in enumerate(collection) if t['values'][12]]
                raw_long[m] += len(long_indices)
                row = nt[m][key]
                assert len(long_indices) == len(row.Track_px0), (key, m)
                mismatch_measurements[m] += len(row.Track_nMeasurements) != len(long_indices)
                leader = int(data[m]['LeadTrack_Idx'][index])
                leaders.append(long_indices[leader] if leader >= 0 else -1)
                for i, t in enumerate(collection):
                    v = t['values']
                    sm, si = origins[i] if m == 2 else (m, i)
                    track_rows.append([run, event, m, i, sm, si] + v)
                    nonfinite_chi2[m] += not np.isfinite(v[7])
                for j, i in enumerate(long_indices):
                    v = collection[i]['values']
                    # Maker uses raw rotated components; diagnostic stores original frame.
                    assert np.allclose([row.Track_px0[j], row.Track_py0[j], row.Track_pz0[j]],
                                       [v[5], v[4], -v[3]], rtol=2e-6, atol=.05, equal_nan=True)
                    assert np.allclose([row.Track_Chi2[j], row.Track_nDoF[j], row.Track_nLayers[j]],
                                       [v[7], v[8], v[10]], rtol=2e-6, equal_nan=True)
                    if v[13] != 0:
                        assert int(row.t_barcode[j]) == int(v[13]) and int(row.t_pdg[j]) == int(v[14])
                        assert np.isclose(row.t_truthHitRatio[j], v[15]/(v[8]+5), rtol=2e-6)
                        match_checked[m] += 1
                    if m == 2:
                        assert bool(row.Track_isForward[j]) == (origins[i][0] == 0)
                for left, right in itertools.combinations(range(len(collection)), 2):
                    a, b = collection[left], collection[right]
                    va, vb = a['values'], b['values']
                    exact = sum(h in set(a['hits']) for h in b['hits'])
                    shared = sum(h in set(a['merge_hits']) for h in b['merge_hits'])
                    purity = min(va[15]/va[9], vb[15]/vb[9])
                    pair_rows.append([run, event, m, left, right, exact, shared,
                                      min(va[9], vb[9]), int(va[13] != 0 and va[13] == vb[13]), purity])
            # Retain every B/M final-selection migration, including nonlong blockers.
            bpass, mpass = masks[1, index, -1], masks[2, index, -1]
            if bpass != mpass:
                b = leaders[1]
                present = next((i for i, origin in enumerate(origins) if origin == (1, b)), -1)
                blockers = []
                if b >= 0:
                    bhits = collections[1][b]['merge_hits']
                    blockers = [i for i, t in enumerate(collections[2])
                                if sum(h in set(t['merge_hits']) for h in bhits) > 6]
                migration_rows.append([run, event, int(bpass), int(mpass), *leaders, present,
                                       blockers[0] if blockers else -1])
    for m in range(3):
        assert raw_long[m] == sum(len(r.Track_px0) for r in nt[m].values())
    result.update(track_fields=np.array(TRACK_FIELDS), pair_fields=np.array(PAIR_FIELDS),
                  tracks=np.array(track_rows, dtype=np.float64).reshape(-1, len(TRACK_FIELDS)),
                  pairs=np.array(pair_rows, dtype=np.float64).reshape(-1, len(PAIR_FIELDS)),
                  migrations=np.array(migration_rows, dtype=np.int64).reshape(-1, 9),
                  raw_counts=raw_counts, raw_long=raw_long, nonfinite_raw_chi2=nonfinite_chi2,
                  truth_matches_checked=match_checked, measurement_length_mismatches=mismatch_measurements)
    np.savez_compressed(args.output, **result)
    print('VALIDATED', json.dumps(dict(events=int(counts[0,0]), truth=int(counts[0,fi]),
          final=counts[:,-1].tolist(), raw_tracks=raw_counts.tolist(), raw_long=raw_long.tolist(),
          nonfinite_raw_chi2=nonfinite_chi2.tolist(), truth_checked=match_checked.tolist(),
          measurements_length_mismatch=mismatch_measurements.tolist(), bytes=args.output.stat().st_size)), flush=True)


if __name__ == '__main__':
    main()
