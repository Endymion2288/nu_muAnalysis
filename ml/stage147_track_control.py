"""Frozen truth-association diagnosis of cached scores; no refit or new readout."""
import csv
import gzip
import json
import resource
import time
from collections import Counter
from pathlib import Path

import awkward as ak
import numpy as np
import uproot

from stage145_mu_joint import clean, wilson

OUT = Path('workbook/stage147_energy_ml')
FIELDS = ['pdg', 'barcode', 'pdg_parent', 'barcode_parent', 'truthHitRatio', 'pz']
BRANCHES = ['run', 'eventID', 'longTracks', 'Track_pz0', 'Track_nDoF', 'Track_Chi2', 'Track_nLayers']
BRANCHES += ['t_'+field for field in FIELDS]


def read(path, stop):
    tick, cpu = time.perf_counter(), time.process_time()
    with uproot.open(path, array_cache=None) as root:
        tree = root['nt']
        missing = sorted(set(BRANCHES)-set(tree.keys()))
        assert not missing, missing
        values = tree.arrays(BRANCHES, entry_stop=stop)
        lengths = {field: int(ak.sum(ak.num(values['t_'+field], axis=1) != ak.num(values.Track_pz0, axis=1))) for field in FIELDS}
        report = dict(input_N=len(values), missing=missing, misaligned_event_N=lengths,
                      read_bytes=int(root.file.source.num_requested_bytes), CPU_s=time.process_time()-cpu,
                      wall_s=time.perf_counter()-tick)
    return values, report


def main():
    tick, cpu = time.perf_counter(), time.process_time()
    plan = json.loads((OUT/'protocol.json').read_text())
    _, pilot = read(plan['PHYS'], 64)
    (OUT/'pilot.json').write_text(json.dumps(pilot, indent=2)+'\n')
    values, measured = read(plan['PHYS'], 4096)
    with gzip.open(plan['event_records'], 'rt') as stream:
        container = json.load(stream)
    identities = json.loads(container['workbook/stage146_energy_ml/identity_records.json.gz'])
    assert len(identities) == len(values)
    assert all(int(values.run[i]) == row['run'] and int(values.eventID[i]) == row['event'] for i, row in enumerate(identities))
    leading = ak.argmax(values.Track_pz0, axis=1, keepdims=True, mask_identity=True)

    def get(branch):
        chosen = ak.local_index(values[branch], axis=1) == ak.firsts(leading)[:, None]
        return clean(ak.to_numpy(ak.fill_none(ak.firsts(values[branch][chosen]), np.nan)))

    pz, ndof, chi = get('Track_pz0')/1000, get('Track_nDoF'), get('Track_Chi2')
    chi[chi < 0] = np.nan
    good = ((ak.to_numpy(values.longTracks) == 1) & np.isfinite(pz) & (pz > 50) & (pz < 2000)
            & (ndof > 0) & (chi/np.maximum(ndof, 1) < 10) & (get('Track_nLayers') >= 7))
    expected = np.array([row['entry'] for row in identities if 'scores' in row])
    assert np.array_equal(np.flatnonzero(good), expected)
    selected = [identities[int(entry)] for entry in expected]
    native = {field: get('t_'+field)[good] for field in FIELDS}
    aligned = np.ones(len(expected), dtype=bool)
    for field in FIELDS:
        aligned &= ak.to_numpy(ak.num(values['t_'+field], axis=1) == ak.num(values.Track_pz0, axis=1))[good]
    pdg, barcode, ratio = native['pdg'], native['barcode'], native['truthHitRatio'].copy()
    invalid_ratio = ~np.isfinite(ratio) | (ratio < 0) | (ratio > 1)
    ratio[invalid_ratio] = np.nan
    known = np.array([row['reason'] == 'matched_retained_mu_root' for row in selected])
    hitmatch = aligned & np.isfinite(pdg) & (pdg != 0) & np.isfinite(barcode) & (barcode > 0)
    classification = np.full(len(expected), 'unknown_association', dtype=object)
    classification[hitmatch & (np.abs(pdg) == 13)] = 'recorded_mu_match'
    classification[hitmatch & (np.abs(pdg) != 13)] = 'recorded_nonmu_match'
    classification[~known] = 'unknown_root'
    direct_root = np.array([bool(hitmatch[i] and int(barcode[i]) in row['matched_root_barcodes']) for i, row in enumerate(selected)])
    truepz = native['pz']/1000
    with np.errstate(divide='ignore', invalid='ignore'):
        pzrelative = pz[good]/truepz-1
    pzrelative[~hitmatch | ~np.isfinite(truepz) | (truepz <= 0)] = np.nan
    rows = []
    for policy in ['Q15', 'Qshape30']:
        scored = np.array([row['scores'][policy]['scored'] for row in selected])
        alarm = np.array([row['scores'][policy]['alert'] for row in selected])
        heldout = np.array([row['heldout'] for row in selected])
        for group in ['all', 'overflow', 'high_activity', 'pz50_100']:
            mask = heldout & np.array([row['groups'][group] for row in selected])
            for category in ['all', 'recorded_mu_match', 'recorded_nonmu_match', 'unknown_association', 'unknown_root']:
                denominator = mask & ((classification == category) if category != 'all' else np.ones(len(expected), bool))
                use = denominator & scored
                n, k = int(use.sum()), int((use & alarm).sum())
                low, high = wilson(k, n)
                finite_ratio, finite_pz = use & np.isfinite(ratio), use & np.isfinite(pzrelative)
                alert_ratio, alert_pz = finite_ratio & alarm, finite_pz & alarm
                rows.append(dict(policy=policy, group=group, association=category, original_heldout_N=int(denominator.sum()),
                    scored_N=n, alerts=k, fraction=k/n if n else None, Wilson95_low=low, Wilson95_high=high,
                    direct_generator_root_match_N=int((use & direct_root).sum()), hit_ratio_N=int(finite_ratio.sum()),
                    hit_ratio_median=float(np.median(ratio[finite_ratio])) if finite_ratio.any() else None,
                    hit_ratio_below08_N=int((finite_ratio & (ratio < .8)).sum()),
                    relative_pz_N=int(finite_pz.sum()), relative_pz_median=float(np.median(pzrelative[finite_pz])) if finite_pz.any() else None,
                    alert_hit_ratio_N=int(alert_ratio.sum()), alert_hit_ratio_median=float(np.median(ratio[alert_ratio])) if alert_ratio.any() else None,
                    alert_relative_pz_N=int(alert_pz.sum()), alert_relative_pz_median=float(np.median(pzrelative[alert_pz])) if alert_pz.any() else None))
    previous = list(csv.DictReader(Path('workbook/stage146_energy_ml/heldout_by_root.tsv').open(), delimiter='\t'))
    for row in rows:
        if row['association'] == 'all':
            old = next(r for r in previous if r['policy'] == row['policy'] and r['group'] == row['group'] and r['ancestry'] == 'all')
            assert all(int(old[field]) == row[field] for field in ['original_heldout_N', 'scored_N', 'alerts'])
    with (OUT/'heldout_track.tsv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter='\t', lineterminator='\n')
        writer.writeheader()
        writer.writerows({key: 'NA' if value is None else value for key, value in row.items()} for row in rows)
    # Keep the tiny tail witness table, including truth-match failures.
    witnesses = []
    for i, row in enumerate(selected):
        if row['heldout'] and (row['groups']['overflow'] or row['groups']['high_activity']):
            witnesses.append(dict(entry=row['entry'], run=row['run'], event=row['event'], ancestry=row['reason'],
                group=row['groups'], classification=classification[i], t_pdg=float(pdg[i]) if np.isfinite(pdg[i]) else None,
                t_barcode=float(barcode[i]) if np.isfinite(barcode[i]) else None,
                t_parent_pdg=float(native['pdg_parent'][i]) if np.isfinite(native['pdg_parent'][i]) else None,
                t_parent_barcode=float(native['barcode_parent'][i]) if np.isfinite(native['barcode_parent'][i]) else None,
                hit_ratio=float(ratio[i]) if np.isfinite(ratio[i]) else None,
                pz0_GeV=float(pz[good][i]), matched_truth_pz_GeV=float(truepz[i]) if np.isfinite(truepz[i]) else None,
                scores=row['scores']))
    (OUT/'tail_witnesses.json').write_text(json.dumps(witnesses, indent=2, allow_nan=False)+'\n')
    report = dict(passed=True, pilot=pilot, measured=measured, original_identity_exact=True, original_selection_exact=True,
        selected_N=len(expected), classification_counts=dict(Counter(classification)), original_group_counts_exact=True,
        invalid_hit_ratio_N=int(invalid_ratio.sum()), nonpositive_barcode_N=int((~np.isfinite(barcode) | (barcode <= 0)).sum()),
        CPU_s=time.process_time()-cpu, wall_s=time.perf_counter()-tick,
        RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, energy_fits=0, response_fits=0,
        new_G4=0, reserved_forward=0, true_PRD_association_or_covariance_certified=False,
        scope='Recorded ntuple truth match diagnostic only, not new sensor information, transported process classification, calibrated covariance or data/nu transfer')
    (OUT/'summary.json').write_text(json.dumps(report, indent=2)+'\n')
    print(report, flush=True)


if __name__ == '__main__':
    main()
