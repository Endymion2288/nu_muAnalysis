#!/usr/bin/env python3
"""Paired old / rotated-large / rotated-small reconstruction comparison."""
import argparse
import json
import math
from pathlib import Path
import resource
import time

import numpy as np
from compare_tracking import MODES, selection
import report_tracking_station as station
import report_tracking_material as material
from report_tracking_ablation import event_key, ordered, subset
from report_tracking_master_integration import load, paired_momentum_bands


def paired_track_properties(data, der, masks, comparisons, output):
    rows = []
    for left, right in comparisons:
        for m, mode in enumerate(MODES):
            indices, correct = {}, {}
            for version in [left, right]:
                d = der[version]; leader = d['leaders'][:, m]; li = np.maximum(leader, 0)
                indices[version] = li
                correct[version] = (leader >= 0) & d['primary'][li] & (d['purity'][li] >= .7)
            common = masks['truth_station_acceptance'] & correct[left] & correct[right]
            for scope, selected in dict(common_primary_leaders=common,
                    both_final_correct=common & der[left]['final'][:, m] & der[right]['final'][:, m]).items():
                il, ir = indices[left][selected], indices[right][selected]
                lc, rc = der[left]['col'], der[right]['col']
                lcharge, rcharge = lc['charge'][il], rc['charge'][ir]
                expected = -np.sign(lc['pdg'][il])
                row = dict(baseline=left, variant=right, mode=mode, scope=scope, pairs=len(il),
                    charge_disagreements=int((lcharge != rcharge).sum()),
                    baseline_wrong_charge=int((lcharge != expected).sum()),
                    variant_wrong_charge=int((rcharge != expected).sum()),
                    wrong_to_right_charge=int(((lcharge != expected) & (rcharge == expected)).sum()),
                    right_to_wrong_charge=int(((lcharge == expected) & (rcharge != expected)).sum()))
                for name in ['measurements', 'layers', 'ndof']:
                    x, y = lc[name][il], rc[name][ir]
                    row.update({name + '_fewer': int((y < x).sum()), name + '_equal': int((y == x).sum()),
                        name + '_more': int((y > x).sum()), name + '_mean_delta': float((y-x).mean()) if len(x) else np.nan})
                # The uncut leader cohort includes ndof=0; retain nonfinite ratios.
                # Final-track numerical validity is audited separately.
                with np.errstate(divide='ignore', invalid='ignore'):
                    x, y = lc['chi2'][il] / lc['ndof'][il], rc['chi2'][ir] / rc['ndof'][ir]
                row['baseline_median_chi2_ndof'] = float(np.median(x)) if len(x) else np.nan
                row['variant_median_chi2_ndof'] = float(np.median(y)) if len(y) else np.nan
                rows.append(row)
    station.table(output / 'paired_track_properties.tsv', rows)


def momentum_tails_and_common_bands(data, der, masks, output):
    tails, extremes, bands, final_accuracy = [], [], [], []
    for m, mode in enumerate(MODES):
        for st in range(3):
            errors, signed_errors, corrects = {}, {}, {}
            t = data['old']['primary_station'][:, st, 5] / 1000
            for version, a in data.items():
                d = der[version]; leader = d['leaders'][:, m]; li = np.maximum(leader, 0)
                correct = (leader >= 0) & d['primary'][li] & (d['purity'][li] >= .7)
                p = a['reco_at_primary_station'][li, st, 5] / 1000
                with np.errstate(invalid='ignore', divide='ignore'):
                    signed_error = p / t - 1
                    error = abs(signed_error)
                valid = correct & np.isfinite(error) & (t > 0)
                errors[version] = error; signed_errors[version] = signed_error; corrects[version] = valid
                scopes = dict(accepted_matched_leader=valid & masks['truth_station_acceptance'],
                    accepted_final_correct=valid & masks['truth_station_acceptance'] & d['final'][:, m],
                    fiducial_final_correct=valid & d['final'][:, m])
                for scope, selected in scopes.items():
                    y = error[selected]
                    tails.append(dict(version=version, mode=mode, station=st+1, scope=scope,
                        pairs=len(y), median=float(np.median(y)) if len(y) else np.nan,
                        q95=float(np.quantile(y, .95)) if len(y) else np.nan,
                        q99=float(np.quantile(y, .99)) if len(y) else np.nan,
                        mean=float(y.mean()) if len(y) else np.nan,
                        maximum=float(y.max()) if len(y) else np.nan,
                        error_gt_half=int((y > .5).sum()), error_gt_one=int((y > 1).sum()),
                        error_gt_ten=int((y > 10).sum()), error_gt_thousand=int((y > 1000).sum())))
                    if scope != 'accepted_final_correct':
                        continue
                    for i in np.flatnonzero(selected & (error > 10)):
                        extremes.append(dict(version=version, mode=mode, station=st+1,
                            run=int(a['run'][i]), eventID=int(a['eventID'][i]),
                            reference_pz_gev=float(t[i]), reco_pz_gev=float(p[i]),
                            absolute_relative_error=float(error[i]),
                            chi2=float(d['col']['chi2'][li[i]]), ndof=float(d['col']['ndof'][li[i]]),
                            layers=float(d['col']['layers'][li[i]]), purity=float(d['purity'][li[i]])))
            common = masks['truth_station_acceptance'] & np.logical_and.reduce(list(corrects.values()))
            common_final = common & np.logical_and.reduce([d['final'][:, m] for d in der.values()])
            for group, population in [('all', np.ones(len(t), bool)), ('nominal', data['old']['run'] != 200080)]:
                for version, error in signed_errors.items():
                    final_accuracy.append(dict(version=version, group=group, mode=mode, station=st+1,
                        **station.residual_summary(error[common_final & population])))
                for scope, cohort in [('common_primary_leaders', common), ('all_final_correct', common_final)]:
                    for lo, hi in zip([100, 300, 1000, 3000], [300, 1000, 3000, np.inf]):
                        selected = cohort & population & (t >= lo) & (t < hi)
                        for version, error in errors.items():
                            y = error[selected]
                            bands.append(dict(version=version, group=group, mode=mode, station=st+1, scope=scope,
                                low_gev=lo, high_gev=hi, common_pairs=len(y),
                                median_absolute=float(np.median(y)) if len(y) else np.nan,
                                q95=float(np.quantile(y, .95)) if len(y) else np.nan,
                                tail_gt_half=int((y > .5).sum())))
    station.table(output / 'momentum_tail_audit.tsv', tails)
    station.table(output / 'extreme_momentum_events.tsv', extremes)
    station.table(output / 'three_way_momentum_bands.tsv', bands)
    station.table(output / 'three_way_final_station_accuracy.tsv', final_accuracy)


def version_loss_causes(data, der, masks, comparisons, cuts, output):
    rows, first, events = [], [], []
    for left, right in comparisons:
        for m, mode in enumerate(MODES):
            correct = {}
            for version in [left, right]:
                d = der[version]; leader = d['leaders'][:, m]; li = np.maximum(leader, 0)
                correct[version] = (leader >= 0) & d['primary'][li] & (d['purity'][li] >= .7)
            for migration, source, dest in [('lost', left, right), ('gained', right, left)]:
                selected = masks['truth_station_acceptance'] & der[source]['final'][:, m] & ~der[dest]['final'][:, m]
                c = data[dest]['raw_primary_counts'][:, m]
                category = np.full(len(selected), 'source_wrong_or_low_purity', dtype='U60')
                category[correct[source]] = 'leader_changed_or_low_purity'
                category[correct[source] & correct[dest]] = 'both_correct_leaders'
                category[correct[source] & (c[:, 1] == 0) & (c[:, 0] > 0)] = 'primary_raw_only'
                category[correct[source] & (c[:, 0] == 0)] = 'no_primary_raw'
                failed = np.argmax(~der[dest]['raw'][:, m], axis=1)
                for name in np.unique(category[selected]):
                    rows.append(dict(baseline=left, variant=right, mode=mode, migration=migration,
                        category=name, events=int((selected & (category == name)).sum()), total=int(selected.sum())))
                for j, cut in enumerate(cuts):
                    first.append(dict(baseline=left, variant=right, mode=mode, migration=migration,
                        first_failed_cut=cut, events=int((selected & (failed == j)).sum()), total=int(selected.sum())))
                for i in np.flatnonzero(selected):
                    events.append(dict(baseline=left, variant=right, mode=mode, migration=migration,
                        run=int(data[source]['run'][i]), eventID=int(data[source]['eventID'][i]),
                        source_primary=bool(correct[source][i]), dest_primary=bool(correct[dest][i]),
                        category=str(category[i]), first_failed_cut=cuts[failed[i]]))
    station.table(output / 'version_loss_causes.tsv', rows)
    station.table(output / 'version_first_failed.tsv', first)
    station.table(output / 'version_migration_events.tsv', events)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--partial', action='store_true')
    args = parser.parse_args(); start = time.monotonic(); out = args.output
    out.mkdir(parents=True, exist_ok=True)
    records = [r.split('\t') for r in args.manifest.read_text().splitlines() if r.split('\t')[6] == 'small']
    small, audit = station.combine(records, 'new', out)
    (out / 'new.npz').rename(out / 'small.npz')
    data = dict(old=load(args.repo / 'workbook/stage203_station_truth/old.npz'),
                large=load(args.repo / 'workbook/stage208_master_integration/full/latest.npz'), small=small)
    if args.partial:
        for v in ['old', 'large']:
            data[v] = subset(data[v], event_key(small))
    immutable = ['run', 'eventID', 'truth_pz_nu', 'truth_dec_x_nu', 'truth_dec_y_nu', 'truth_dec_z_nu',
                 'primary', 'primary_production_momentum_mev', 'primary_station', 'primary_layer_hits', 'scintillator']
    for v, a in data.items():
        for key in immutable:
            assert np.array_equal(a[key], data['old'][key], equal_nan=a[key].dtype.kind in 'fc'), (v, key)
        if not args.partial:
            for key in ['all_run', 'all_eventID']:
                assert np.array_equal(a[key], data['old'][key]), (v, key)
    configuration = None; provenance = None; counts = []
    for record, row in zip(records, audit):
        row['version'] = 'small'
        config = json.loads(row.pop('effective_reco'))
        assert config['variance'] == 'small' and config['initial_variance_inflation'] == [100, 100, 100, 100, 1000]
        assert config['exact_strict_map'] and len(config['algorithms']) == 4
        for alg in config['algorithms'].values():
            assert alg['isolated_smoothing']
            assert math.isclose(alg['seed_covariance']['covTheta'], 8.41e-6, rel_tol=1e-12)
            assert math.isclose(alg['seed_covariance']['covQOverP'], 1e-5, rel_tol=1e-12)
        config['material_file'] = 'packaged strict rowmajor rotated material'
        if configuration is not None:
            assert configuration == config, ('configuration drift', record[0])
        configuration = config
        shard = ordered(load(record[5])); restored = subset(small, event_key(shard))
        for key in station.EVENT_KEYS + station.TRACK_KEYS:
            assert np.array_equal(shard[key], restored[key], equal_nan=shard[key].dtype.kind in 'fc'), (record[0], key)
        source = json.loads(str(shard['integration_provenance_json']))
        assert source['commit'] == '7fd40df8cd3b60e81b4095a4f84310c4a54700a0'
        if provenance is not None:
            assert provenance == source
        provenance = source; counts.append(shard['counts'])
    totals = np.sum(counts, axis=0)
    assert np.array_equal(totals[:, 6], np.full(3, len(small['run'])))
    if not args.partial:
        assert len(small['all_run']) == 3374987 and len(small['run']) == 383670
        assert np.array_equal(totals[:, :7], np.tile(
            [3374987, 3374987, 2559272, 2186815, 883318, 418248, 383670], (3, 1)))
    masks = material.truth_masks(data['old'])
    if not args.partial:
        assert masks['truth_station_acceptance'].sum() == 140132
    groups = dict(all=np.ones(len(small['run']), bool), nominal=small['run'] != 200080)
    groups.update({str(r): small['run'] == r for r in np.unique(small['run'])})
    der = {v: station.derived(a) for v, a in data.items()}
    for v, a in data.items():
        der[v]['control'] = station.controlled(a, data['old'])
        assert np.array_equal(der[v]['control'], ((a['event_cut_bits'][:, :, None] >> np.arange(14)) & 1).astype(bool)), v
    comparisons = [('old', 'large'), ('old', 'small'), ('large', 'small')]
    cuts = [name for name, _ in selection(args.repo)[0]][6:]
    cutflow = []
    for v, a in data.items():
        for m, mode in enumerate(MODES):
            for j, name in enumerate(['NoCuts'] + [name for name, _ in selection(args.repo)[0]]):
                n = int(totals[m, j]) if j <= 6 else int(((a['event_cut_bits'][:, m] >> (j - 7)) & 1).sum())
                if v == 'small':
                    assert n == totals[m, j]
                cutflow.append(dict(version=v, mode=mode, cut=name, passed=n, initial=int(totals[m, 0]),
                    source='common RDO truth cuts measured in small' if j <= 6 else 'version cumulative event bits'))
    station.table(out / 'full_input_cutflow.tsv', cutflow)
    station.basic_metrics(data, der, out, groups, masks, cuts)
    residuals, bins = station.response_metrics(data, der, out, groups, masks, comparisons)
    station.particle_content(data, der, groups, out)
    station.local_cut_migrations(data, der, groups, out)
    material.duplicates(data, der, groups, masks, out)
    material.selection_pairs(data, der, groups, masks, comparisons, out)
    material.mode_migrations(data, der, groups, masks, cuts, out)
    material.spectra(data, der, masks, out)
    material.common_cohort(data, der, masks, out)
    paired_momentum_bands(data, der, masks, out, comparisons)
    paired_track_properties(data, der, masks, comparisons, out)
    momentum_tails_and_common_bands(data, der, masks, out)
    version_loss_causes(data, der, masks, comparisons, cuts, out)
    station.plots(data, der, out, masks, residuals, bins)
    station.performance_summary(audit, out)
    (out / 'source_audit.json').write_text(json.dumps(audit, indent=2) + '\n')
    (out / 'effective_configuration.json').write_text(json.dumps(configuration, indent=2) + '\n')
    (out / 'runtime_provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    result = dict(full_sample=not args.partial, versions=list(data), checked_shards=len(records),
        input_events=int(totals[0, 0]), fiducial=len(small['run']), accepted=int(masks['truth_station_acceptance'].sum()),
        source_commit=provenance['commit'], exact_truth_and_waveforms=True,
        exact_all_input_ids=not args.partial, exact_shard_readback=True,
        accepted_final={v: der[v]['final'][masks['truth_station_acceptance']].sum(axis=0).tolist() for v in data},
        accepted_final_correct={}, station_reference='SiHit direction times HepMC production momentum magnitude; no G4 local momentum',
        wall_s=time.monotonic()-start, max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    for v, d in der.items():
        values = []
        for m in range(3):
            l = d['leaders'][:, m]; li = np.maximum(l, 0)
            correct = (l >= 0) & d['primary'][li] & (d['purity'][li] >= .7)
            values.append(int((masks['truth_station_acceptance'] & d['final'][:, m] & correct).sum()))
        result['accepted_final_correct'][v] = values
    (out / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
