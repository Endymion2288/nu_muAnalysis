#!/usr/bin/env python3
"""Bounded CaloNu muon response extraction, with independent scintillator selection."""
import argparse
import csv
import json
import resource
import time
from pathlib import Path

import awkward as ak
import numpy as np
import uproot


def config(repo):
    return json.loads((repo / 'ml/configs/calonu_muon_control.json').read_text())


def manifest(repo):
    return list(csv.DictReader((repo / 'ml/configs/calonu_muon_files.tsv').open(), delimiter='\t'))


def output_dir(repo):
    p = repo / 'workbook/stage36_energy_ml'
    p.mkdir(parents=True, exist_ok=True)
    return p


def cache_dir(repo):
    return repo / config(repo)['cache']


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def branches():
    names = ['run', 'eventID', 'eventTime', 'longTracks', 'distanceToCollidingBCID', 'TBP', 'TAP']
    names += ['Track_' + k for k in ['p0', 'pz0', 'nLayers', 'nDoF', 'Chi2', 'X_atVetoNu', 'Y_atVetoNu',
                                    'ThetaX_atVetoNu', 'ThetaY_atVetoNu']]
    names += [k + '_raw_charge' for k in ['VetoNu0', 'VetoNu1', 'Veto20', 'Veto21']]
    names += [f'CaloNu{i}_{k}' for i in range(4) for k in ['charge', 'raw_charge', 'nMIP', 'E_EM', 'status',
                                                                    'raw_peak', 'baseline_rms']]
    names += ['CaloNu_total_' + k for k in ['E_EM', 'fit_E_EM', 'raw_E_EM']]
    return names


def selection(arr, sample, grl):
    idx = ak.argmax(arr['Track_pz0'], axis=1, keepdims=True)
    values = {}
    for key in branches():
        if key.startswith('Track_'):
            assert bool(ak.all(ak.num(arr[key]) == ak.num(arr['Track_pz0'])))
            values[key] = ak.to_numpy(ak.fill_none(ak.firsts(arr[key][idx]), np.nan))
        else:
            values[key] = ak.to_numpy(arr[key])
    cuts = []
    stable = np.ones(len(arr), bool)
    if sample == 'data':
        stable[:] = False
        for run in np.unique(values['run']):
            record = grl[str(int(run))]
            same = values['run'] == run
            good = np.zeros(len(arr), bool)
            for interval in record['stable_list']:
                good |= (values['eventTime'] >= interval['start_utime']) & (values['eventTime'] <= interval['stop_utime'])
            for interval in record.get('excluded_list', []):
                good &= ~((values['eventTime'] >= interval['start_utime']) & (values['eventTime'] <= interval['stop_utime']))
            stable |= same & good
        stable &= values['distanceToCollidingBCID'] == 0
    cuts.append(('stable_colliding_if_data', stable))
    cuts.append(('one_long_track', values['longTracks'] == 1))
    with np.errstate(divide='ignore', invalid='ignore'):
        quality = (values['Track_nLayers'] >= 7) & (values['Track_nDoF'] >= 9) & (values['Track_Chi2'] / values['Track_nDoF'] < 15)
    cuts.append(('track_quality', quality))
    cuts.append(('reco_p_100_1000_GeV', (values['Track_p0'] >= 100000) & (values['Track_p0'] < 1000000)))
    cuts.append(('valid_vetonu_extrapolation', (abs(values['Track_X_atVetoNu']) < 500) & (abs(values['Track_Y_atVetoNu']) < 500)
                 & (np.hypot(values['Track_ThetaX_atVetoNu'], values['Track_ThetaY_atVetoNu']) < .025)))
    cuts.append(('independent_scintillator_coincidence', np.logical_and.reduce([values[k + '_raw_charge'] > 40 for k in ['VetoNu0', 'VetoNu1', 'Veto20', 'Veto21']])))
    keep = np.ones(len(arr), bool)
    counts = [dict(cut='input', passed=len(arr))]
    for name, cut in cuts:
        keep &= cut
        counts.append(dict(cut=name, passed=int(keep.sum())))
    return {k: v[keep] for k, v in values.items()}, counts


def extract(repo, index, output, limit=None):
    tick, cpu = time.perf_counter(), time.process_time()
    row = manifest(repo)[index]
    cfg = config(repo)
    grl = json.loads((repo / 'ml/configs/calonu_muon_grl.json').read_text())
    stop = min(int(row['entry_stop']), limit) if limit is not None else int(row['entry_stop'])
    with uproot.open(row['input']) as f:
        total = f['nt'].num_entries
        arr = f['nt'].arrays(branches(), entry_stop=stop)
    values, cutflow = selection(arr, row['sample'], grl)
    assert np.all(values['run'] == int(row['run']))
    n = len(values['run'])
    data = {k: v.astype(np.float32) if v.dtype.kind == 'f' else v for k, v in values.items()}
    data.update(group_index=np.full(n, index, np.int16))
    metadata = dict(index=index, sample=row['sample'], run=int(row['run']), group=row['group'], input=row['input'],
                    file_entries=total, read_entries=len(arr), selected=n, cutflow=cutflow,
                    max_float32_absolute_difference={k: float(np.max(abs(values[k][np.isfinite(values[k])] - v[np.isfinite(values[k])])))
                                                    for k, v in data.items() if k in values and v.dtype.kind == 'f' and np.isfinite(values[k]).any()},
                    wall_s=time.perf_counter()-tick, cpu_s=time.process_time()-cpu,
                    peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                    protocol_frozen_utc=cfg['frozen_utc'], smoke=limit is not None)
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output, **data, metadata_json=np.array(json.dumps(metadata)))
    print(json.dumps(metadata), flush=True)


def collect(repo):
    records = []
    samples = {s: [] for s in ['MC', 'data']}
    for row in manifest(repo):
        with np.load(cache_dir(repo) / f'shards/{row["index"]}.npz') as z:
            record = json.loads(str(z['metadata_json']))
            assert not record['smoke'] and record['group'] == row['group']
            assert record['protocol_frozen_utc'] == config(repo)['frozen_utc']
            records.append(record)
            item = {k: z[k] for k in z.files if k != 'metadata_json'}
            assert len(item['run']) == record['selected']
            # A merged PG file contains five generators whose eventID each restarts.
            # Preserve file + selected-row identity, rather than dropping ID collisions.
            item['source_selected_row'] = np.arange(len(item['run']), dtype=np.int32)
            samples[row['sample']].append(item)
    result = dict(files=len(records), input_events=sum(r['read_entries'] for r in records),
                  extraction_wall_s=sum(r['wall_s'] for r in records), extraction_cpu_s=sum(r['cpu_s'] for r in records),
                  peak_rss_MiB=max(r['peak_rss_MiB'] for r in records), samples={})
    for sample, items in samples.items():
        values = {k: np.concatenate([d[k] for d in items]) for k in items[0]}
        assert len(set(zip(values['group_index'], values['source_selected_row']))) == len(values['run'])
        path = cache_dir(repo) / f'{sample}.npz'
        np.savez_compressed(path, **values)
        with np.load(path) as z:
            for k, v in values.items():
                np.testing.assert_array_equal(z[k], v)
        result['samples'][sample] = dict(events=len(values['run']), groups=len(np.unique(values['group_index'])),
                                       bytes=path.stat().st_size, all_field_readback_equal=True,
                                       distinct_run_event_pairs=len(set(zip(values['run'], values['eventID']))),
                                       unique_file_selected_row_keys=True,
                                       identity_note=('PG eventID restarts within merged generation files; no collision removed; file and selected row preserve identity'
                                                      if sample == 'MC' else 'run/eventID unique in this cohort; file and selected row also preserve identity'))
    write_json(output_dir(repo) / 'extraction_summary.json', result)
    write_json(output_dir(repo) / 'extraction_files.json', records)
    print(json.dumps(result), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['extract', 'collect'])
    p.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--index', type=int, default=0)
    p.add_argument('--limit', type=int)
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    if a.action == 'extract':
        extract(a.repo, a.index, a.output, a.limit)
    else:
        collect(a.repo)


if __name__ == '__main__':
    main()
