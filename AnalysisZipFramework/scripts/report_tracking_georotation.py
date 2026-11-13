#!/usr/bin/env python3
"""Report new Calypso paired efficiencies, duplicates, truth residuals and migrations."""
import argparse
import gc
import json
from pathlib import Path
import re
import time

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import uproot

from compare_tracking import MODES, selection
from extract_tracking_georotation import TRACK_FIELDS, PAIR_FIELDS
from report_tracking_comparison import report as cutflow_report, save_table, figure_save, fraction, wilson, COLORS
from report_tracking_z import report as z_report


def event_key(run, event):
    return np.asarray(run, dtype=np.int64) * 1000000000 + np.asarray(event, dtype=np.int64)


def load(manifest, output):
    records = [line.split('\t') for line in manifest.read_text().splitlines()]
    fixed_names = ('counts overlaps nonfinite_leading_quality nontrack_columns existing_merge_verified '
                   'fiducial_index tracking_index energy_den energy_pass radius_den radius_pass '
                   'z_den z_pass raw_counts raw_long nonfinite_raw_chi2 truth_matches_checked '
                   'measurement_length_mismatches').split()
    parts, events, tracks, pairs, migrations, performance, settings = [], [], [], [], [], [], []
    expected_provenance = None
    for record in records:
        with np.load(record[5]) as source:
            assert int(source['manifest_index']) == int(record[0])
            assert np.array_equal(source['track_fields'], TRACK_FIELDS)
            assert np.array_equal(source['pair_fields'], PAIR_FIELDS)
            parts.append({key: source[key] for key in fixed_names})
            events.append({key: source[key] for key in source.files if key.startswith('event_')})
            tracks.append(source['tracks']); pairs.append(source['pairs']); migrations.append(source['migrations'])
            if 'performance_json' in source:
                perf = json.loads(str(source['performance_json']))
                row = dict(index=int(record[0]), run=int(record[1]), events=int(source['counts'][0,0]),
                           output_bytes=Path(record[5]).stat().st_size, host=str(source['host']))
                for name, value in perf.items():
                    numbers = dict(re.findall(r'(\w+)=([0-9.]+)', value))
                    row.update({name + '_' + k: float(v) for k,v in numbers.items()})
                performance.append(row)
                setting = json.loads(str(source['effective_reco_json']))
                assert len(setting) == 4
                for s in setting.values():
                    assert s['IsolateCandidateSmoothing'] is True
                    assert s['MaterialEnergyLoss'] is True and s['MaterialScattering'] is True
                    assert not any(s[k] for k in ('BypassRefit','FixedTruthHits','ElectronHypothesis',
                                                  'MaxStepSize','SeedOverrideFile','AuditFile','AuditClosure'))
                settings.append(setting)
                provenance = str(source['software_provenance_json'])
                if expected_provenance is None:
                    expected_provenance = provenance
                assert provenance == expected_provenance
    summary = {key: np.stack([p[key] for p in parts]) for key in fixed_names}
    summary.update(manifest_indices=np.array([int(r[0]) for r in records]),
                   runs=np.array([int(r[1]) for r in records]))
    np.savez_compressed(output / 'counts_input.npz', **summary)
    event = {key: np.concatenate([p[key] for p in events]) for key in events[0]}
    event.update(manifest_indices=summary['manifest_indices'],
                 file_offsets=np.r_[0, np.cumsum([len(e['event_run']) for e in events])])
    np.savez_compressed(output / 'fiducial_events.npz', **event)
    arrays = dict(tracks=np.concatenate(tracks), pairs=np.concatenate(pairs), migrations=np.concatenate(migrations),
                  track_fields=np.array(TRACK_FIELDS), pair_fields=np.array(PAIR_FIELDS))
    np.savez_compressed(output / 'candidate_diagnostics.npz', **arrays)
    if performance:
        save_table(output/'performance.tsv', list(performance[0]), performance)
        (output/'effective_reco.json').write_text(json.dumps(settings[0], indent=2)+'\n')
    del parts, events, tracks, pairs, migrations
    gc.collect()
    return summary, event, arrays


def duplicate_tables(summary, event, arrays, output):
    tracks, pairs = arrays['tracks'], arrays['pairs']
    col = {name: tracks[:, i] for i, name in enumerate(TRACK_FIELDS)}
    ids = event_key(col['run'], col['event'])
    fid_ids = event_key(event['event_run'], event['event_eventID'])
    fid = np.isin(ids, fid_ids)
    final = [fid_ids[event['event_cut_bits'][:,m] == 16383] for m in range(3)]
    fit_quality = ((col['layers'] >= 7) & (col['ndof'] >= 9) &
                   np.isfinite(col['chi2']) & (col['chi2'] < 15*col['ndof']))
    scopes = dict(raw_all=np.ones(len(tracks), dtype=bool), long_all=col['long'] == 1,
                  long_truthfid=(col['long'] == 1) & fid,
                  long_fit_quality_truthfid=(col['long'] == 1) & fid & fit_quality,
                  long_final=(col['long'] == 1) & np.logical_or.reduce([
                      (col['mode'] == m) & np.isin(ids, final[m]) for m in range(3)]))
    # Pair endpoint lookups only need candidates participating in a pair.
    endpoints = {(int(r[0]),int(r[1]),int(r[2]),int(i)) for r in pairs for i in r[3:5]}
    lookup = {(int(r[0]),int(r[1]),int(r[2]),int(r[3])): i for i,r in enumerate(tracks)
              if (int(r[0]),int(r[1]),int(r[2]),int(r[3])) in endpoints}
    left = np.array([lookup[tuple(map(int, r[:4]))] for r in pairs], dtype=int)
    right = np.array([lookup[(int(r[0]),int(r[1]),int(r[2]),int(r[4]))] for r in pairs], dtype=int)
    duplicate_rows, pair_rows, truth_rows = [], [], []
    groups = dict(all=np.ones(len(tracks), dtype=bool), nominal=col['run'] != 200080)
    groups.update({str(r): col['run'] == r for r in sorted(set(summary['runs']))})
    for group, group_mask in groups.items():
        for scope, scope_mask in scopes.items():
            for m, mode in enumerate(MODES):
                selected = group_mask & scope_mask & (col['mode'] == m)
                event_ids = ids[selected]
                active_events = np.unique(event_ids)
                track_count = int(selected.sum())
                for threshold in (.5, .7, .9):
                    matched = selected & (col['barcode'] != 0) & (col['truth_hits'] >= threshold*col['measurements'])
                    selected_ids = ids[matched]
                    truth_ids = np.rec.fromarrays([selected_ids, col['barcode'][matched].astype(np.int64)])
                    unique, counts = np.unique(truth_ids, return_counts=True)
                    excess = int(np.maximum(counts-1, 0).sum())
                    duplicates = unique[counts > 1]
                    duplicate_events = np.unique(duplicates.f0)
                    matched_events, y = np.unique(selected_ids, return_counts=True)
                    x = np.zeros(len(matched_events))
                    np.add.at(x, np.searchsorted(matched_events, unique.f0), np.maximum(counts-1, 0))
                    denominator = int(matched.sum())
                    rate = float(fraction(excess, denominator))
                    se = np.sqrt(np.sum((x-rate*y)**2))/denominator if denominator else np.nan
                    lo, hi = wilson(len(duplicate_events), len(active_events))
                    duplicate_rows.append(dict(group=group, scope=scope, mode=mode, purity_threshold=threshold,
                        tracks=track_count, events_with_tracks=len(active_events), truth_matched_tracks=denominator,
                        distinct_truth_particles=len(unique), duplicate_truth_groups=len(duplicates),
                        excess_duplicate_tracks=excess, duplicate_events=len(duplicate_events),
                        excess_fraction_percent=100*rate, event_cluster_se_percent=100*se,
                        duplicate_event_fraction_percent=100*float(fraction(len(duplicate_events), len(active_events))),
                        duplicate_event_wilson_low_percent=100*lo, duplicate_event_wilson_high_percent=100*hi))
                pair_mask = selected[left] & selected[right]
                p = pairs[pair_mask]
                same_truth = (p[:,8] == 1) & (p[:,9] >= .7)
                long_count = col['long'][left[pair_mask]] + col['long'][right[pair_mask]]
                different_origins = col['source_mode'][left[pair_mask]] != col['source_mode'][right[pair_mask]]
                pair_rows.append(dict(group=group, scope=scope, mode=mode, tracks=track_count,
                    candidate_pairs=len(p), merge_key_shared_gt6_pairs=int((p[:,6] > 6).sum()),
                    exact_shared_gt6_pairs=int((p[:,5] > 6).sum()),
                    shared_fraction_ge_half_pairs=int((p[:,5] >= .5*p[:,7]).sum()),
                    same_truth_purity07_pairs=int(same_truth.sum()),
                    same_truth_purity07_shared_le6_pairs=int((same_truth & (p[:,6] <= 6)).sum()),
                    same_truth_both_long_pairs=int((same_truth & (long_count == 2)).sum()),
                    same_truth_one_long_pairs=int((same_truth & (long_count == 1)).sum()),
                    same_truth_neither_long_pairs=int((same_truth & (long_count == 0)).sum()),
                    same_truth_different_origin_pairs=int((same_truth & different_origins).sum())))
                primary = selected & (np.abs(col['pdg']) == 13) & (col['neutrino_parent'] == 1) & \
                    (col['truth_hits'] >= .7*col['measurements'])
                residual = (col['pz_mev'][primary] - col['truth_pz_mev'][primary]) / col['truth_pz_mev'][primary]
                finite = residual[np.isfinite(residual)]
                truth_rows.append(dict(group=group, scope=scope, mode=mode,
                    primary_muon_matched_tracks=int(primary.sum()),
                    events_with_primary_muon=len(np.unique(ids[primary])), finite_residual_tracks=len(finite),
                    median_relative_pz_error_percent=float(100*np.median(finite)) if len(finite) else np.nan,
                    median_absolute_relative_pz_error_percent=float(100*np.median(abs(finite))) if len(finite) else np.nan,
                    q68_absolute_relative_pz_error_percent=float(100*np.quantile(abs(finite), .68)) if len(finite) else np.nan,
                    absolute_relative_pz_error_gt50_percent_tracks=int((abs(finite) > .5).sum())))
    save_table(output/'duplicates.tsv', list(duplicate_rows[0]), duplicate_rows)
    save_table(output/'hit_overlap.tsv', list(pair_rows[0]), pair_rows)
    save_table(output/'primary_muon_truth.tsv', list(truth_rows[0]), truth_rows)
    fig, axes = plt.subplots(1, 2, figsize=(12,4.5))
    displayed = ['raw_all','long_all','long_truthfid','long_fit_quality_truthfid','long_final']
    for m, mode in enumerate(MODES):
        rows = [next(r for r in duplicate_rows if r['group']=='all' and r['scope']==s and
                     r['mode']==mode and r['purity_threshold']==.7) for s in displayed]
        x = np.arange(len(rows)) + (m-1)*.17
        axes[0].errorbar(x, [r['excess_fraction_percent'] for r in rows],
                         yerr=[r['event_cluster_se_percent'] for r in rows], fmt='o', color=COLORS[m], label=mode)
        axes[1].plot(x, [r['duplicate_event_fraction_percent'] for r in rows], 'o', color=COLORS[m], label=mode)
    for ax in axes:
        ax.set_xticks(range(len(displayed)), displayed, rotation=22, ha='right')
        ax.grid(alpha=.25); ax.legend(); ax.set_ylim(bottom=0)
    axes[0].set_ylabel('Excess / truth-matched tracks (%)')
    axes[1].set_ylabel('Duplicate events / events with tracks (%)')
    fig.suptitle('Same truth barcode with hit purity >= 0.7; independent of shared-hit criterion')
    fig.tight_layout(); figure_save(fig, output, 'duplicate_comparison')
    return duplicate_rows, pair_rows, truth_rows


def migrations(event, arrays, output):
    tracks = arrays['tracks']
    needed = {(int(r[0]),int(r[1])) for r in arrays['migrations']}
    lookup = {(int(r[0]),int(r[1]),int(r[2]),int(r[3])): r for r in tracks if (int(r[0]),int(r[1])) in needed}
    bits = {(int(r),int(e)): b for r,e,b in zip(event['event_run'],event['event_eventID'],event['event_cut_bits'])}
    rows = []
    for r in arrays['migrations']:
        run, ev, bp, mp, fl, bl, ml, retained, blocker = map(int, r)
        b = lookup.get((run,ev,1,bl)); m = lookup.get((run,ev,2,ml))
        if bp:
            category = ('no_merge_long_track' if ml < 0 else
                        'backward_retained_other_leader' if retained >= 0 else
                        'backward_removed_shared_hits' if blocker >= 0 else 'unresolved')
        else:
            category = 'merge_gain'
        row = dict(run=run, event=ev, backward_pass=bp, merge_pass=mp, category=category,
                   forward_leader_raw=fl, backward_leader_raw=bl, merge_leader_raw=ml,
                   backward_retained_at=retained, blocker_merge_raw=blocker,
                   backward_bits=int(bits[(run,ev)][1]), merge_bits=int(bits[(run,ev)][2]))
        for prefix, track in [('backward',b),('merge',m)]:
            row[prefix+'_source_mode'] = int(track[4]) if track is not None else -1
            for field in ('pz_mev','chi2','ndof','measurements','barcode','pdg','truth_pz_mev','truth_hits','neutrino_parent'):
                row[prefix+'_'+field] = float(track[TRACK_FIELDS.index(field)]) if track is not None else np.nan
        rows.append(row)
    if rows:
        save_table(output/'migration_events.tsv', list(rows[0]), rows)
    counts = {name: sum(r['category']==name for r in rows) for name in sorted({r['category'] for r in rows})}
    (output/'migration_summary.json').write_text(json.dumps(counts,indent=2)+'\n')
    return counts


def compare_old(repo, summary, event, output):
    old_path = repo/'workbook/stage10_tracking_z/fiducial_events.npz'
    if not old_path.exists():
        return {}
    with np.load(old_path) as source:
        old = {key:source[key] for key in source.files}
    old_ids = event_key(old['event_run'], old['event_eventID'])
    new_ids = event_key(event['event_run'], event['event_eventID'])
    common_events = np.zeros(len(new_ids), dtype=bool)
    for i, index in enumerate(event['manifest_indices']):
        if index in old['manifest_indices']:
            common_events[event['file_offsets'][i]:event['file_offsets'][i+1]] = True
    assert int(common_events.sum()) == len(old_ids)
    order = np.argsort(new_ids)
    positions = order[np.searchsorted(new_ids[order], old_ids)]
    assert np.array_equal(new_ids[positions], old_ids)
    assert len(np.unique(new_ids)) == len(new_ids)
    for key in ('event_truth_pz_nu','event_truth_dec_x_nu','event_truth_dec_y_nu','event_truth_dec_z_nu'):
        assert np.array_equal(event[key][positions], old[key]), key
    cuts, _ = selection(repo)
    names = [n for n,_ in cuts][6:]
    rows = []
    for m,mode in enumerate(MODES):
        for j,name in enumerate(names):
            a = ((old['event_cut_bits'][:,m] >> j) & 1).astype(bool)
            b = ((event['event_cut_bits'][positions,m] >> j) & 1).astype(bool)
            lost, gain, both = int((a & ~b).sum()), int((~a & b).sum()), int((a & b).sum())
            delta = (gain-lost)/len(a)
            se = np.sqrt(((gain+lost)/len(a)-delta**2)/len(a))
            rows.append(dict(mode=mode,cut=name,denominator=len(a),old_pass=int(a.sum()),new_pass=int(b.sum()),
                old_only=lost,new_only=gain,both=both,delta_percentage_points=100*delta,
                paired_se_percentage_points=100*se))
    save_table(output/'new_vs_old_common342.tsv', list(rows[0]), rows)
    old_loss = (old['event_cut_bits'][:,1]==16383) & (old['event_cut_bits'][:,2]!=16383)
    current = event['event_cut_bits'][positions[old_loss]]
    result = dict(old_loss_events=int(old_loss.sum()),new_backward_pass=int((current[:,1]==16383).sum()),
        new_merge_pass=int((current[:,2]==16383).sum()),
        new_backward_only=int(((current[:,1]==16383)&(current[:,2]!=16383)).sum()),
        both_fail=int(((current[:,1]!=16383)&(current[:,2]!=16383)).sum()))
    (output/'old89_recheck.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def scintillator_control(repo, manifest, event, output, skip_old=False):
    raw = ((event['event_reco_decision_bits'][:, :, None] >> np.arange(14)) & 1).astype(bool)
    native = np.logical_and.accumulate(raw, axis=2)
    assert np.array_equal(np.sum(native.astype(np.uint16) << np.arange(14), axis=2), event['event_cut_bits'])
    track_cuts = [0,4,5,6,7,8,9,10,11]
    tracking = np.logical_and.accumulate(raw[:,:,track_cuts], axis=2)
    cuts,_ = selection(repo)
    names = [n for n,_ in cuts][6:]
    track_rows = [dict(mode=mode,cut=names[j],denominator=len(raw),
                       passed=int(tracking[:,m,k].sum()),
                       efficiency_percent=100*tracking[:,m,k].mean())
                  for m,mode in enumerate(MODES) for k,j in enumerate(track_cuts)]
    save_table(output/'tracking_only.tsv',list(track_rows[0]),track_rows)
    if skip_old:
        return
    controlled = raw.copy()
    common = np.zeros(len(raw),dtype=bool)
    columns = ['run','eventID','Veto20_charge','Veto21_charge','Preshower0_charge','Preshower1_charge',
               'VetoNu0_reduced_charge','VetoNu1_reduced_charge']+[f'Timing{i}_charge' for i in range(4)]
    records = [line.split('\t') for line in manifest.read_text().splitlines()]
    with np.load(repo/'workbook/stage10_tracking_z/fiducial_events.npz') as source:
        requested_indices = {int(r[0]) for r in records}
        requested = np.zeros(len(source['event_run']),dtype=bool)
        for i,index in enumerate(source['manifest_indices']):
            if int(index) in requested_indices:
                requested[source['file_offsets'][i]:source['file_offsets'][i+1]]=True
        old_ids = event_key(source['event_run'][requested],source['event_eventID'][requested])
        old_bits = source['event_cut_bits'][requested]
        old_indices = set(source['manifest_indices'])
    for i,record in enumerate(records):
        if int(record[0]) not in old_indices:
            continue
        start,stop = event['file_offsets'][i:i+2]
        with uproot.open(record[4]) as source:
            old = source['nt'].arrays(columns,library='np')
        ids = event_key(old['run'],old['eventID'])
        target = event_key(event['event_run'][start:stop],event['event_eventID'][start:stop])
        order=np.argsort(ids); positions=order[np.searchsorted(ids[order],target)]
        assert np.array_equal(ids[positions],target)
        v={k:old[k][positions] for k in columns}
        common[start:stop]=True
        # ROOT adds float branches before comparing to the double threshold.
        bottom=v['Timing0_charge']+v['Timing1_charge']
        top=v['Timing2_charge']+v['Timing3_charge']
        for m in range(3):
            y=event['event_Lead_Track_Y_atTrig'][start:stop,m]
            controlled[start:stop,m,1]=(v['Veto20_charge']>40)&(v['Veto21_charge']>40)
            controlled[start:stop,m,2]=((y>20)&(top>20))|((y< -20)&(bottom>20))|((abs(y)<20)&(top+bottom>20))
            controlled[start:stop,m,3]=(v['Preshower0_charge']>2.5)&(v['Preshower1_charge']>2.5)
            controlled[start:stop,m,12]=v['VetoNu0_reduced_charge']<30
            controlled[start:stop,m,13]=v['VetoNu1_reduced_charge']<30
    controlled_cumulative=np.logical_and.accumulate(controlled,axis=2)
    new_ids=event_key(event['event_run'],event['event_eventID'])
    order=np.argsort(new_ids); positions=order[np.searchsorted(new_ids[order],old_ids)]
    assert len(positions)==int(common.sum()) and np.array_equal(new_ids[positions],old_ids)
    previous=((old_bits[:,:,None]>>np.arange(14))&1).astype(bool)
    rows=[]
    for m,mode in enumerate(MODES):
        for j,name in enumerate(names):
            new_native=native[positions,m,j]
            control=controlled_cumulative[positions,m,j]
            for label,a,b in [('old_to_new_fixed_old_scintillator',previous[:,m,j],control),
                              ('new_native_to_fixed_old_scintillator',new_native,control)]:
                lost=int((a&~b).sum());gain=int((~a&b).sum());n=len(a);delta=(gain-lost)/n
                rows.append(dict(comparison=label,mode=mode,cut=name,denominator=n,
                    first_pass=int(a.sum()),second_pass=int(b.sum()),first_only=lost,second_only=gain,
                    both=int((a&b).sum()),delta_percentage_points=100*delta,
                    paired_se_percentage_points=100*np.sqrt(((lost+gain)/n-delta**2)/n)))
    save_table(output/'fixed_scintillator_version_comparison.tsv',list(rows[0]),rows)
    np.savez_compressed(output/'fixed_old_scintillator_events.npz',
                        run=event['event_run'][positions],event=event['event_eventID'][positions],
                        cumulative=controlled_cumulative[positions])
    changed=[]
    for m,mode in enumerate(MODES):
        for j in (1,2,3,12,13):
            changed.append(dict(mode=mode,cut=names[j],denominator=int(common.sum()),
                individual_decision_changed=int((raw[common,m,j]!=controlled[common,m,j]).sum())))
    save_table(output/'scintillator_decision_changes.tsv',list(changed[0]),changed)


def main():
    start = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--skip-old',action='store_true')
    args = parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    summary,event,arrays = load(args.manifest,args.output)
    cutflow_report(args.repo,args.manifest,args.output,args.output/'counts_input.npz',
                   require_existing=False, software_label='geoRotation 88c457c1 + isolated smoothing')
    z_report(args.repo,args.manifest,args.output/'paired_results.npz',args.output,
             combined=args.output/'fiducial_events.npz')
    # Correct the old report's historical-context sentence for this new sample.
    zpath = args.output/'comparison_z.md'
    zpath.write_text(zpath.read_text().replace('与阶段 09 相同的', '本次新版重建的'))
    duplicate_rows,pair_rows,truth_rows = duplicate_tables(summary,event,arrays,args.output)
    migration = migrations(event,arrays,args.output)
    old = {} if args.skip_old else compare_old(args.repo,summary,event,args.output)
    scintillator_control(args.repo,args.manifest,event,args.output,args.skip_old)
    counts = summary['counts'].sum(axis=0)
    report = dict(files=len(summary['runs']),events=int(counts[0,0]),truth=int(counts[0,6]),
        final=counts[:,-1].tolist(),raw_tracks=summary['raw_counts'].sum(axis=0).tolist(),
        long_tracks=summary['raw_long'].sum(axis=0).tolist(),
        nonfinite_raw_chi2=summary['nonfinite_raw_chi2'].sum(axis=0).tolist(),
        truth_matches_checked=summary['truth_matches_checked'].sum(axis=0).tolist(),
        migration=migration,old89=old,report_wall_seconds=time.monotonic()-start)
    (args.output/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)


if __name__ == '__main__':
    main()
