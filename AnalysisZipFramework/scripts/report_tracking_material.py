#!/usr/bin/env python3
"""Full paired material-map production, reusing frozen old/native event caches."""
import argparse
import json
from pathlib import Path
import resource
import time

import numpy as np
import matplotlib.pyplot as plt
import report_tracking_station as station
from report_tracking_ablation import paired_binary, event_key
from compare_tracking import MODES, selection


def load(path):
    with np.load(path) as f:
        return {k: f[k] for k in f.files}


def truth_masks(old):
    t = old['primary_station']; unique = old['primary'][:, 2] == 1
    finite = unique & np.isfinite(t).all(axis=(1, 2)) & (t[:, :, 5] > 0).all(axis=1)
    layers = (old['primary_layer_hits'] > 0).sum(axis=1) >= 7
    radius = (np.linalg.norm(t[:, :, :2], axis=2) < 95).all(axis=1)
    pz = (t[:, :, 5] > 100000).all(axis=1)
    theta = (1000*np.arctan2(np.linalg.norm(t[:, :, 3:5], axis=2), t[:, :, 5]) < 25).all(axis=1)
    return dict(fiducial=np.ones(len(t), bool), unique_primary=unique, three_stations=finite,
                truth_layers_ge7=finite & layers, truth_radius_lt95=finite & layers & radius,
                truth_pz_gt100=finite & layers & radius & pz,
                truth_station_acceptance=finite & layers & radius & pz & theta)


def duplicates(data, der, groups, masks, output):
    rows = []; details = []; primary_rows = []
    for version, a in data.items():
        d = der[version]; c = d['col']
        for m, mode in enumerate(MODES):
            for scope, quality in [('long', np.ones(len(a['tracks']), bool)), ('quality', d['quality'])]:
                for threshold in [.5, .7, .9]:
                    chosen = (c['mode'] == m) & quality & (c['barcode'] != 0) & (d['purity'] >= threshold)
                    pairs = np.column_stack([d['idx'][chosen], c['barcode'][chosen].astype(np.int64)])
                    pairs, counts = np.unique(pairs, axis=0, return_counts=True)
                    if scope == 'quality' and threshold == .7:
                        indices = np.flatnonzero(chosen)
                        order = np.lexsort((c['barcode'][indices],d['idx'][indices]))
                        indices = indices[order]; starts = np.r_[0,np.cumsum(counts)]
                        for j in np.flatnonzero(counts > 1):
                            event, barcode = pairs[j]; tracks = indices[starts[j]:starts[j+1]]
                            pz = c['pz_mev'][tracks]/1000
                            details.append(dict(version=version,mode=mode,run=int(a['run'][event]),
                                eventID=int(a['eventID'][event]),barcode=int(barcode),tracks=len(tracks),
                                primary=bool(a['primary'][event,2] == 1 and barcode == a['primary'][event,0]),
                                truth_accepted=bool(masks['truth_station_acceptance'][event]),
                                final=bool(d['final'][event,m]),leader_in_group=bool((c['leader'][tracks] == 1).any()),
                                raw_indices=json.dumps(c['raw_index'][tracks].astype(int).tolist()),
                                minimum_hit_purity=float(d['purity'][tracks].min()),
                                minimum_pz_gev=float(pz.min()),maximum_pz_gev=float(pz.max())))
                    for group, g in groups.items():
                        for denom_name in ['fiducial', 'truth_station_acceptance']:
                            denominator = g & masks[denom_name]
                            inside = denominator[pairs[:, 0]]
                            dup = inside & (counts > 1)
                            den = int(denominator.sum()); n = len(np.unique(pairs[dup, 0]))
                            primary = inside & (a['primary'][pairs[:, 0], 2] == 1) & (pairs[:, 1] == a['primary'][pairs[:, 0], 0])
                            rows.append(dict(version=version, mode=mode, scope=scope, purity_threshold=threshold,
                                group=group, denominator_name=denom_name, denominator=den,
                                matched_tracks=int(counts[inside].sum()), matched_truth_groups=int(inside.sum()),
                                duplicate_groups=int(dup.sum()), excess_tracks=int((counts[dup]-1).sum()),
                                duplicate_events=n, duplicate_event_percent=100*n/den if den else np.nan,
                                matched_group_duplicate_percent=100*dup.sum()/inside.sum() if inside.any() else np.nan,
                                primary_duplicate_events=int((primary & (counts > 1)).sum())))
            # Raw summaries retain all primary-muon matches, including short fragments.
            for scope,j in [('raw',0),('long',1),('quality',2)]:
                counts = a['raw_primary_counts'][:,m,j]
                if scope != 'raw':
                    chosen = (c['mode'] == m) & d['primary'] & (d['purity'] >= .7)
                    if scope == 'quality': chosen &= d['quality']
                    assert np.array_equal(np.bincount(d['idx'][chosen],minlength=len(counts)),counts)
                for group,g in groups.items():
                    for name in ['fiducial','truth_station_acceptance']:
                        den = g & masks[name]; matched = den & (counts > 0); dup = den & (counts > 1)
                        primary_rows.append(dict(version=version,mode=mode,scope=scope,purity_threshold=.7,
                            group=group,denominator_name=name,denominator=int(den.sum()),
                            matched_primary_events=int(matched.sum()),matched_primary_tracks=int(counts[den].sum()),
                            duplicate_primary_events=int(dup.sum()),excess_primary_tracks=int((counts[dup]-1).sum()),
                            duplicate_event_percent=100*dup.sum()/den.sum() if den.any() else np.nan,
                            duplicate_given_primary_match_percent=100*dup.sum()/matched.sum() if matched.any() else np.nan))
    station.table(output / 'duplicates.tsv', rows)
    station.table(output / 'duplicate_quality_events.tsv', details)
    station.table(output / 'primary_duplicate_counts.tsv',primary_rows)


def selection_pairs(data, der, groups, masks, comparisons, output):
    rows = []
    for base, variant in comparisons:
        for group, g in groups.items():
            for denom_name in ['fiducial', 'truth_station_acceptance']:
                den = g & masks[denom_name]
                for m, mode in enumerate(MODES):
                    for stage in ['track_pass', 'final', 'fixed_final', 'final_correct', 'fixed_correct']:
                        passed = []
                        for v in [base, variant]:
                            d = der[v]; leader = d['leaders'][:, m]; li = np.maximum(leader, 0)
                            correct = (leader >= 0) & d['primary'][li] & (d['purity'][li] >= .7)
                            mask = d['control'][:, m, -1] if stage.startswith('fixed') else d['track_pass'][:, m] if stage == 'track_pass' else d['final'][:, m]
                            if stage.endswith('correct'): mask = mask & correct
                            passed.append(mask)
                        rows.append(dict(baseline=base, variant=variant, group=group, denominator_name=denom_name,
                                         mode=mode, stage=stage, **paired_binary(*passed, den)))
    station.table(output / 'paired_efficiency.tsv', rows)


def migration_events(data, der, masks, output):
    rows = []
    if 'strict' not in data: return
    cutnames = ['has_long','veto_charge','timing','preshower','pz','layers','ndof','chi2',
                'rmax','rIFT','rVetoNu','theta','VetoNu0','VetoNu1']
    for base in ['old','new']:
        for m,mode in enumerate(MODES):
            a = der[base]['final'][:,m]; b = der['strict']['final'][:,m]
            for event in np.flatnonzero(masks['truth_station_acceptance'] & (a != b)):
                row = dict(baseline=base,mode=mode,run=int(data[base]['run'][event]),
                           eventID=int(data[base]['eventID'][event]),baseline_final=bool(a[event]),strict_final=bool(b[event]))
                for v in [base,'strict']:
                    d = der[v]; leader = d['leaders'][event,m]
                    bits = int(data[v]['event_cut_bits'][event,m]); failed = [j for j in range(14) if not (bits >> j)&1]
                    row[v+'_first_failed'] = cutnames[failed[0]] if failed else 'pass'
                    row[v+'_primary_long'] = int(data[v]['raw_primary_counts'][event,m,1])
                    row[v+'_correct_leader'] = bool(leader >= 0 and d['primary'][leader] and d['purity'][leader] >= .7)
                    row[v+'_lead_pz_gev'] = float(d['col']['pz_mev'][leader]/1000) if leader >= 0 else np.nan
                # Normalize keys across old/new baselines for a rectangular table.
                for suffix in ['first_failed','primary_long','correct_leader','lead_pz_gev']:
                    row['baseline_'+suffix] = row.pop(base+'_'+suffix)
                rows.append(row)
    station.table(output/'truth_accepted_migration_events.tsv',rows)


def mode_migrations(data, der, groups, masks, cuts, output):
    rows = []; failures = []; accuracy = []; events = []
    for version,a in data.items():
        d = der[version]
        event_starts = np.searchsorted(d['idx'], np.arange(len(a['run'])+1))
        for left,right in [(0,1),(0,2),(1,2)]:
            for stage in ['track_pass','final','fixed_final']:
                p = d['control'][:,:,-1] if stage == 'fixed_final' else d[stage]
                for group,g in groups.items():
                    for name in ['fiducial','truth_station_acceptance']:
                        den = g & masks[name]
                        rows.append(dict(version=version,left=MODES[left],right=MODES[right],stage=stage,
                            group=group,denominator_name=name,**paired_binary(p[:,left],p[:,right],den)))
            lost = d['final'][:,left] & ~d['final'][:,right]
            for group,g in groups.items():
                total = 0
                for j,cut in enumerate(cuts):
                    before = np.ones(len(lost),bool) if j == 0 else ((a['event_cut_bits'][:,right] >> (j-1)) & 1).astype(bool)
                    fail = lost & g & before & (((a['event_cut_bits'][:,right] >> j) & 1) == 0)
                    n = int(fail.sum()); total += n
                    failures.append(dict(version=version,left=MODES[left],right=MODES[right],group=group,
                        first_failed_right_cut=cut,events=n,left_pass_right_fail=int((lost & g).sum())))
                assert total == int((lost & g).sum())
            l = d['leaders'][:,left]; r = d['leaders'][:,right]; il = np.maximum(l,0); ir = np.maximum(r,0)
            both = (l >= 0) & (r >= 0) & d['primary'][il] & d['primary'][ir] & (d['purity'][il] >= .7) & (d['purity'][ir] >= .7)
            for event in np.flatnonzero(lost):
                # Merge retains original candidates; compare all persisted summary fields,
                # including position, momentum, fit quality and truth identity.
                candidates = np.arange(event_starts[event],event_starts[event+1])
                candidates = candidates[d['col']['mode'][candidates] == right]
                left_summary = a['tracks'][l[event],5:]
                candidate_summary = a['tracks'][candidates,5:]
                equal = ((candidate_summary == left_summary) | (np.isnan(candidate_summary) & np.isnan(left_summary))).all(axis=1)
                events.append(dict(version=version,left=MODES[left],right=MODES[right],run=int(a['run'][event]),
                    eventID=int(a['eventID'][event]),truth_accepted=bool(masks['truth_station_acceptance'][event]),
                    left_raw_index=int(d['col']['raw_index'][l[event]]),
                    right_raw_index=int(d['col']['raw_index'][r[event]]) if r[event] >= 0 else -1,
                    left_leader_preserved_in_right_long=bool(equal.any()),
                    left_primary=bool(d['primary'][il[event]] and d['purity'][il[event]] >= .7),
                    right_primary=bool(r[event] >= 0 and d['primary'][ir[event]] and d['purity'][ir[event]] >= .7)))
            for st in range(3):
                t = a['primary_station'][:,st,5]
                x = a['reco_at_primary_station'][il,st,5]; y = a['reco_at_primary_station'][ir,st,5]
                valid = lost & both & np.isfinite(x) & np.isfinite(y) & np.isfinite(t) & (t > 0)
                x = abs(x[valid]/t[valid]-1); y = abs(y[valid]/t[valid]-1)
                lw = int((x < y-1e-10).sum()); rw = int((y < x-1e-10).sum())
                accuracy.append(dict(version=version,left=MODES[left],right=MODES[right],station=st+1,
                    scope='left_final_right_fail_common_primary',pairs=len(x),left_closer=lw,right_closer=rw,
                    ties=len(x)-lw-rw,left_median_absolute=float(np.median(x)) if len(x) else np.nan,
                    right_median_absolute=float(np.median(y)) if len(y) else np.nan,
                    sign_p=station.binomtest(rw,lw+rw).pvalue if lw+rw else np.nan))
    station.table(output/'mode_efficiency_migrations.tsv',rows)
    station.table(output/'mode_loss_first_failed_cut.tsv',failures)
    station.table(output/'mode_loss_station_accuracy.tsv',accuracy)
    station.table(output/'mode_loss_events.tsv',events)


def spectra(data, der, masks, output):
    rows = []
    edges = np.r_[station.EDGES[:-1], 20000, np.inf]
    for version, a in data.items():
        d = der[version]
        for m, mode in enumerate(MODES):
            leader = d['leaders'][:, m]; li = np.maximum(leader, 0)
            for st in range(3):
                truth = a['primary_station'][:, st, 3:] / 1000
                reco = a['reco_at_primary_station'][li, st, 3:] / 1000
                for quantity in ['p', 'pz']:
                    t = np.linalg.norm(truth, axis=1) if quantity == 'p' else truth[:, 2]
                    r = np.linalg.norm(reco, axis=1) if quantity == 'p' else reco[:, 2]
                    for scope, selected, value in [
                        ('truth_fiducial', masks['fiducial'], t),
                        ('truth_accepted', masks['truth_station_acceptance'], t),
                        ('leader', leader >= 0, r), ('track_cuts', d['track_pass'][:, m], r),
                        ('final', d['final'][:, m], r),
                        ('fixed_old_charge_final', d['control'][:, m, -1], r)]:
                        valid = selected & np.isfinite(value)
                        counts = np.histogram(value[valid], bins=edges)[0]
                        for lo, hi, n in zip(edges[:-1], edges[1:], counts):
                            rows.append(dict(version=version, mode=mode, station=st+1,
                                quantity=quantity, scope=scope, low_gev=lo, high_gev=hi, events=int(n),
                                selected=int(selected.sum()), missing_local=int((selected & ~np.isfinite(value)).sum()),
                                negative=int((valid & (value < 0)).sum())))
    station.table(output / 'momentum_spectra.tsv', rows)


def common_cohort(data, der, masks, output):
    rows = []
    fig, axes = plt.subplots(3, 3, figsize=(13, 11), constrained_layout=True)
    for m,mode in enumerate(MODES):
        for st in range(3):
            residual = {}
            for version,a in data.items():
                d = der[version]; leader = d['leaders'][:,m]; li = np.maximum(leader,0)
                valid = (leader >= 0) & d['primary'][li] & (d['purity'][li] >= .7)
                t = a['primary_station'][:,st,5]; r = a['reco_at_primary_station'][li,st,5]
                valid &= np.isfinite(t) & np.isfinite(r) & (t > 0)
                x = np.full(len(t),np.nan); x[valid] = r[valid]/t[valid]-1
                residual[version] = x
            common = np.logical_and.reduce([np.isfinite(x) for x in residual.values()])
            scopes = dict(common_primary_leaders=common,
                truth_accepted_common=common & masks['truth_station_acceptance'],
                all_final=common & np.logical_and.reduce([d['final'][:,m] for d in der.values()]))
            for scope,mask in scopes.items():
                for version,x in residual.items():
                    rows.append(dict(version=version,mode=mode,station=st+1,scope=scope,
                                     **station.residual_summary(x[mask])))
            for version,x in residual.items():
                q = np.linspace(0,1,1001)
                if common.any(): axes[st,m].plot(100*np.quantile(abs(x[common]),q),q,label=version)
            ax = axes[st,m]; ax.set_xscale('log'); ax.set_xlim(.1,300); ax.set_ylim(0,1)
            ax.set_title(f'{mode}, Station {st+1}'); ax.grid(alpha=.2)
            ax.set_xlabel('Absolute relative pz error [%]'); ax.set_ylabel('Cumulative fraction')
            ax.legend(fontsize=8)
    station.figure_save(fig,output,'common_station_accuracy')
    station.table(output/'common_cohort_station_accuracy.tsv',rows)


def main():
    started = time.monotonic()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--manifest', action='append', required=True, help='label=local manifest')
    p.add_argument('--allow-partial', action='store_true')
    args = p.parse_args(); out = args.output; out.mkdir(parents=True, exist_ok=True)
    data = {v: load(args.repo / f'workbook/stage203_station_truth/{v}.npz') for v in ['old', 'new']}
    audit = []; configurations = {}; manifests = {}; cutflows = []
    for item in args.manifest:
        label, path = item.split('=', 1)
        assert label not in data
        rows = [r.split('\t') for r in Path(path).read_text().splitlines()]
        assert all(r[1] == 'material' for r in rows)
        manifests[label] = rows
        # Extraction version is new; keep the map label separate from that coordinate convention.
        records = [r[:1] + ['new'] + r[2:] for r in rows]
        a, files = station.combine(records, 'new', out)
        (out / 'new.npz').rename(out / (label + '.npz'))
        original = out / (label + '_input_manifest.tsv')
        sources = {(int(r[0]), int(r[4])): r[5] for r in
                   (line.split('\t') for line in original.read_text().splitlines())} if original.exists() else {}
        for row, source in zip(files, rows):
            row['version'] = label
            with np.load(source[5]) as f:
                assert str(f['variant']) == 'material'
                effective = json.loads(str(f['effective_ablation_json']))
                cutflows.append((label, int(source[0]), f['counts'].copy()))
            filename = effective['geometry']['MaterialMapInputFile']
            assert 'material-rotated.json' in filename
            row['runtime_material_file'] = filename
            if sources: row['source_path'] = sources[row['index'], row['skip']]
            effective['geometry']['MaterialMapInputFile'] = 'material-rotated.json (worker scratch)'
            row.pop('effective_reco')
            if label in configurations: assert configurations[label] == effective, ('configuration drift', label)
            else: configurations[label] = effective
        audit += files; data[label] = a
    controls = list(configurations.values())
    assert all(c == controls[0] for c in controls), 'non-material configuration changed between maps'
    reference_ids = event_key(data[next(iter(manifests))])
    if args.allow_partial:
        from report_tracking_ablation import subset
        for v in ['old', 'new']: data[v] = subset(data[v], reference_ids)
    old = data['old']
    truth_keys = ['run', 'eventID', 'truth_pz_nu', 'truth_dec_x_nu', 'truth_dec_y_nu', 'truth_dec_z_nu',
                  'primary', 'primary_production_momentum_mev', 'primary_station', 'primary_layer_hits']
    for v, a in data.items():
        for k in truth_keys:
            assert np.array_equal(a[k], old[k], equal_nan=a[k].dtype.kind in 'fc'), (v, k)
        if not args.allow_partial:
            for k in ['all_run', 'all_eventID']: assert np.array_equal(a[k], old[k]), (v, k)
        if v != 'old': assert np.array_equal(a['scintillator'], data['new']['scintillator'], equal_nan=True), (v, 'charge drift')
    if not args.allow_partial:
        assert len(old['all_run']) == 3374987 and len(old['run']) == 383670
        for v in manifests: assert sum(r['events'] for r in audit if r['version'] == v) == 3374987
    # Recover each source science array from the sorted merged cache, beyond zip readback.
    from report_tracking_ablation import subset, ordered
    shard_checks = 0
    for label, rows in manifests.items():
        for row in rows:
            source = ordered(load(Path(row[5])))
            restored = subset(data[label], event_key(source))
            for k in station.EVENT_KEYS + station.TRACK_KEYS:
                assert np.array_equal(source[k], restored[k], equal_nan=source[k].dtype.kind in 'fc'), (label,row[0],row[4],k)
            shard_checks += 1
    masks = truth_masks(old)
    if not args.allow_partial: assert masks['truth_station_acceptance'].sum() == 140132
    groups = dict(all=np.ones(len(old['run']), bool), nominal=old['run'] != 200080)
    groups.update({str(r): old['run'] == r for r in np.unique(old['run'])})
    der = {v: station.derived(a) for v,a in data.items()}
    for v,a in data.items(): der[v]['control'] = station.controlled(a, old)
    assert np.array_equal(der['old']['control'], ((old['event_cut_bits'][:,:,None] >> np.arange(14)) & 1).astype(bool))
    if not args.allow_partial:
        assert der['old']['final'].sum(axis=0).tolist() == [92937,103985,104930]
        assert der['new']['final'].sum(axis=0).tolist() == [87986,99060,102760]
        assert der['new']['control'][:,:,-1].sum(axis=0).tolist() == [88961,100142,103883]
    comparisons = [('old','new')] + [(base,v) for v in manifests for base in ['old','new']]
    labels = list(manifests)
    comparisons += [(labels[i], labels[j]) for i in range(len(labels)) for j in range(i+1,len(labels))]
    cuts = [name for name,_ in selection(args.repo)[0]][6:]
    cutrows = []
    names = ['NoCuts'] + [name for name,_ in selection(args.repo)[0]]
    for label in manifests:
        total = np.sum([c for v,_,c in cutflows if v == label], axis=0)
        for m,mode in enumerate(MODES):
            for j,name in enumerate(names):
                cutrows.append(dict(version=label,mode=mode,cut=name,passed=int(total[m,j]),
                                    initial=int(total[m,0])))
    station.table(out/'full_input_cutflow.tsv',cutrows)
    cutrows = []
    for label,a in data.items():
        for m,mode in enumerate(MODES):
            for j,name in enumerate(cuts):
                cutrows.append(dict(version=label,mode=mode,cut=name,
                    truth_fiducial=len(a['run']),actual_passed=int(((a['event_cut_bits'][:,m] >> j)&1).sum()),
                    fixed_old_charge_passed=int(der[label]['control'][:,m,j].sum())))
    station.table(out/'fiducial_cutflow.tsv',cutrows)
    station.basic_metrics(data,der,out,groups,masks,cuts)
    residuals,bins = station.response_metrics(data,der,out,groups,masks,comparisons)
    station.particle_content(data,der,groups,out)
    station.local_cut_migrations(data,der,groups,out)
    duplicates(data,der,groups,masks,out)
    selection_pairs(data,der,groups,masks,comparisons,out)
    migration_events(data,der,masks,out)
    mode_migrations(data,der,groups,masks,cuts,out)
    spectra(data,der,masks,out)
    common_cohort(data,der,masks,out)
    station.plots(data,der,out,masks,residuals,bins)
    fixed = out / 'fixed_old_charge'; fixed.mkdir(exist_ok=True)
    fixed_data = {v: dict(a) for v,a in data.items()}; fixed_der = {v: dict(d) for v,d in der.items()}
    for v in data:
        fixed_data[v]['event_cut_bits'] = (der[v]['control'].astype(np.uint16) << np.arange(14,dtype=np.uint16)).sum(axis=2).astype(np.uint16)
        fixed_der[v]['final'] = der[v]['control'][:,:,-1]
    station.basic_metrics(fixed_data,fixed_der,fixed,groups,masks,cuts)
    station.response_metrics(fixed_data,fixed_der,fixed,groups,masks,comparisons,only_final=True)
    station.particle_content(fixed_data,fixed_der,groups,fixed)
    station.performance_summary(audit,out)
    (out/'source_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    (out/'effective_configurations.json').write_text(json.dumps(configurations,indent=2)+'\n')
    (out/'selection_definition.json').write_text((args.repo/'workbook/stage203_station_truth/selection_definition.json').read_text())
    summary = dict(versions=list(data), baseline_source='stage203 immutable full caches; old and new were not reconstructed again',
                   common_events=None if args.allow_partial else len(old['all_run']), common_truth_fiducial=len(old['run']),
                   truth_accepted=int(masks['truth_station_acceptance'].sum()), exact_truth=True,
                   exact_all_event_ids=not args.allow_partial, exact_new_waveforms=True, exact_cache_readback=True,
                   old_charge_self_control_all_cut_bits_exact=True,
                   same_effective_nonmaterial_configuration=True,
                   full_baseline_counts_verified=not args.allow_partial,
                   exact_shard_science_readback=True, checked_shards=shard_checks,
                   local_reference='SiHit station direction times linked HepMC production momentum magnitude',
                   transported_g4_local_momentum_measured=False, wall_s=time.monotonic()-started,
                   max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n'); print(json.dumps(summary),flush=True)


if __name__ == '__main__':
    main()
