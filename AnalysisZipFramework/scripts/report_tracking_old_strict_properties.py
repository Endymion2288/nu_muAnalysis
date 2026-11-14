#!/usr/bin/env python3
"""Inventory old/strict waveform and tracking differences without changing reconstruction."""
import argparse
import itertools
import json
import math
from pathlib import Path
import resource
import time

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from compare_tracking import MODES
from extract_tracking_station import SCALARS
from report_tracking_ablation import load_cache, subset, event_key, paired_binary
from report_tracking_material import truth_masks
from report_tracking_station import derived, controlled, table, figure_save

CHANNELS = ['Veto20', 'Veto21', 'Preshower0', 'Preshower1', 'VetoNu0_reduced',
            'VetoNu1_reduced', 'Timing0', 'Timing1', 'Timing2', 'Timing3']
CUTS = ['long', 'veto', 'timing', 'preshower', 'pz', 'layers', 'ndof', 'chi2',
        'rmax', 'rIFT', 'rVetoNu', 'theta', 'VetoNu0', 'VetoNu1']
BLOCKS = {'veto': [1], 'timing': [2], 'preshower': [3], 'VetoNu0': [12], 'VetoNu1': [13]}


def raw_with_charge(track, charge):
    c = charge['scintillator'].astype(np.float32)
    raw = ((track['event_individual_bits'][:, :, None] >> np.arange(14)) & 1).astype(bool)
    bottom = c[:, 6] + c[:, 7]; top = c[:, 8] + c[:, 9]
    y = track['event_scalars'][:, :, SCALARS.index('Lead_Track_Y_atTrig')]
    raw[:, :, 1] = ((c[:, 0] > 40) & (c[:, 1] > 40))[:, None]
    raw[:, :, 2] = ((y > 20) & (top[:, None] > 20)) | ((y < -20) & (bottom[:, None] > 20)) | ((abs(y) < 20) & ((top + bottom)[:, None] > 20))
    raw[:, :, 3] = ((c[:, 2] > 2.5) & (c[:, 3] > 2.5))[:, None]
    raw[:, :, 12] = (c[:, 4] < 30)[:, None]; raw[:, :, 13] = (c[:, 5] < 30)[:, None]
    return raw


def write(out, name, rows):
    table(out / (name + '.tsv'), rows)


def waveform_plot(data, accepted, out):
    fig, axes = plt.subplots(2, 3, figsize=(14, 8), constrained_layout=True)
    ticks=[-1000, -10, 0, 10, 1000, 100000, 10000000]
    labels=['−1000', '−10', '0', '10', '10³', '10⁵', '10⁷']
    for j, ax in enumerate(axes.flat):
        for v, a in data.items():
            x = a['scintillator'][accepted, j]; x = x[np.isfinite(x)]
            edges = np.r_[-1000, -10, -1, 0, np.geomspace(.001, 1e8, 160)]
            ax.hist(x, bins=edges, histtype='step', label=v)
        threshold = 40 if j < 2 else 2.5 if j < 4 else 30
        ax.axvline(threshold, color='black', ls=':')
        ax.set_xscale('symlog',linthresh=1)
        ax.set(yscale='log', xlim=(-1000,1e8), xlabel='Charge [pC]', ylabel='Events', title=CHANNELS[j])
        ax.set_xticks(ticks,labels); ax.tick_params(axis='x',labelsize=9); ax.legend()
    figure_save(fig, out, 'waveform_charge_distributions')


def main():
    started = time.monotonic()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--pilot', action='store_true')
    p.add_argument('--waveform-plots-only', action='store_true')
    args = p.parse_args(); out = args.output; out.mkdir(parents=True, exist_ok=True)
    paths = {'old': 'workbook/stage203_station_truth/old.npz', 'strict': 'workbook/stage205_material/full/strict.npz'}
    if args.waveform_plots_only:
        data={}
        for v,path in paths.items():
            with np.load(args.repo/path) as z:
                data[v]={k:z[k] for k in ['primary','primary_station','primary_layer_hits','scintillator']}
        waveform_plot(data,truth_masks(data['old'])['truth_station_acceptance'],out)
        return
    data = {v: load_cache(args.repo / path) for v, path in paths.items()}
    for key in ['run', 'eventID', 'primary', 'primary_station', 'primary_layer_hits']:
        assert np.array_equal(data['old'][key], data['strict'][key], equal_nan=True), key
    if args.pilot:
        ids = event_key(data['old'])[::80]
        data = {v: subset(a, ids) for v, a in data.items()}
    masks = truth_masks(data['old']); accepted = masks['truth_station_acceptance']
    groups = {'fiducial': np.ones(len(accepted), bool), 'accepted': accepted,
              'nominal_accepted': accepted & (data['old']['run'] != 200080)}
    groups.update({f'run{r}_accepted': accepted & (data['old']['run'] == r) for r in np.unique(data['old']['run'])})
    der = {v: derived(a) for v, a in data.items()}
    raw = {(t, c): raw_with_charge(data[t], data[c]) for t in data for c in data}
    for v, a in data.items():
        assert np.array_equal(raw[v, v], der[v]['raw'])
        assert np.array_equal(np.logical_and.accumulate(raw[v, v], axis=2), ((a['event_cut_bits'][:, :, None] >> np.arange(14)) & 1).astype(bool))
        assert np.array_equal(np.logical_and.accumulate(raw[v, 'old'], axis=2), controlled(a, data['old']))
    # Input charge distribution and exact threshold migrations, including NaN/Inf.
    stats = []; migrations = []; anomalies = []
    for group, den in groups.items():
        for j, channel in enumerate(CHANNELS):
            a = data['old']['scintillator'][:, j]; b = data['strict']['scintillator'][:, j]
            finite = np.isfinite(a) & np.isfinite(b) & den
            difference = b[finite] - a[finite]
            for v, values in [('old', a), ('strict', b)]:
                selected = values[den]; f = selected[np.isfinite(selected)]
                quantiles = np.quantile(f, [.001, .01, .5, .99, .999]) if len(f) else np.full(5, np.nan)
                stats.append(dict(group=group, version=v, channel=channel, events=int(den.sum()),
                    nan=int(np.isnan(selected).sum()), posinf=int(np.isposinf(selected).sum()), neginf=int(np.isneginf(selected).sum()),
                    finite_negative=int(((selected < 0) & np.isfinite(selected)).sum()),
                    q001_pc=quantiles[0], q01_pc=quantiles[1], median_pc=quantiles[2], q99_pc=quantiles[3], q999_pc=quantiles[4],
                    paired_finite=int(finite.sum()), changed_finite=int((a[finite] != b[finite]).sum()),
                    median_abs_difference_pc=float(np.median(abs(difference))) if len(difference) else np.nan,
                    abs_difference_gt1pc=int((abs(difference) > 1).sum())))
            if j < 6:
                threshold = 40 if j < 2 else 2.5 if j < 4 else 30
                x = a > threshold if j < 4 else a < threshold
                y = b > threshold if j < 4 else b < threshold
                migrations.append(dict(group=group, channel=channel, threshold_pc=threshold,
                                       **paired_binary(x, y, den)))
            for label, selected in [('nonfinite', ~np.isfinite(b)), ('finite_negative', np.isfinite(b) & (b < 0))]:
                anomalies.append(dict(group=group, channel=channel, strict_category=label,
                    events=int((den & selected).sum()), old_finite_nonnegative=int((den & selected & np.isfinite(a) & (a >= 0)).sum())))
    write(out, 'charge_distributions', stats); write(out, 'channel_threshold_migrations', migrations); write(out, 'charge_anomalies', anomalies)
    # Four corners keep the track-dependent timing Y with its tracking version.
    corners = []; replacements = []; combinations = []; shapley = []; timing = []; eventrows = []
    for group, den in groups.items():
        for m, mode in enumerate(MODES):
            baseline = raw['strict', 'strict'][:, m].all(axis=1)
            for t, c in itertools.product(data, repeat=2):
                passed = raw[t, c][:, m].all(axis=1)
                corners.append(dict(group=group, mode=mode, tracking=t, waveform=c, **paired_binary(der['old']['final'][:, m], passed, den)))
            counts = {}
            for bits in range(32):
                r = raw['strict', 'strict'][:, m].copy()
                for j, (_, indices) in enumerate(BLOCKS.items()):
                    if bits & (1 << j): r[:, indices] = raw['strict', 'old'][:, m, :][:, indices]
                passed = r.all(axis=1)
                counts[bits] = int((den & passed).sum())
                combinations.append(dict(group=group, mode=mode, old_waveform_block_mask=bits,
                    old_blocks=','.join(k for j, k in enumerate(BLOCKS) if bits & (1 << j)) or 'none',
                    passed=counts[bits], **paired_binary(baseline, passed, den)))
            for j, block in enumerate(BLOCKS):
                phi = 0.
                for bits in range(32):
                    if bits & (1 << j): continue
                    k = bits.bit_count() if hasattr(int, 'bit_count') else bin(bits).count('1')
                    weight = math.factorial(k) * math.factorial(4-k) / math.factorial(5)
                    phi += weight * (counts[bits | (1 << j)] - counts[bits])
                shapley.append(dict(group=group, mode=mode, block=block,
                    average_marginal_restored_events=phi, efficiency_pp=100*phi/den.sum() if den.any() else np.nan))
            assert np.isclose(sum(r['average_marginal_restored_events'] for r in shapley[-5:]), counts[31] - counts[0])
            for j, channel in enumerate(CHANNELS):
                hybrid = dict(data['strict']); c = data['strict']['scintillator'].copy(); c[:, j] = data['old']['scintillator'][:, j]; hybrid['scintillator'] = c
                passed = raw_with_charge(data['strict'], hybrid)[:, m].all(axis=1)
                replacements.append(dict(group=group, mode=mode, channel=channel, **paired_binary(baseline, passed, den)))
            for yversion, cversion in itertools.product(data, repeat=2):
                hybrid = dict(data['strict']); hybrid['event_scalars'] = data['strict']['event_scalars'].copy()
                hybrid['event_scalars'][:, m, 9] = data[yversion]['event_scalars'][:, m, 9]
                r = raw_with_charge(hybrid, data[cversion])[:, m]
                timing.append(dict(group=group, mode=mode, y_version=yversion, waveform=cversion,
                    timing_pass=int((den & r[:, 2]).sum()),
                    final_replacing_only_timing=int((den & raw['strict', 'strict'][:, m, :][:, [0,1,3,4,5,6,7,8,9,10,11,12,13]].all(axis=1) & r[:, 2]).sum())))
    write(out, 'four_corner_efficiency', corners); write(out, 'single_channel_replacement', replacements)
    write(out, 'waveform_block_combinations', combinations); write(out, 'waveform_shapley', shapley); write(out, 'timing_y_charge_controls', timing)
    # A mutually exclusive classification of all final events changed by replacing the waveform.
    for m, mode in enumerate(MODES):
        actual = raw['strict', 'strict'][:, m].all(axis=1); fixed = raw['strict', 'old'][:, m].all(axis=1)
        for i in np.flatnonzero(accepted & (actual != fixed)):
            c = data['strict']['scintillator'][i]; oldc = data['old']['scintillator'][i]
            failed = [CUTS[j] for j in [1,2,3,12,13] if not raw['strict', 'strict'][i,m,j]]
            psbad = c[2:4] <= 2.5; psbad |= ~np.isfinite(c[2:4])
            category = ('preshower_nonfinite' if np.any(psbad & ~np.isfinite(c[2:4])) else
                        'preshower_finite_negative' if np.any(psbad & np.isfinite(c[2:4]) & (c[2:4] < 0)) else
                        'preshower_finite_nonnegative_below_threshold' if psbad.any() else 'other_waveform')
            eventrows.append(dict(mode=mode, run=int(data['old']['run'][i]), eventID=int(data['old']['eventID'][i]),
                actual_final=bool(actual[i]), old_waveform_final=bool(fixed[i]), category=category,
                failed_blocks=','.join(failed), old_ps0_pc=oldc[2], strict_ps0_pc=c[2], old_ps1_pc=oldc[3], strict_ps1_pc=c[3]))
    write(out, 'waveform_changed_final_events', eventrows)
    # Tracking stages expose reconstruction efficiency separately from scintillator selection.
    stages = {}; stage_rows = []; overlap = []; cut_rows = []; relax = []; qrows = []
    for v, a in data.items():
        d = der[v]; leader = d['leaders']; li = np.maximum(leader, 0)
        correct = (leader >= 0) & d['primary'][li] & (d['purity'][li] >= .7)
        stages[v] = dict(primary_raw=a['raw_primary_counts'][:,:,0] > 0,
            primary_long=a['raw_primary_counts'][:,:,1] > 0, primary_quality=a['raw_primary_counts'][:,:,2] > 0,
            has_long=leader >= 0, correct_leader=correct, track_cuts=d['track_pass'],
            actual_final=d['final'], fixed_old_waveform=raw[v,'old'].all(axis=2))
        for group, den in groups.items():
            for name, values in stages[v].items():
                f, b, merge = values.T
                for label, chosen in [('both_FB', f & b), ('F_only', f & ~b), ('B_only', b & ~f), ('neither_FB', ~f & ~b),
                                      ('FB_union', f | b), ('merge_outside_FB', merge & ~f & ~b), ('FB_union_missing_merge', (f | b) & ~merge)]:
                    overlap.append(dict(group=group, version=v, stage=name, population=label, events=int((den & chosen).sum())))
            for m, mode in enumerate(MODES):
                r = raw[v, 'old'][:, m]; cumulative = np.logical_and.accumulate(r, axis=1)
                for j, cut in enumerate(CUTS):
                    before = np.ones(len(den), bool) if j == 0 else cumulative[:,j-1]
                    cut_rows.append(dict(group=group, version=v, mode=mode, cut=cut,
                        individual_pass=int((den & r[:,j]).sum()), cumulative_pass=int((den & cumulative[:,j]).sum()), first_failed=int((den & before & ~r[:,j]).sum())))
                    if j in [0,1,2,3,12,13]: continue
                    passed = np.delete(r,j,axis=1).all(axis=1)
                    relax.append(dict(group=group, version=v, mode=mode, removed_cut=cut,
                        fixed_final=int((den & cumulative[:,-1]).sum()), extra_events=int((den & passed & ~cumulative[:,-1]).sum())))
                good = correct[:,m]; idx = li[:,m]; q = d['col']['charge'][idx]; expected = -np.sign(a['primary'][:,1])
                pz = a['primary_station'][:,0,5] / 1000
                for scope, chosen in [('leaders', good), ('track_cuts', good & d['track_pass'][:,m]),
                                      ('final', good & d['final'][:,m]), ('fixed_final', good & stages[v]['fixed_old_waveform'][:,m])]:
                    for low, high in [(0,np.inf),(100,300),(300,1000),(1000,3000),(3000,np.inf)]:
                        selected = den & chosen & (pz >= low) & (pz < high)
                        qrows.append(dict(group=group, version=v, mode=mode, scope=scope, truth_pz_low_gev=low,
                            truth_pz_high_gev=high, matched_primary_events=int(selected.sum()), wrong_charge=int((selected & (q != expected)).sum())))
    for group, den in groups.items():
        for name in stages['old']:
            for m, mode in enumerate(MODES):
                stage_rows.append(dict(group=group, stage=name, mode=mode,
                    **paired_binary(stages['old'][name][:,m], stages['strict'][name][:,m], den)))
    write(out, 'tracking_stage_migrations', stage_rows); write(out, 'forward_backward_overlap', overlap)
    write(out, 'fixed_waveform_cutflow', cut_rows); write(out, 'single_cut_removal_diagnostic', relax); write(out, 'track_charge_sign', qrows)
    waveform_plot(data, accepted, out)
    fig, axes = plt.subplots(1, 3, figsize=(14, 4), constrained_layout=True)
    for m, ax in enumerate(axes):
        names = ['primary_raw', 'primary_long', 'primary_quality', 'track_cuts', 'actual_final', 'fixed_old_waveform']
        for v in data: ax.plot(range(len(names)), [100*(accepted & stages[v][s][:,m]).sum()/accepted.sum() for s in names], 'o-', label=v)
        ax.set_xticks(range(len(names)), ['raw μ', 'long μ', 'quality μ', 'track cuts', 'final', 'old waveform'], rotation=35, ha='right')
        ax.set(title=MODES[m], ylabel='Events / truth-accepted [%]'); ax.legend(); ax.grid(alpha=.2)
    figure_save(fig, out, 'tracking_efficiency_stages')
    summary = dict(versions=list(data), input_paths=paths, pilot=args.pilot, events=len(accepted), accepted=int(accepted.sum()),
        exact_ids_and_truth=True, exact_raw_and_cumulative_cut_reproduction=True, exact_previous_waveform_control=True,
        all_32_waveform_subsets_measured=True, shapley_sum_closure=True, active_charge_sign_cut=False,
        control_scope='conditional cached selection replacement, not waveform reconstruction or unique causal decomposition',
        raw_all_candidate_parameters_available=False, transported_G4_station_momentum_available=False,
        wall_s=time.monotonic()-started, max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    (out/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
