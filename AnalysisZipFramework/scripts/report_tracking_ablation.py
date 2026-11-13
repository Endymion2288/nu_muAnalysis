#!/usr/bin/env python3
"""Paired GENIE ablations, retaining losses as well as conditional momentum response."""
import argparse
import csv
import json
from pathlib import Path
import resource
import re
import time

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import binomtest
from report_tracking_station import EVENT_KEYS, TRACK_KEYS, derived, controlled
from extract_tracking_station import SCALARS
from compare_tracking import MODES, selection


def table(path, rows):
    if not rows:
        return
    with path.open('w') as f:
        writer = csv.DictWriter(f, list(rows[0]), delimiter='\t', lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def event_key(a):
    return a['run'].astype(np.int64) * 1000000000 + a['eventID'].astype(np.int64)


def ordered(a):
    order = np.argsort(event_key(a))
    inverse = np.empty(len(order), int)
    inverse[order] = np.arange(len(order))
    for k in EVENT_KEYS:
        a[k] = a[k][order]
    a['tracks'][:, 0] = inverse[a['tracks'][:, 0].astype(int)]
    order = np.lexsort((a['tracks'][:, 2], a['tracks'][:, 1], a['tracks'][:, 0]))
    for k in TRACK_KEYS:
        a[k] = a[k][order]
    assert len(np.unique(event_key(a))) == len(a['run'])
    return a


def subset(a, ids):
    keep = np.isin(event_key(a), ids)
    inverse = np.full(len(keep), -1, int)
    inverse[keep] = np.arange(keep.sum())
    track = keep[a['tracks'][:, 0].astype(int)]
    out = {k: a[k][keep].copy() for k in EVENT_KEYS}
    out.update({k: a[k][track].copy() for k in TRACK_KEYS})
    out['tracks'][:, 0] = inverse[out['tracks'][:, 0].astype(int)]
    return out


def load_cache(path):
    with np.load(path) as f:
        return {k: f[k] for k in EVENT_KEYS + TRACK_KEYS}


def full_selection_audit(repo, output):
    """Full stage203 inputs: conditional charge replacement, without a new reco run."""
    keys = ['event_individual_bits', 'event_cut_bits', 'event_scalars', 'scintillator',
            'run', 'primary', 'primary_station', 'primary_layer_hits']
    caches = {}
    for v in ['old', 'new']:
        with np.load(repo / f'workbook/stage203_station_truth/{v}.npz') as f:
            caches[v] = {k: f[k] for k in keys}
    old, new = caches['old'], caches['new']
    t = old['primary_station']
    accepted = (old['primary'][:, 2] == 1) & np.isfinite(t).all(axis=(1, 2)) & (t[:, :, 5] > 100000).all(axis=1)
    accepted &= (np.linalg.norm(t[:, :, :2], axis=2) < 95).all(axis=1)
    accepted &= (1000*np.arctan2(np.linalg.norm(t[:, :, 3:5], axis=2), t[:, :, 5]) < 25).all(axis=1)
    accepted &= (old['primary_layer_hits'] > 0).sum(axis=1) >= 7
    fixed = controlled(new, old)[:, :, -1]
    rows = []; wave = []
    for m, mode in enumerate(MODES):
        oldpass = old['event_cut_bits'][:, m] == 16383
        newpass = new['event_cut_bits'][:, m] == 16383
        for group, den in [('fiducial', np.ones(len(accepted), bool)), ('truth_accepted', accepted)]:
            for name, before, after in [('old_to_native', oldpass, newpass),
                ('old_to_new_fixed_old_charge', oldpass, fixed[:, m]),
                ('native_to_fixed_old_charge', newpass, fixed[:, m])]:
                row = dict(group=group, mode=mode, control=name)
                row.update(paired_binary(before, after, den)); rows.append(row)
    for j, name in enumerate(['Veto20', 'Veto21', 'Preshower0', 'Preshower1', 'VetoNu0_reduced', 'VetoNu1_reduced']):
        a = old['scintillator'][:, j]; b = new['scintillator'][:, j]
        for group, den in [('fiducial', np.ones(len(accepted), bool)), ('truth_accepted', accepted)]:
            threshold = 2.5 if j in [2, 3] else 40 if j in [0, 1] else 30
            before = a > threshold if j < 4 else a < threshold
            after = b > threshold if j < 4 else b < threshold
            row = dict(group=group, channel=name, threshold_pc=threshold,
                old_median_pc=float(np.median(a[den])), new_median_pc=float(np.median(b[den])),
                old_positive_new_nonpositive=int((den & (a > 0) & (b <= 0)).sum()),
                old_nonfinite=int((den & ~np.isfinite(a)).sum()),new_nonfinite=int((den & ~np.isfinite(b)).sum()),
                old_positive_new_negative_finite=int((den & (a > 0) & (b < 0) & np.isfinite(b)).sum()))
            row.update(paired_binary(before, after, den)); wave.append(row)
    table(output / 'full_selection_decomposition.tsv', rows)
    table(output / 'full_scintillator_migrations.tsv', wave)


def combine(rows, variant):
    arrays = {k: [] for k in EVENT_KEYS + TRACK_KEYS}
    audit = []
    offset = 0
    for row in rows:
        if row[1] != variant:
            continue
        path = Path(row[5].replace('/eos/user/x/xcheng/', '/eos/home-x/xcheng/'))
        with np.load(path) as f:
            assert str(f['variant']) == variant and int(f['manifest_index']) == int(row[0])
            for k in arrays:
                v = f[k].copy()
                if k == 'tracks':
                    v[:, 0] += offset
                arrays[k].append(v)
            offset += len(f['run'])
            audit.append(dict(index=int(row[0]), variant=variant, skip=int(row[4]), nevents=int(row[3]),
                events=int(f['counts'][0, 0]), truth=len(f['run']), checked=int(f['official_long_matches_checked']),
                performance=json.loads(str(f['performance_json'])), effective=str(f['effective_ablation_json']),
                bytes=path.stat().st_size, path=str(path), host=str(f['host'])))
    return ordered({k: np.concatenate(v) for k, v in arrays.items()}), audit


def paired_binary(before, after, denominator):
    n = int(denominator.sum())
    lost = int((denominator & before & ~after).sum())
    gained = int((denominator & ~before & after).sum())
    delta = (gained - lost) / n if n else np.nan
    se = np.sqrt(max(0, (lost + gained) / n - delta**2) / n) if n else np.nan
    return dict(denominator=n, before=int((before & denominator).sum()), after=int((after & denominator).sum()),
        lost=lost, gained=gained, delta_pp=100*delta, paired_se_pp=100*se,
        low95_pp=100*(delta-1.96*se), high95_pp=100*(delta+1.96*se),
        mcnemar_p=binomtest(gained, gained+lost).pvalue if gained+lost else 1.)


def smoothing_audit(native, shared, accepted, output):
    """Retain changed states sampled at primary truth stations, including tails."""
    assert np.array_equal(native['tracks'], shared['tracks'], equal_nan=True)
    d = derived(native)
    x = native['reco_at_primary_station']; y = shared['reco_at_primary_station']
    changed = ~((x == y) | (np.isnan(x) & np.isnan(y))).all(axis=2)
    records = []
    for i, station in zip(*np.nonzero(changed)):
        event = d['idx'][i]
        primary = bool(d['primary'][i] and d['purity'][i] >= .7)
        truth = native['primary_station'][event, station, 5]
        residual = lambda value: value / truth - 1 if primary and np.isfinite(truth) and truth > 0 else np.nan
        records.append(dict(run=int(native['run'][event]), event=int(native['eventID'][event]),
            mode=MODES[int(d['col']['mode'][i])], station=int(station+1), track_row=int(i),
            primary=primary, leader=bool(d['col']['leader'][i]), truth_accepted=bool(accepted[event]),
            native_final=bool(native['event_cut_bits'][event, int(d['col']['mode'][i])] == 16383),
            truth_pz_mev=float(truth), isolated_pz_mev=float(x[i,station,5]),
            shared_pz_mev=float(y[i,station,5]),
            isolated_relative_pz=residual(x[i,station,5]), shared_relative_pz=residual(y[i,station,5])))
    table(output / 'smoothing_changed_states.tsv', records)


def main():
    start = time.monotonic()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, required=True)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--validate-baselines', action='store_true')
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rows = [line.split('\t') for line in args.manifest.read_text().splitlines()]
    variants = list(dict.fromkeys(r[1] for r in rows))
    data = {}; audit = []
    for v in variants:
        data[v], records = combine(rows, v)
        audit += records
    assert 'native' in data
    ids = event_key(data['native'])
    baseline_checks = []
    for v, version in [('old', 'old'), ('native', 'new')]:
        cache = subset(load_cache(args.repo / f'workbook/stage203_station_truth/{version}.npz'), ids)
        if v not in data:
            data[v] = cache
        if args.validate_baselines:
            for k in EVENT_KEYS + TRACK_KEYS:
                assert np.array_equal(data[v][k], cache[k], equal_nan=cache[k].dtype.kind in 'fc'), (v, k)
            baseline_checks.append(dict(variant=v, all_columns_exact=True, events=len(ids), tracks=len(cache['tracks'])))
    truth_keys = ['run', 'eventID', 'primary', 'primary_station', 'primary_production_momentum_mev', 'primary_layer_hits']
    for v, a in data.items():
        for k in truth_keys:
            assert np.array_equal(a[k], data['old'][k], equal_nan=a[k].dtype.kind in 'fc'), (v, k)
        if v != 'old':
            assert np.array_equal(a['scintillator'], data['native']['scintillator'], equal_nan=True), (v, 'waveform drift')
        np.savez_compressed(args.output / (v+'.npz'), **a)
        with np.load(args.output / (v+'.npz')) as f:
            for k, x in a.items():
                assert np.array_equal(x, f[k], equal_nan=x.dtype.kind in 'fc'), (v, k)
    for row in rows:
        path = Path(row[5].replace('/eos/user/x/xcheng/', '/eos/home-x/xcheng/'))
        source = ordered(load_cache(path))
        restored = subset(data[row[1]], event_key(source))
        for k, x in source.items():
            assert np.array_equal(x, restored[k], equal_nan=x.dtype.kind in 'fc'), ('shard readback',row[1],row[0],k)
    old = data['old']
    t = old['primary_station']
    accepted = (old['primary'][:, 2] == 1) & np.isfinite(t).all(axis=(1, 2)) & (t[:, :, 5] > 100000).all(axis=1)
    accepted &= (np.linalg.norm(t[:, :, :2], axis=2) < 95).all(axis=1)
    accepted &= (1000*np.arctan2(np.linalg.norm(t[:, :, 3:5], axis=2), t[:, :, 5]) < 25).all(axis=1)
    accepted &= (old['primary_layer_hits'] > 0).sum(axis=1) >= 7
    masks = dict(fiducial=np.ones(len(ids), bool), truth_accepted=accepted)
    # These run-based subsets test the nominal samples separately from DSID200080.
    masks['truth_accepted_without200080'] = accepted & (old['run'] != 200080)
    der = {v: derived(a) for v, a in data.items()}
    metrics = []; cutrows = []; momentum = []; pairs = []; duplicates = []; residual = {}; stages = {}; corrects = {}
    cutnames = [name for name, _ in selection(args.repo)[0]][6:]
    for v, a in data.items():
        d = der[v]; d['fixed'] = controlled(a, old)
        residual[v] = {}; stages[v] = {}; corrects[v] = {}
        for m, mode in enumerate(MODES):
            leader = d['leaders'][:, m]; li = np.maximum(leader, 0); has = leader >= 0
            correct = has & d['primary'][li] & (d['purity'][li] >= .7)
            corrects[v][mode] = correct
            charge = correct & (d['col']['charge'][li] * a['primary'][:, 1] > 0)
            s = dict(any_primary=a['raw_primary_counts'][:, m, 0] > 0,
                primary_long=a['raw_primary_counts'][:, m, 1] > 0,
                primary_quality=a['raw_primary_counts'][:, m, 2] > 0,
                has_long=has, correct_leader=correct, track_cuts=d['track_pass'][:, m],
                final=d['final'][:, m], fixed_final=d['fixed'][:, m, -1],
                fixed_correct=d['fixed'][:, m, -1] & correct, wrong_sign=charge)
            stages[v][mode] = s
            for scope, quality in [('long', np.ones(len(a['tracks']), bool)), ('quality', d['quality'])]:
                for threshold in [.5, .7, .9]:
                    chosen = (d['col']['mode'] == m) & quality & (d['col']['barcode'] != 0) & (d['purity'] >= threshold)
                    truth_pairs = np.column_stack([d['idx'][chosen], d['col']['barcode'][chosen].astype(np.int64)])
                    unique_pairs, number = np.unique(truth_pairs, axis=0, return_counts=True)
                    for group, denominator in masks.items():
                        inside = denominator[unique_pairs[:, 0]] if len(unique_pairs) else np.array([], bool)
                        dup = inside & (number > 1)
                        duplicates.append(dict(variant=v, mode=mode, scope=scope, purity_threshold=threshold,
                            group=group, denominator=int(denominator.sum()),
                            matched_tracks=int(number[inside].sum()), truth_groups=int(inside.sum()),
                            duplicate_groups=int(dup.sum()), excess_tracks=int((number[dup]-1).sum()),
                            duplicate_events=len(np.unique(unique_pairs[dup, 0]))))
            for group, denominator in masks.items():
                for name, passed in s.items():
                    metrics.append(dict(variant=v, mode=mode, group=group, stage=name,
                        denominator=int(denominator.sum()), passed=int((denominator & passed).sum())))
                count = a['raw_primary_counts'][:, m, 1]
                metrics.append(dict(variant=v, mode=mode, group=group, stage='multiple_primary_long',
                    denominator=int(denominator.sum()), passed=int((denominator & (count > 1)).sum())))
            for j, name in enumerate(cutnames):
                before = np.ones(len(ids), bool) if j == 0 else d['fixed'][:, m, j-1]
                fail = accepted & before & ~d['fixed'][:, m, j]
                cutrows.append(dict(variant=v, mode=mode, cut=name, failed=int(fail.sum())))
            for station in range(3):
                r = np.full(len(ids), np.nan)
                reco = a['reco_at_primary_station'][li, station, 5]
                valid = correct & np.isfinite(reco) & np.isfinite(t[:, station, 5]) & (t[:, station, 5] > 0)
                r[valid] = reco[valid] / t[valid, station, 5] - 1
                residual[v][mode, station] = r
                for scope, sel in [('primary_leader', valid), ('fixed_final', valid & s['fixed_final'])]:
                    x = r[sel]
                    q = np.quantile(x, [.16, .5, .84]) if len(x) else [np.nan]*3
                    momentum.append(dict(variant=v, mode=mode, station=station+1, scope=scope, n=len(x),
                        median_abs_relative_percent=100*np.median(abs(x)) if len(x) else np.nan,
                        residual_q16_percent=100*q[0], residual_median_percent=100*q[1], residual_q84_percent=100*q[2],
                        within10=int((abs(x) < .1).sum()), within20=int((abs(x) < .2).sum()),
                        below_half=int((x < -.5).sum()), above_double=int((x > 1).sum())))
    for v in data:
        if v == 'old':
            continue
        for base in ['old', 'native']:
            if v == base:
                continue
            for mode in MODES:
                for name in stages[v][mode]:
                    for group, denominator in masks.items():
                        row = dict(baseline=base, variant=v, mode=mode, stage=name, group=group)
                        row.update(paired_binary(stages[base][mode][name], stages[v][mode][name], denominator))
                        pairs.append(row)
    accuracy = []; rng = np.random.default_rng(204)
    for v in data:
        if v == 'old':
            continue
        for base in ['old', 'native']:
            if v == base:
                continue
            for mode in MODES:
                for station in range(3):
                    x = residual[base][mode, station]; y = residual[v][mode, station]
                    for scope, scope_mask in [('primary_leader', np.ones(len(ids), bool)),
                        ('both_fixed_final', stages[base][mode]['fixed_final'] & stages[v][mode]['fixed_final'])]:
                        common = np.isfinite(x) & np.isfinite(y) & scope_mask
                        a = abs(x[common]); b = abs(y[common]); n = len(a)
                        delta = []
                        if n:
                            for _ in range(400):
                                sample = rng.integers(n, size=n)
                                delta.append(100*(np.median(b[sample])-np.median(a[sample])))
                        q = np.quantile(delta, [.025, .975]) if n else [np.nan]*2
                        accuracy.append(dict(baseline=base, variant=v, mode=mode, station=station+1, scope=scope, n=n,
                            old_median_abs_percent=100*np.median(a) if n else np.nan,
                            new_median_abs_percent=100*np.median(b) if n else np.nan,
                            median_delta95_low_pp=q[0], median_delta95_high_pp=q[1],
                            improved=int((b < a).sum()), worsened=int((b > a).sum())))
    for name, values in [('metrics', metrics), ('first_failed_cut_fixed', cutrows), ('station_response', momentum),
                         ('paired_efficiency', pairs), ('paired_accuracy', accuracy), ('duplicates', duplicates)]:
        table(args.output / (name+'.tsv'), values)
    full_selection_audit(args.repo, args.output)
    configurations = {}
    for row in audit:
        text = row.pop('effective')
        config = json.loads(text) if text.startswith('{') else text
        if isinstance(config, dict) and 'geometry' in config:
            material = config['geometry'].get('MaterialMapInputFile', '')
            if 'material-rotated.json' in material:
                row['material_runtime_file'] = material
                config['geometry']['MaterialMapInputFile'] = 'material-rotated.json (worker scratch)'
        key = row['variant']
        if key in configurations:
            assert configurations[key] == config, ('configuration drift', key, row['index'])
        else:
            configurations[key] = config
        row['effective_key'] = key
    (args.output / 'effective_configurations.json').write_text(json.dumps(configurations, indent=2)+'\n')
    (args.output / 'files.json').write_text(json.dumps(audit, indent=2)+'\n')
    invariance = {}
    for variant in ['shared','reset']:
        if variant not in data: continue
        invariance[variant] = {}
        for key in EVENT_KEYS + TRACK_KEYS:
            a = data['native'][key]; b = data[variant][key]
            record = dict(native_shape=list(a.shape),variant_shape=list(b.shape))
            if a.shape == b.shape:
                equal = (a == b) | (np.isnan(a) & np.isnan(b)) if a.dtype.kind in 'fc' else a == b
                record['different_rows'] = int((~equal.reshape(len(a),-1).all(axis=1)).sum()) if len(a) else 0
                record['exact'] = bool(equal.all())
            invariance[variant][key] = record
    (args.output / 'invariance.json').write_text(json.dumps(invariance,indent=2)+'\n')
    if 'shared' in data:
        smoothing_audit(data['native'], data['shared'], accepted, args.output)
    performance = []
    for row in audit:
        for stage, line in row['performance'].items():
            numbers = {k:float(v) for k,v in re.findall(r'(wall_seconds|max_rss_kib|user_seconds|system_seconds)=([0-9.]+)',line)}
            performance.append(dict(variant=row['variant'],index=row['index'],stage=stage,events=row['events'],
                **numbers,events_per_wall_second=row['events']/numbers['wall_seconds'] if numbers.get('wall_seconds',0)>0 else np.nan))
    table(args.output / 'performance.tsv',performance)
    validation = dict(baselines=baseline_checks, common_truth=len(ids), accepted=int(accepted.sum()),
        variants=list(data), shards=len(rows), exact_truth=True, exact_cache_readback=True, exact_shard_readback=True,
        exact_waveform_arrays_across_tracking_controls=True,
        source_events_by_variant={v:sum(r['events'] for r in audit if r['variant']==v) for v in variants},
        full_g4_local_momentum_measured=False, wall_s=time.monotonic()-start,
        max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    (args.output / 'validation.json').write_text(json.dumps(validation, indent=2)+'\n')
    fig, ax = plt.subplots(1, 2, figsize=(13, 5), constrained_layout=True)
    labels = list(data)
    for m, mode in enumerate(MODES):
        values = []
        for v in labels:
            values.append(100*np.mean(stages[v][mode]['fixed_correct'][accepted]))
        ax[0].plot(labels, values, 'o-', label=mode)
    for v in labels:
        r = residual[v]['merge', 0]; r = r[np.isfinite(r)]
        ax[1].hist(r, bins=np.linspace(-1, 1, 101), density=True, histtype='step', label=v)
    ax[0].set_ylabel('Correct final efficiency [%]\n(truth acceptance, old charges)')
    ax[0].tick_params(axis='x', rotation=65); ax[0].legend()
    ax[1].set_xlabel('Station 1 pz / reference pz - 1 (matched primary leaders)')
    ax[1].set_ylabel('Density within displayed range'); ax[1].legend(fontsize=7)
    fig.savefig(args.output / 'controls.svg')
    fig.savefig(args.output / 'controls.png',dpi=150)
    plt.close(fig)
    main_variants = [v for v in ['old','native','material','material_oldprior'] if v in data]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4), constrained_layout=True)
    plot_rows = []
    for station, ax in enumerate(axes):
        common = np.logical_and.reduce([np.isfinite(residual[v]['merge',station]) for v in main_variants])
        for v in main_variants:
            x = np.sort(abs(residual[v]['merge',station][common]))
            ax.step(100*x,np.arange(1,len(x)+1)/len(x),where='post',label=v)
            plot_rows.append(dict(variant=v,station=station+1,mode='merge',common_events=len(x),median_abs_percent=100*np.median(x)))
        ax.set_xscale('log');ax.set_xlim(.1,300);ax.set_ylim(0,1)
        ax.set_xlabel(f'Station {station+1} absolute relative pz error [%]')
        ax.grid(alpha=.2)
    axes[0].set_ylabel('Fraction of common primary leaders')
    axes[0].legend(fontsize=8)
    fig.savefig(args.output/'momentum_recovery.svg')
    fig.savefig(args.output/'momentum_recovery.png',dpi=150);plt.close(fig)
    table(args.output/'plot_common_cohort.tsv',plot_rows)
    print(json.dumps(validation), flush=True)


if __name__ == '__main__':
    main()
