#!/usr/bin/env python3
"""Explain paired tracking losses with track identities, shared measurements and event displays."""

import argparse
from collections import Counter
import csv
import gzip
import json
from pathlib import Path
import re
import resource
import time

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from report_tracking_comparison import figure_save, save_table

MODES = ('forward', 'backward', 'merge')
COLORS = dict(forward='#0072B2', backward='#D55E00', merge='#009E73')
PARAMETERS = ('x0', 'y0', 'z0', 'px0', 'py0', 'pz0', 'Chi2', 'nDoF', 'charge')


def signature(raw, i):
    return np.array([raw['Track_'+key][i] for key in PARAMETERS])


def same(a, b):
    return a.shape == b.shape and bool(np.allclose(a, b, rtol=0, atol=0, equal_nan=True))


def measurement_index(event, mode, i):
    raw = event['modes'][mode]['raw']
    params = np.array([raw['Track_'+key][i] for key in PARAMETERS[:6]])
    candidates = []
    for j, track in enumerate(event['measurements'][mode]):
        if not track['states']:
            continue
        if (np.allclose(track['states'][0], params, rtol=1e-7, atol=1e-5, equal_nan=True) and
                np.isclose(track['chi2'], raw['Track_Chi2'][i], rtol=1e-7, atol=1e-5, equal_nan=True) and
                track['ndof'] == raw['Track_nDoF'][i]):
            candidates.append(j)
    assert len(candidates) == 1, (event['run'], event['event'], mode, i, candidates)
    return candidates[0]


def hits(track):
    # Retain the same station/layer/side/strip comparison used by official MergeTracksAlg.
    return set(map(tuple, track['hits']))


def track_pass(raw, i, scalars):
    """Counterfactual candidate-level checks, leaving event cuts and YAML thresholds fixed."""
    pz = raw['Track_pz0'][i]
    theta = np.arctan2(np.hypot(raw['Track_px0'][i], raw['Track_py0'][i]), pz)*1000
    # All final backward-only events passed fixed scintillator/veto inputs. Timing is checked
    # only for the retained original backward leader, whose coordinates are unchanged.
    is_original_backward_leader = same(signature(raw, i), scalars)
    return bool(pz > 100000 and raw['Track_nLayers'][i] >= 7 and raw['Track_nDoF'][i] >= 9 and
                raw['Track_Chi2'][i]/raw['Track_nDoF'][i] < 15 and
                raw['Track_r_atMaxRadius'][i] < 95 and
                np.hypot(raw['Track_X_atVetoStation2'][i], raw['Track_Y_atVetoStation2'][i]) < 95 and
                np.hypot(raw['Track_X_atVetoNu'][i], raw['Track_Y_atVetoNu'][i]) < 120 and theta < 25 and
                is_original_backward_leader)


def summarize(event):
    b = event['modes']['backward']; m = event['modes']['merge']
    bi, mi = int(b['scalars']['LeadTrack_Idx']), int(m['scalars']['LeadTrack_Idx'])
    original = signature(b['raw'], bi)
    retained = [i for i in range(len(m['raw']['Track_pz0'])) if same(original, signature(m['raw'], i))]
    bj = measurement_index(event, 'backward', bi)
    bt = event['measurements']['backward'][bj]
    raw_retained = [i for i, t in enumerate(event['measurements']['merge'])
                    if same(np.array(t['states']), np.array(bt['states'])) and
                    same(np.array([t['chi2'], t['ndof']]), np.array([bt['chi2'], bt['ndof']]))]
    # Different track lengths cannot be broadcast for equality.
    if retained:
        assert raw_retained and mi not in retained
        assert track_pass(m['raw'], retained[0], original)
        mechanism = 'backward_leader_retained_but_not_leading'
    else:
        assert not raw_retained
        mechanism = 'backward_leader_removed_by_merge'
    blockers = []
    for j, track in enumerate(event['measurements']['merge']):
        shared = sum(tuple(hit) in hits(track) for hit in bt['hits'])
        if shared > 6:
            blockers.append((j, track, shared))
    if not retained:
        assert blockers, (event['run'], event['event'], 'removed without shared-hit winner')
    winner = blockers[0] if blockers and not retained else None
    ms = m['scalars']; bs = b['scalars']
    row = dict(run=event['run'], eventID=event['event'], mechanism=mechanism,
               backward_track_count=len(b['raw']['Track_pz0']), merge_track_count=len(m['raw']['Track_pz0']),
               backward_leader_raw_index=bj, backward_leader_retained=bool(retained),
               backward_pz_GeV=bs['LeadTrack_pz0'], merge_pz_GeV=ms['LeadTrack_pz0'],
               backward_rmax_mm=bs['LeadTrack_r_atMaxRadius'], merge_rmax_mm=ms['LeadTrack_r_atMaxRadius'],
               backward_rIFT_mm=bs['LeadTrack_rIFT'], merge_rIFT_mm=ms['LeadTrack_rIFT'],
               backward_theta_mrad=bs['LeadTrack_Theta'], merge_theta_mrad=ms['LeadTrack_Theta'],
               backward_z0_mm=b['raw']['Track_z0'][bi],
               merge_z0_mm=m['raw']['Track_z0'][mi] if mi >= 0 else np.nan,
               backward_z_at_rmax_mm=b['raw']['Track_z_atMaxRadius'][bi],
               merge_z_at_rmax_mm=m['raw']['Track_z_atMaxRadius'][mi] if mi >= 0 else np.nan,
               backward_measurements=len(bt['hits']),
               blocking_merge_raw_index=winner[0] if winner else -1,
               blocking_measurements=len(winner[1]['hits']) if winner else 0,
               blocking_shared_hits=winner[2] if winner else 0,
               blocking_unique_hits=len(hits(winner[1])) if winner else 0,
               blocking_distinct_planes=len({tuple(h[:3]) for h in winner[1]['hits']}) if winner else 0,
               blocking_stations=','.join(map(str, sorted({h[0] for h in winner[1]['hits']}))) if winner else '',
               blocking_has_all_stations=all(s in {h[0] for h in winner[1]['hits']} for s in (1,2,3)) if winner else '',
               blocking_duplicate_measurements=len(winner[1]['hits'])-len(hits(winner[1])) if winner else 0,
               backward_chi2_ndof=bs['LeadTrack_Chi2_NDF'],
               blocking_chi2_ndof=winner[1]['chi2']/winner[1]['ndof'] if winner and winner[1]['ndof'] else np.nan,
               merge_leader_is_forward=bool(m['raw']['Track_isForward'][mi]) if mi >= 0 else '',
               merge_leader_measurements=len(event['measurements']['merge'][measurement_index(event, 'merge', mi)]['hits'])
                                         if mi >= 0 else 0,
               backward_radius_margin_mm=95-bs['LeadTrack_r_atMaxRadius'],
               merge_leader_long=mi >= 0,
               truth_pz_GeV=bs['truth_pz_nu'], truth_r_mm=bs['truth_dec_r'], truth_z_mm=bs['truth_dec_z_nu'])
    if winner:
        n1, n0 = len(winner[1]['hits']), len(bt['hits'])
        row['blocking_priority'] = 'more_measurements' if n1 > n0 else 'same_measurements_lower_chi2'
        assert n1 > n0 or (n1 == n0 and row['blocking_chi2_ndof'] <= row['backward_chi2_ndof'])
    else:
        row['blocking_priority'] = 'not_removed'
    return row


def make_viewer(events, rows, template, output):
    packed = []
    for event, row in zip(events, rows):
        modes = {}
        for mode in MODES:
            part = event['modes'][mode]; raw = part['raw']; tracks = []
            for i in range(len(raw['Track_pz0'])):
                j = measurement_index(event, mode, i)
                tracks.append(dict(points=[state[:3] for state in event['measurements'][mode][j]['states']],
                                   ift=[raw['Track_X_atVetoStation2'][i], raw['Track_Y_atVetoStation2'][i]]))
            # Include raw candidates rejected by the long-track station requirement, as dashed lines.
            accepted = {measurement_index(event, mode, i) for i in range(len(tracks))}
            rejected = [[state[:3] for state in track['states']] for j, track in enumerate(event['measurements'][mode])
                        if j not in accepted]
            modes[mode] = dict(scalars=part['scalars'], tracks=tracks, rejected=rejected)
        b = event['modes']['backward']['raw']
        packed.append(dict(run=event['run'], event=event['event'], info=row, modes=modes,
                           spacepoints=list(zip(b['SpacePoint_x'], b['SpacePoint_y'], b['SpacePoint_z']))))
    # Use JSON null for nonfinite values so the standalone viewer remains valid JSON.
    def finite(value):
        if isinstance(value, dict): return {key: finite(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)): return [finite(item) for item in value]
        if isinstance(value, float): return round(value, 6) if np.isfinite(value) else None
        return value
    serialized = json.dumps(finite(packed), separators=(',', ':'))
    output.write_text(template.read_text().replace('__EVENT_DATA__', serialized))


def draw_event(event, row, output):
    fig, axes = plt.subplots(2, 3, figsize=(17, 8), sharex=True, sharey='row')
    for col, mode in enumerate(MODES):
        part = event['modes'][mode]; raw = part['raw']; lead = int(part['scalars']['LeadTrack_Idx'])
        for k, coordinate in enumerate(('x', 'y')):
            ax = axes[k, col]
            ax.scatter(raw['SpacePoint_z'], raw['SpacePoint_'+coordinate], s=4, alpha=.35, color='grey', rasterized=True)
            # Approximate station positions from EventDisplay_PHYS/src/DetectorRender.py.
            for station in (0, 1190, 2380):
                ax.axvspan(station-40, station+40, color='#eeeeee', zorder=0)
            for i in range(len(raw['Track_pz0'])):
                j = measurement_index(event, mode, i)
                states = np.asarray(event['measurements'][mode][j]['states'])
                order = np.argsort(states[:, 2])
                ax.plot(states[order, 2], states[order, k], '.-', color=COLORS[mode],
                        lw=2.3 if i == lead else .8, alpha=1 if i == lead else .4,
                        label=f'track {i}'+(' (leading)' if i == lead else ''))
                # Mark extrapolated coordinates separately; connecting them linearly would fake a field fit.
                value = raw['Track_'+('X' if k == 0 else 'Y')+'_atVetoStation2'][i]
                if abs(value) < 1000:
                    ax.scatter([-1590], [value], marker='x', s=40, color=COLORS[mode])
            accepted = {measurement_index(event, mode, i) for i in range(len(raw['Track_pz0']))}
            for j, track in enumerate(event['measurements'][mode]):
                if j not in accepted and track['states']:
                    states = np.asarray(track['states']); order = np.argsort(states[:, 2])
                    ax.plot(states[order, 2], states[order, k], '--', color=COLORS[mode], lw=1.2,
                            label=f'candidate {j} (not long)')
            ax.set_ylabel(f'{coordinate} (mm)'); ax.grid(alpha=.2)
            ax.set_xlim(-1800, 2500); ax.set_ylim(-125, 125)
            ax.axvline(-1590, ls=':', color='grey')
            if k == 0:
                s = part['scalars']
                ax.set_title(f'{mode}: Nlong={int(s["longTracks"])}; pz={s["LeadTrack_pz0"]:.2f} GeV\n'
                             f'rmax={s["LeadTrack_r_atMaxRadius"]:.2f} mm; rIFT={s["LeadTrack_rIFT"]:.2f} mm')
                if event['measurements'][mode]:
                    ax.legend(fontsize=7, loc='best')
            else:
                ax.set_xlabel('z (mm); crosses: VetoStation2 extrapolation')
    fig.suptitle(f'Run {event["run"]}, event {event["event"]} · {row["first_failed_cut"]}\n'
                 f'{row["mechanism"]}; shared hits={row["blocking_shared_hits"]}; '
                 f'measurements B/blocker={row["backward_measurements"]}/{row["blocking_measurements"]}')
    fig.tight_layout(); figure_save(fig, output, f'event_{event["run"]}_{event["event"]}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--combined', type=Path)
    parser.add_argument('--allow-partial', action='store_true')
    parser.add_argument('--example', action='append', default=[], help='Additional static example: run/event')
    args = parser.parse_args(); repo = args.repo.resolve()
    output = repo/'workbook/stage17_tracking_loss'; tick = time.monotonic()
    expected = list(csv.DictReader((output/'loss_events.tsv').open(), delimiter='\t'))
    lookup = {(int(r['run']), int(r['eventID'])): r for r in expected}
    if args.combined:
        with gzip.open(args.combined, 'rt') as source:
            events = json.load(source)
    else:
        events = [json.loads(path.read_text()) for path in sorted((repo/'ntuples/tracking_loss_stage17').glob('*.json'))
                  if re.fullmatch(r'\d+_\d+\.json', path.name)]
    ids = [(event['run'], event['event']) for event in events]
    assert len(ids) == len(set(ids))
    if not args.allow_partial:
        assert set(ids) == set(lookup), (len(ids), len(lookup))
    rows = []
    for event in events:
        reference = lookup[(event['run'], event['event'])]
        assert event['existing_merge_verified']
        assert event['expected_bits'] == [int(reference[key]) for key in ('forward_bits', 'backward_bits', 'merge_bits')]
        row = summarize(event); row['first_failed_cut'] = reference['first_failed_cut']; rows.append(row)
    save_table(output/'event_mechanisms.tsv', list(rows[0]), rows)
    nonlong = [row for row in rows if row['blocking_has_all_stations'] is False]
    if nonlong:
        save_table(output/'nonlong_blockers.tsv', list(nonlong[0]), nonlong)
    categories = []
    for cut in sorted({row['first_failed_cut'] for row in rows}):
        selected = [row for row in rows if row['first_failed_cut'] == cut]
        categories.append(dict(first_failed_cut=cut, events=len(selected),
                               backward_leader_removed=sum(not row['backward_leader_retained'] for row in selected),
                               backward_leader_retained=sum(row['backward_leader_retained'] for row in selected)))
    save_table(output/'mechanism_by_cut.tsv', list(categories[0]), categories)
    # One compressed diagnostic record replaces per-job JSON, after exact serialization readback.
    combined = repo/'ntuples/tracking_loss_stage17/diagnostics.json.gz'
    if not args.combined and not args.allow_partial:
        serialized = json.dumps(events, allow_nan=True, separators=(',', ':'))
        with gzip.open(combined, 'wt') as target:
            target.write(serialized)
        with gzip.open(combined, 'rt') as source:
            assert json.dumps(json.load(source), allow_nan=True, separators=(',', ':')) == serialized
    plt.rcParams.update({'font.size': 10, 'svg.fonttype': 'none'})
    fig, axes = plt.subplots(2, 3, figsize=(15, 9))
    for ax, key, threshold, title in zip(axes[0], ['pz_GeV', 'rmax_mm', 'rIFT_mm'], [100,95,95],
                                        ['Leading track pz (GeV)', 'Maximum track radius (mm)', 'IFT extrapolated radius (mm)']):
        a = np.array([row['backward_'+key] for row in rows]); b = np.array([row['merge_'+key] for row in rows])
        valid = np.isfinite(a) & np.isfinite(b)
        ax.scatter(a[valid], b[valid], s=20, alpha=.8)
        limits = [min(a[valid].min(), b[valid].min(), threshold)*.9,
                  max(a[valid].max(), b[valid].max(), threshold)*1.05]
        ax.plot(limits, limits, color='grey', lw=.8); ax.axvline(threshold, ls='--', color='grey')
        ax.axhline(threshold, ls='--', color='grey'); ax.set(xlabel='Backward '+title, ylabel='Merge '+title)
        if key == 'pz_GeV':
            ax.set_xscale('log'); ax.set_yscale('log')
        ax.grid(alpha=.2)
    axes[1,0].hist([row['backward_z_at_rmax_mm'] for row in rows], bins=[-100,100,500,1000,1500,2000,2500],
                    histtype='step', lw=2, label='Backward leading')
    axes[1,0].hist([row['merge_z_at_rmax_mm'] for row in rows if np.isfinite(row['merge_z_at_rmax_mm'])],
                    bins=[-100,100,500,1000,1500,2000,2500], histtype='step', lw=2, label='Merge leading')
    axes[1,0].set(xlabel='z at maximum track radius (mm)', ylabel='Events'); axes[1,0].legend()
    mechanisms = Counter(row['mechanism'] for row in rows)
    axes[1,1].barh(list(mechanisms), list(mechanisms.values()), color='#D55E00')
    axes[1,1].set_xlabel('Events')
    axes[1,2].scatter([row['backward_measurements'] for row in rows], [row['blocking_measurements'] for row in rows],
                      s=35, alpha=.4)
    axes[1,2].plot([0,24], [0,24], color='grey'); axes[1,2].set(
        xlabel='Measurements: backward leader', ylabel='Measurements: blocking merge track')
    fig.suptitle(f'{len(rows)} backward-pass / merge-fail events · paired reconstructed-track diagnostics\n'
                 'Missing merge leaders are omitted from scatter plots; original cuts and reconstruction unchanged')
    fig.tight_layout(); figure_save(fig, output, 'paired_track_diagnostics')
    # Cover all distinct failing cuts and both identity mechanisms with deterministic examples.
    chosen = []
    for key in sorted({(r['first_failed_cut'], r['mechanism']) for r in rows}):
        indices = [i for i, r in enumerate(rows) if (r['first_failed_cut'], r['mechanism']) == key]
        chosen.append(indices[len(indices)//2])
    for requested in args.example:
        run, event_id = map(int, requested.split('/'))
        index = ids.index((run, event_id))
        if index not in chosen:
            chosen.append(index)
    for i in chosen:
        draw_event(events[i], rows[i], output)
    make_viewer(events, rows, Path(__file__).with_name('tracking_loss_viewer.html'), output/'event_viewer.html')
    summary = dict(events=len(rows), mechanisms=dict(mechanisms),
                   blocking_priority=dict(Counter(row['blocking_priority'] for row in rows)),
                   merge_leader_is_forward=dict(Counter(str(row['merge_leader_is_forward']) for row in rows)),
                   event_display_ids=[f'{events[i]["run"]}/{events[i]["event"]}' for i in chosen],
                   track_nMeasurements_length_mismatch=sum(len(part['raw']['Track_nMeasurements']) != len(part['raw']['Track_pz0'])
                                                           for event in events for part in event['modes'].values()),
                   removed_by_nonlong_candidate=sum(row['blocking_has_all_stations'] is False for row in rows),
                   blocking_duplicate_measurements_events=sum(row['blocking_duplicate_measurements'] > 0 for row in rows),
                   wall_seconds=time.monotonic()-tick,
                   peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    (output/'details_summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
