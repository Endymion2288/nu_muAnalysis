#!/usr/bin/env python3
"""Compare the integrated master against frozen old and strict on common RDO events."""
import argparse
import json
from pathlib import Path
import resource
import time

import numpy as np
import report_tracking_station as station
import report_tracking_material as material
from report_tracking_ablation import event_key, ordered, subset
from compare_tracking import MODES, selection


def load(path):
    with np.load(path) as source:
        return {k: source[k] for k in source.files}


def paired_momentum_bands(data, der, masks, output):
    """Hold event identity fixed when comparing low and high momentum accuracy."""
    rows = []
    for baseline, variant in [('old', 'latest'), ('strict', 'latest')]:
        for m, mode in enumerate(MODES):
            left, right = der[baseline]['leaders'][:, m], der[variant]['leaders'][:, m]
            il, ir = np.maximum(left, 0), np.maximum(right, 0)
            common = (left >= 0) & (right >= 0)
            common &= der[baseline]['primary'][il] & der[variant]['primary'][ir]
            common &= (der[baseline]['purity'][il] >= .7) & (der[variant]['purity'][ir] >= .7)
            for st in range(3):
                truth = data[baseline]['primary_station'][:, st, 3:] / 1000
                a = data[baseline]['reco_at_primary_station'][il, st, 3:] / 1000
                b = data[variant]['reco_at_primary_station'][ir, st, 3:] / 1000
                for quantity in ['p', 'pz']:
                    t = np.linalg.norm(truth, axis=1) if quantity == 'p' else truth[:, 2]
                    x = np.linalg.norm(a, axis=1) if quantity == 'p' else a[:, 2]
                    y = np.linalg.norm(b, axis=1) if quantity == 'p' else b[:, 2]
                    with np.errstate(invalid='ignore', divide='ignore'):
                        x, y = abs(x / t - 1), abs(y / t - 1)
                    valid = common & np.isfinite(x) & np.isfinite(y) & (t > 0)
                    for group, population in [('all', np.ones(len(t), bool)), ('nominal', data[baseline]['run'] != 200080)]:
                        for scope, selected in [
                            ('truth_accepted_common', masks['truth_station_acceptance']),
                            ('both_final', der[baseline]['final'][:, m] & der[variant]['final'][:, m])]:
                            for lo, hi in zip([0, 100, 300, 1000, 3000], [100, 300, 1000, 3000, np.inf]):
                                selected_bin = valid & population & selected & (t >= lo) & (t < hi)
                                u, v = x[selected_bin], y[selected_bin]
                                lw, rw = int((u < v - 1e-10).sum()), int((v < u - 1e-10).sum())
                                rows.append(dict(baseline=baseline, variant=variant, group=group, mode=mode,
                                    station=st + 1, quantity=quantity, scope=scope, low_gev=lo, high_gev=hi,
                                    pairs=len(u), baseline_closer=lw, variant_closer=rw, ties=len(u)-lw-rw,
                                    baseline_median_absolute=float(np.median(u)) if len(u) else np.nan,
                                    variant_median_absolute=float(np.median(v)) if len(v) else np.nan,
                                    baseline_tail_gt_half=int((u > .5).sum()), variant_tail_gt_half=int((v > .5).sum()),
                                    sign_p=float(station.binomtest(rw, lw + rw).pvalue) if lw + rw else np.nan))
    station.table(output / 'paired_momentum_bands.tsv', rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--partial', action='store_true')
    parser.add_argument('--paired-old', action='store_true')
    args = parser.parse_args()
    start = time.monotonic()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    records = [r.split('\t') for r in args.manifest.read_text().splitlines()]
    latest, audit = station.combine(records, 'new', out)
    (out / 'new.npz').rename(out / 'latest.npz')
    data = dict(old=load(args.repo / 'workbook/stage203_station_truth/old.npz'),
                strict=load(args.repo / 'workbook/stage205_material/full/strict.npz'), latest=latest)
    truth = ['run', 'eventID', 'truth_pz_nu', 'truth_dec_x_nu', 'truth_dec_y_nu', 'truth_dec_z_nu',
             'primary', 'primary_production_momentum_mev', 'primary_station', 'primary_layer_hits']
    configurations = []
    for row, record in zip(audit, records):
        row['version'] = 'latest'
        config = json.loads(row.pop('effective_reco'))
        assert config['exact_strict_map']
        assert len(config['algorithms']) == 4
        assert all(a['isolated_smoothing'] for a in config['algorithms'].values())
        row['material_file'] = config['material_file']
        config['material_file'] = 'packaged validated row-major map (per-process temporary path)'
        if configurations:
            assert configurations[0] == config, ('configuration drift', record[0])
        else:
            configurations.append(config)
    if args.partial:
        for version in ('old', 'strict'):
            data[version] = subset(data[version], event_key(latest))
    for version, a in data.items():
        for k in truth:
            assert np.array_equal(a[k], data['old'][k], equal_nan=a[k].dtype.kind in 'fc'), (version, k)
        if not args.partial:
            for k in ('all_run', 'all_eventID'):
                assert np.array_equal(a[k], data['old'][k]), (version, k)
    strict_equivalence = {}
    for k in station.EVENT_KEYS + station.TRACK_KEYS:
        a, b = data['strict'][k], latest[k]
        row = dict(strict_shape=list(a.shape), latest_shape=list(b.shape), same_shape=a.shape == b.shape)
        if a.shape == b.shape:
            equal = a == b
            if a.dtype.kind in 'fc':
                equal |= np.isnan(a) & np.isnan(b)
            row.update(exact=bool(equal.all()), unequal_elements=int((~equal).sum()), elements=a.size)
        strict_equivalence[k] = row
    (out / 'strict_array_equivalence.json').write_text(json.dumps(strict_equivalence, indent=2) + '\n')
    if not args.partial:
        assert len(latest['all_run']) == 3374987 and len(latest['run']) == 383670
        assert sum(row['events'] for row in audit) == 3374987
    source_counts = []
    paired_audit = []
    provenance = None
    for record in records:
        shard = ordered(load(record[5]))
        shard_provenance = json.loads(str(shard['integration_provenance_json']))
        if provenance is None:
            provenance = shard_provenance
        else:
            assert provenance == shard_provenance, ('source drift', record[0])
        source_counts.append(shard['counts'])
        restored = subset(latest, event_key(shard))
        for k in station.EVENT_KEYS + station.TRACK_KEYS:
            assert np.array_equal(shard[k], restored[k], equal_nan=shard[k].dtype.kind in 'fc'), (record[0], record[4], k)
        if args.paired_old:
            old_path = Path(record[5].replace('latest_', 'old_'))
            old_shard = ordered(load(old_path))
            for key in ['all_run', 'all_eventID']:
                assert np.array_equal(old_shard[key], shard[key]), ('paired input IDs', record[0], key)
            for key in truth:
                assert np.array_equal(old_shard[key], shard[key], equal_nan=shard[key].dtype.kind in 'fc'), ('paired truth', record[0], key)
            reference = subset(data['old'], event_key(old_shard))
            for k in station.EVENT_KEYS + station.TRACK_KEYS:
                assert np.array_equal(old_shard[k], reference[k], equal_nan=old_shard[k].dtype.kind in 'fc'), ('old replay', record[0], k)
            assert str(old_shard['host']) == audit[len(paired_audit)]['host']
            assert str(old_shard['paired_order']) == str(shard['paired_order'])
            paired_audit.append(dict(index=int(record[0]), skip=int(record[4]), host=str(old_shard['host']),
                                     order=str(shard['paired_order']),
                                     events=int(old_shard['counts'][0, 0]), exact_old_cache=True,
                                     old=json.loads(str(old_shard['performance_json'])),
                                     latest=json.loads(str(shard['performance_json']))))
    masks = material.truth_masks(data['old'])
    if not args.partial:
        assert masks['truth_station_acceptance'].sum() == 140132
    groups = dict(all=np.ones(len(latest['run']), bool), nominal=latest['run'] != 200080)
    groups.update({str(r): latest['run'] == r for r in np.unique(latest['run'])})
    der = {v: station.derived(a) for v, a in data.items()}
    for v, a in data.items():
        der[v]['control'] = station.controlled(a, data['old'])
    assert np.array_equal(der['old']['control'], ((data['old']['event_cut_bits'][:, :, None] >> np.arange(14)) & 1).astype(bool))
    comparisons = [('old', 'latest'), ('strict', 'latest')]
    cuts = [name for name, _ in selection(args.repo)[0]][6:]
    cutrows = []
    totals = np.sum(source_counts, axis=0)
    names = ['NoCuts'] + [name for name, _ in selection(args.repo)[0]]
    assert np.array_equal(totals[:, 6], np.full(3, len(latest['run'])))
    for version, a in data.items():
        for m, mode in enumerate(MODES):
            for j, name in enumerate(names):
                # The first six cuts use only unchanged truth inputs from common RDOs.
                # Later counts are exact sums of each version's cached cumulative bits.
                passed = int(totals[m, j]) if j <= 6 else int(((a['event_cut_bits'][:, m] >> (j - 7)) & 1).sum())
                if version == 'latest':
                    assert passed == totals[m, j], ('raw/fiducial cutflow closure', mode, name)
                cutrows.append(dict(version=version, mode=mode, cut=name, passed=passed,
                    initial=int(totals[m, 0]), source='common RDO truth cuts measured in latest' if j <= 6 else 'version cumulative event bits'))
    station.table(out / 'full_input_cutflow.tsv', cutrows)
    cutrows = []
    for version, a in data.items():
        for m, mode in enumerate(MODES):
            for j, name in enumerate(cuts):
                passed = ((a['event_cut_bits'][:, m] >> j) & 1).astype(bool)
                cutrows.append(dict(version=version, mode=mode, cut=name, truth_fiducial=len(a['run']),
                    actual_passed=int(passed.sum()), fixed_old_charge_passed=int(der[version]['control'][:, m, j].sum()),
                    truth_accepted=int(masks['truth_station_acceptance'].sum()),
                    truth_accepted_passed=int((passed & masks['truth_station_acceptance']).sum())))
    station.table(out / 'fiducial_cutflow.tsv', cutrows)
    station.basic_metrics(data, der, out, groups, masks, cuts)
    residuals, bins = station.response_metrics(data, der, out, groups, masks, comparisons)
    station.particle_content(data, der, groups, out)
    station.local_cut_migrations(data, der, groups, out)
    material.duplicates(data, der, groups, masks, out)
    material.selection_pairs(data, der, groups, masks, comparisons, out)
    material.mode_migrations(data, der, groups, masks, cuts, out)
    material.spectra(data, der, masks, out)
    material.common_cohort(data, der, masks, out)
    paired_momentum_bands(data, der, masks, out)
    station.plots(data, der, out, masks, residuals, bins)

    # Explicit old/latest migration list, including every failed cumulative cut.
    migration = []
    for m, mode in enumerate(MODES):
        a, b = der['old']['final'][:, m], der['latest']['final'][:, m]
        for index in np.flatnonzero(masks['truth_station_acceptance'] & (a != b)):
            row = dict(mode=mode, run=int(latest['run'][index]), eventID=int(latest['eventID'][index]),
                       old_final=bool(a[index]), latest_final=bool(b[index]))
            for version in ('old', 'latest'):
                bits = int(data[version]['event_cut_bits'][index, m])
                failed = [cuts[j] for j in range(14) if not (bits >> j) & 1]
                row[version + '_first_failed'] = failed[0] if failed else 'pass'
            migration.append(row)
    station.table(out / 'truth_accepted_migration_events.tsv', migration)
    channels = ['Veto20', 'Veto21', 'Preshower0', 'Preshower1', 'VetoNu0_reduced',
                'VetoNu1_reduced', 'Timing0', 'Timing1', 'Timing2', 'Timing3']
    charge_rows = []
    for version in ('strict', 'latest'):
        for name, group in [('fiducial', masks['fiducial']), ('accepted', masks['truth_station_acceptance'])]:
            for j, channel in enumerate(channels):
                a, b = data['old']['scintillator'][group, j], data[version]['scintillator'][group, j]
                equal = (a == b) | (np.isnan(a) & np.isnan(b))
                finite = np.isfinite(a) & np.isfinite(b)
                charge_rows.append(dict(version=version, population=name, channel=channel, events=len(a),
                    exact_old_events=int(equal.sum()), nonfinite=int((~np.isfinite(b)).sum()),
                    finite_negative=int((np.isfinite(b) & (b < 0)).sum()),
                    maximum_finite_difference_pc=float(np.max(np.abs(a[finite]-b[finite]))) if finite.any() else None))
    station.table(out / 'waveform_comparison.tsv', charge_rows)
    fixed = out / 'fixed_old_charge'
    fixed.mkdir(exist_ok=True)
    fixed_data, fixed_der = {}, {}
    for v, a in data.items():
        fixed_data[v] = dict(a)
        fixed_data[v]['event_cut_bits'] = (der[v]['control'].astype(np.uint16) << np.arange(14, dtype=np.uint16)).sum(axis=2).astype(np.uint16)
        fixed_der[v] = dict(der[v], final=der[v]['control'][:, :, -1])
    station.basic_metrics(fixed_data, fixed_der, fixed, groups, masks, cuts)
    station.response_metrics(fixed_data, fixed_der, fixed, groups, masks, comparisons, only_final=True)
    station.particle_content(fixed_data, fixed_der, groups, fixed)
    station.performance_summary(audit, out)
    (out / 'source_audit.json').write_text(json.dumps(audit, indent=2) + '\n')
    (out / 'runtime_source_provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    (out / 'effective_configuration.json').write_text(json.dumps(configurations[0], indent=2) + '\n')
    if paired_audit:
        (out / 'paired_old_replay.json').write_text(json.dumps(paired_audit, indent=2) + '\n')
    summary = dict(versions=list(data), source_commit=provenance['commit'], common_events=len(latest['all_run']), fiducial=len(latest['run']),
        accepted=int(masks['truth_station_acceptance'].sum()), full_sample=not args.partial,
        exact_truth=True, exact_all_ids=not args.partial, exact_shard_science_readback=True,
        checked_shards=len(records), exact_old_waveforms=bool(np.array_equal(latest['scintillator'], data['old']['scintillator'], equal_nan=True)),
        final_counts={v: der[v]['final'].sum(axis=0).tolist() for v in data},
        accepted_final_counts={v: der[v]['final'][masks['truth_station_acceptance']].sum(axis=0).tolist() for v in data},
        station_reference='SiHit direction times HepMC production momentum magnitude; G4 local momentum unavailable',
        baseline_scope='old and strict reused validated full caches; latest newly reconstructed',
        wall_s=time.monotonic()-start, max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
