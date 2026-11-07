"""Paired exact-current identity, typed readout and unmodified covariance QA."""
import csv
import gzip
import json
import resource
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import awkward as ak
import numpy as np
import uproot

root, phase, ntuple = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
out, cache = root/'workbook/stage149_energy_ml'/phase, root/'ntuples/energy_ml_stage149'/phase
plan = json.loads((out.parent/'protocol.json').read_text())
with gzip.open(cache/'native.json.gz', 'rt') as stream:
    native = json.load(stream)
seeds = json.loads((out/'seeds.json').read_text())
with gzip.open(root/plan['old_identity_records'], 'rt') as stream:
    capsule = json.load(stream)
old_roots = json.loads(capsule['workbook/stage146_energy_ml/full_roots.json.gz'])
old_ids = json.loads(capsule['workbook/stage146_energy_ml/identity_records.json.gz'])
count = len(native['records'])
cpu, tick = time.process_time(), time.perf_counter()
groups = defaultdict(list)
prefix = dict(calo='Calo', vetonu='VetoNu', veto1='Veto1', veto2='Veto2', trigger='Timing', preshower='Preshower')
for channel, kind, identifier in native['cable_mapping']:
    if kind in prefix:
        groups[kind].append(int(channel))
mapping = {channel: prefix[kind]+str(index) for kind, channels in groups.items()
           for index, channel in enumerate(sorted(channels))}
fields = ['raw_charge', 'raw_peak', 'baseline', 'baseline_rms', 'status']
track_fields = ['Track_pz0', 'Track_px0', 'Track_py0', 'Track_x0', 'Track_y0', 'Track_z0',
                'Track_charge', 'Track_Chi2', 'Track_nDoF', 'Track_nLayers']
branches = ['run', 'eventID', 'longTracks']+track_fields
branches += [name+'_'+field for name in mapping.values() for field in fields]
with uproot.open(ntuple, array_cache=None) as file:
    missing = sorted(set(branches)-set(file['nt'].keys()))
    assert not missing, missing
    array = file['nt'].arrays(branches)
    read_bytes = int(file.file.source.num_requested_bytes)
assert len(array) == count
with uproot.open(plan['old_PHYS'], array_cache=None) as file:
    old = file['nt'].arrays(['run', 'eventID', 'longTracks', 'Track_pz0', 'Track_Chi2', 'Track_nDoF', 'Track_nLayers'], entry_stop=count)
    old_read_bytes = int(file.file.source.num_requested_bytes)


def exact(a, b):
    return bool(np.array_equal(np.asarray(a, dtype=np.float32), np.asarray(b, dtype=np.float32)))


def clean(value, positive=False):
    if not np.isfinite(value) or value in [-999., -9999., -99999.] or (positive and value <= 0):
        return None
    return float(value)


def selected(row):
    pz = np.asarray(row.Track_pz0, dtype=float)
    if not len(pz):
        return False
    k = int(np.argmax(pz))
    chi, ndof, layers = float(row.Track_Chi2[k]), float(row.Track_nDoF[k]), int(row.Track_nLayers[k])
    return bool(int(row.longTracks) == 1 and 50000 < pz[k] < 2000000 and
                np.isfinite(chi) and chi >= 0 and ndof > 0 and chi/ndof < 10 and layers >= 7)


records, covariance_rows, charge_rows = [], [], []
for i, event in enumerate(native['records']):
    current = array[i]
    seed = seeds['records'][i]
    identity = (event['run'], event['event'])
    run_event = identity == (int(current.run), int(current.eventID)) == (seed['run'], seed['event'])
    previous = old_roots[i]
    old_run_event = identity == (previous['run'], previous['event']) == (int(old[i].run), int(old[i].eventID))
    prior_roots = [p for graph in previous['graphs'] for p in graph['roots']]
    root_exact = len(prior_roots) == len(seed['roots']) and all(
        a['pdg'] == b['pdg'] and exact(a['p4'], b['p4']) and exact(a['vertex'], b['vertex'])
        for a, b in zip(prior_roots, seed['roots']))
    tracks = event['tracks']
    nt_pz = list(current.Track_pz0)
    all_tracks_exact = len(tracks) == len(nt_pz)
    for k, track in enumerate(tracks):
        state = track['state']
        target = [float(current[name][k]) for name in ['Track_x0', 'Track_y0', 'Track_z0',
            'Track_px0', 'Track_py0', 'Track_pz0', 'Track_charge', 'Track_Chi2', 'Track_nDoF']]
        all_tracks_exact &= exact(state, target) and track['layers'] == int(current.Track_nLayers[k])
    leading = max(range(len(tracks)), key=lambda k: tracks[k]['state'][5]) if tracks else None
    native_leading = tracks[leading] if leading is not None else None
    covariance = dict(available=False, finite=False, symmetric=False, PSD=None, positive_definite=None)
    if native_leading and len(native_leading['covariance']) == 25:
        matrix = np.asarray(native_leading['covariance']).reshape(5, 5)
        finite = bool(np.isfinite(matrix).all())
        diagonal = np.diag(matrix)
        positive = bool(finite and (diagonal > 0).all())
        covariance.update(available=True, finite=finite, symmetric=bool(finite and np.array_equal(matrix, matrix.T)),
                          diagonal=diagonal.tolist(), offdiagonal_N=int(np.count_nonzero(matrix-np.diag(diagonal))))
        if positive:
            scale = np.sqrt(diagonal)
            correlation = matrix/scale[:, None]/scale[None, :]
            eigen = np.linalg.eigvalsh(correlation)
            covariance.update(PSD=bool(eigen[0] >= -64*np.finfo(float).eps), positive_definite=bool(eigen[0] > 0),
                min_correlation_eigenvalue=float(eigen[0]), max_abs_offdiagonal_correlation=float(np.max(abs(correlation-np.eye(5)))),
                sigma=scale.tolist())
        covariance_rows.append(dict(entry=i, run=identity[0], event=identity[1], pz0_GeV=native_leading['state'][5]/1000,
            selected=selected(current), surface=native_leading['surface_type'], parameter_type=native_leading['parameter_type'], **covariance))
    by_channel = {row['channel']: row for row in event['waves']}
    readout, raw_exact = [], True
    for channel, name in sorted(mapping.items()):
        hit = by_channel.get(channel)
        actual = {field: float(current[name+'_'+field]) for field in fields}
        same = hit is None or all(exact(hit[field], actual[field]) for field in fields)
        raw_exact &= same
        status = int(actual['status'])
        present = hit is not None and actual['baseline_rms'] > 0 and status & (8|128|256) == 0
        measured = dict(channel=channel, name=name, native_present=hit is not None, present=bool(present),
                        status=status, exact=bool(same), stored=actual,
                        raw_charge_pC=clean(actual['raw_charge']) if present else None,
                        raw_peak_mV=clean(actual['raw_peak'], positive=True) if present else None,
                        baseline_rms_mV=clean(actual['baseline_rms'], positive=True) if present else None)
        readout.append(measured)
        charge_rows.append(dict(entry=i, channel=channel, name=name, native_present=hit is not None,
            present=bool(present), status=status, raw_charge_pC=measured['raw_charge_pC'],
            baseline_rms_mV=measured['baseline_rms_mV'], exact=same))
    record = dict(entry=i, run=identity[0], event=identity[1], run_event_exact=run_event,
        old_run_event_exact=old_run_event, old_roots_float32_exact=root_exact,
        old_identity_reason=old_ids[i]['reason'], old_selected=selected(old[i]), new_selected=selected(current),
        all_tracks_float32_exact=bool(all_tracks_exact), leading_index=leading,
        leading_identity_exact=bool(all_tracks_exact and leading is not None and leading == int(np.argmax(nt_pz))),
        raw15_exact=bool(raw_exact), covariance_QA=covariance, readout=readout,
        same_surface_truth_available=False, covariance_pull=None, tracking_bias=None)
    records.append(record)
    assert run_event and old_run_event and root_exact and all_tracks_exact and raw_exact

with gzip.open(cache/'paired.json.gz', 'wt') as stream:
    json.dump(records, stream, separators=(',', ':'), allow_nan=False)
for name, rows in [('covariance', covariance_rows), ('charge', charge_rows)]:
    with (out/(name+'.tsv')).open('w') as stream:
        columns = list(dict.fromkeys(key for row in rows for key in row))
        writer = csv.DictWriter(stream, fieldnames=columns, delimiter='\t', restval='NA', lineterminator='\n') if rows else None
        if writer:
            writer.writeheader()
            writer.writerows({k: json.dumps(v, separators=(',', ':')) if isinstance(v, (list, dict)) else 'NA' if v is None else v
                             for k, v in row.items()} for row in rows)
summary = dict(passed=True, N=count, new_selected_N=sum(r['new_selected'] for r in records),
    old_selected_N=sum(r['old_selected'] for r in records), leading_exact_N=sum(r['leading_identity_exact'] for r in records),
    finite_covariance_N=sum(r['covariance_QA']['finite'] for r in records),
    selected_finite_covariance_N=sum(r['new_selected'] and r['covariance_QA']['finite'] for r in records),
    PSD_N=sum(r['covariance_QA']['PSD'] is True for r in records),
    raw15_exact_N=sum(r['raw15_exact'] for r in records), channels=len(mapping),
    measured_readout_channel_views_N=sum(r['present'] for r in charge_rows),
    readout_status=dict(Counter(str(r['status']) for r in charge_rows)),
    full_same_surface_truth_pull_measured=False, association_probability_measured=False,
    metadata_limit='Actual input metadata retained separately; flags do not certify input transport or data transfer',
    same_current_identity='All long tracks, leading state and raw/status/baseline match at actual float32 ntuple precision',
    CPU_s=time.process_time()-cpu, wall_s=time.perf_counter()-tick, ROOT_read_bytes=read_bytes+old_read_bytes,
    RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
(out/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
print(summary, flush=True)
