#!/usr/bin/env python3
"""Stage34: locked models, one-pass PHYS extraction, ordered held-out evaluation."""
import argparse
import csv
import json
import resource
import time
from datetime import datetime, timezone
from pathlib import Path

import awkward as ak
import numpy as np
import uproot
import xgboost as xgb
import yaml

from track_response import TRACK_BRANCHES, derive, profile, configuration as track_configuration
from train_bdt import check_features, write_table


def stamp():
    return datetime.now(timezone.utc).isoformat()


def configuration(repo):
    return yaml.safe_load((repo / 'ml/configs/frozen_evaluation.yaml').read_text())


def manifest(repo):
    return list(csv.DictReader((repo / 'ml/configs/files.tsv').open(), delimiter='\t'))


def dataset(repo, part):
    return repo / f'ntuples/energy_ml_stage12/dataset/{part}.npz'


def cache(repo, part):
    return repo / f'ntuples/energy_ml_stage34/{part}.npz'


def reportdir(repo):
    path = repo / 'workbook/stage34_energy_ml'
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def truth_diagnostics(arr, tolerance):
    """Same primary/matching definition as stage15, with no station-truth reads."""
    truth = ['pdg', 'barcode', 'px', 'py', 'pz', 'm']
    truth += [f'{kind}_{axis}' for kind in ['prod', 'dec'] for axis in ['x', 'y', 'z']]
    for key in truth:
        if bool(ak.any(ak.num(arr['truth_' + key]) != ak.num(arr['truth_pdg']))):
            raise RuntimeError('Truth vector alignment: ' + key)
    for key in ['t_pdg', 't_barcode', 't_pdg_parent', 't_barcode_parent']:
        if bool(ak.any(ak.num(arr[key]) != ak.num(arr['Track_pz0']))):
            raise RuntimeError('Matching vector alignment: ' + key)
    candidate = arr['truth_pdg'] == ak.firsts(arr['truth_pdg']) * 13 / 14
    for axis in ['x', 'y', 'z']:
        candidate = candidate & (abs(arr['truth_prod_' + axis] - ak.firsts(arr['truth_dec_' + axis])) <= tolerance)
    n = ak.to_numpy(ak.sum(candidate, axis=1))
    valid = n == 1

    def primary(key):
        v = ak.to_numpy(ak.fill_none(ak.firsts(arr['truth_' + key][candidate]), np.nan)).astype(float)
        v[~valid] = np.nan
        return v

    p = np.sqrt(sum(primary(axis) ** 2 for axis in ['px', 'py', 'pz'])) / 1000
    energy = np.sqrt((p * 1000) ** 2 + primary('m') ** 2) / 1000
    enu = np.sqrt(sum(ak.to_numpy(ak.firsts(arr['truth_' + axis])) ** 2 for axis in ['px', 'py', 'pz', 'm'])) / 1000
    lead = ak.argmax(arr['Track_pz0'], axis=1, keepdims=True)
    matched = {k: ak.to_numpy(ak.flatten(arr[k][lead])) for k in ['t_pdg', 't_barcode', 't_pdg_parent', 't_barcode_parent']}
    confirmed = valid & (matched['t_pdg'] == primary('pdg')) & (matched['t_barcode'] == primary('barcode'))
    confirmed &= (matched['t_pdg_parent'] == ak.to_numpy(ak.firsts(arr['truth_pdg'])))
    confirmed &= (matched['t_barcode_parent'] == ak.to_numpy(ak.firsts(arr['truth_barcode'])))
    result = dict(primary_p_GeV=p, primary_valid=valid, primary_candidates=n,
                  truth_E_GeV=enu, y_lepton=1 - energy / enu, confirmed=confirmed)
    for axis in ['x', 'y', 'z']:
        result['vertex_' + axis + '_mm'] = ak.to_numpy(ak.firsts(arr['truth_dec_' + axis]))
    return result


def models(repo, cfg, base, extra):
    names = sum([base['feature_groups'][g] for g in base['feature_versions']['F5']], [])
    check_features(names, sum(base['feature_groups'].values(), []))
    result = {}
    for version, template in cfg['models'].items():
        ordered = names + (extra if version == 'F6' else [])
        result[version] = []
        for seed in cfg['seed_indices']:
            model = xgb.Booster(params={'nthread': 1})
            model.load_model(repo / template.format(seed=seed))
            assert model.feature_names == ordered
            result[version].append(model)
    return names, result


def extract(repo, part, batch, output, index=None):
    cfg = configuration(repo)
    # Enforce sequential unblinding, including extraction of labels.
    if part == 'test':
        assert (reportdir(repo) / 'calibration_state.json').exists()
    if part == 'challenge':
        assert (reportdir(repo) / 'test_summary.json').exists()
    base = yaml.safe_load((repo / 'ml/configs/baseline.yaml').read_text())
    extra = track_configuration(repo)['features']
    names, fitted = models(repo, cfg, base, extra)
    rows = [r for r in manifest(repo) if r['partition'] == part]
    rows = [r for r in rows if int(r['index']) == index] if index is not None else rows[batch * cfg['batch_size']:(batch + 1) * cfg['batch_size']]
    assert rows
    tick = time.perf_counter()
    cpu = time.process_time()
    with np.load(dataset(repo, part)) as z:
        assert json.loads(str(z['config_json'])) == base
        selected = {k: z[k] for k in names + ['eventID', 'run', 'manifest_index', 'ML_truth_E_GeV']}
    truth_branches = ['truth_' + k for k in ['pdg', 'barcode', 'px', 'py', 'pz', 'm']]
    truth_branches += [f'truth_{kind}_{axis}' for kind in ['prod', 'dec'] for axis in ['x', 'y', 'z']]
    branches = ['run', 'eventID', 'Track_PropagationError', 'Track_isForward'] + TRACK_BRANCHES + truth_branches
    branches += ['t_pdg', 't_barcode', 't_pdg_parent', 't_barcode_parent']
    parts = []
    reports = []
    for row in rows:
        start = time.perf_counter()
        old = np.flatnonzero(selected['manifest_index'] == int(row['index']))
        lookup = {int(selected['eventID'][i]): i for i in old}
        assert len(lookup) == len(old) == int(row['expected_selected'])
        with uproot.open(row['input']) as source:
            tree = source['nt']
            ids = tree['eventID'].array(library='np')
            mask = np.isin(ids, list(lookup))
            assert int(mask.sum()) == len(old)
            arr = tree.arrays(branches)[mask]
        track = derive(arr, extra)
        truth = truth_diagnostics(arr, 0.0001)
        order = np.array([lookup[int(e)] for e in track['eventID']])
        for key in ['run', 'eventID']:
            np.testing.assert_array_equal(track[key], selected[key][order])
        np.testing.assert_array_equal(track['reco_p_GeV'], selected['ML_mu_p_GeV'][order])
        np.testing.assert_array_equal(track['reco_charge'], selected['LeadTrack_charge'][order])
        np.testing.assert_allclose(truth['truth_E_GeV'], selected['ML_truth_E_GeV'][order], rtol=1e-12, atol=1e-10)
        data = dict(track, **truth, manifest_index=np.full(len(arr), int(row['index']), dtype=np.int32))
        infer_start = time.perf_counter()
        for version, fitted_models in fitted.items():
            columns = [selected[k][order] for k in names] + ([track[k] for k in extra] if version == 'F6' else [])
            x = np.column_stack(columns).astype(np.float32)
            x[~np.isfinite(x)] = np.nan
            for seed, model in enumerate(fitted_models):
                data[f'{version}_log_seed{seed}'] = model.inplace_predict(x, iteration_range=(0, model.best_iteration + 1))
        parts.append(data)
        info = dict(index=int(row['index']), input=row['input'], partition=part, input_events=len(ids),
                    selected_events=len(arr), wall_s=time.perf_counter() - start,
                    inference_wall_s=time.perf_counter() - infer_start)
        reports.append(info)
        print(json.dumps(info), flush=True)
    result = {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}
    meta = dict(cfg=cfg, partition=part, reports=reports, created_utc=stamp(), wall_s=time.perf_counter() - tick,
                cpu_s=time.process_time() - cpu, peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output, **result, metadata_json=np.array(json.dumps(meta)))
    print(json.dumps(meta), flush=True)


def read_cache(repo, part):
    with np.load(cache(repo, part)) as z:
        return {k: z[k] for k in z.files if k != 'metadata_json'}


def collect(repo, part):
    cfg = configuration(repo)
    rows = [r for r in manifest(repo) if r['partition'] == part]
    root = repo / 'ntuples/energy_ml_stage34'
    shards = []
    reports = []
    resources = []
    for batch in range((len(rows) + cfg['batch_size'] - 1) // cfg['batch_size']):
        with np.load(root / f'shards/{part}_{batch}.npz') as z:
            meta = json.loads(str(z['metadata_json']))
            assert meta['cfg'] == cfg and meta['partition'] == part
            reports += meta['reports']
            resources.append({k: meta[k] for k in ['created_utc', 'wall_s', 'cpu_s', 'peak_rss_MiB']})
            shards.append({k: z[k] for k in z.files if k != 'metadata_json'})
    assert sorted(r['index'] for r in reports) == sorted(int(r['index']) for r in rows)
    full = {k: np.concatenate([s[k] for s in shards]) for k in shards[0]}
    keys = list(zip(full['run'], full['eventID']))
    assert len(set(keys)) == len(keys)
    lookup = {key: i for i, key in enumerate(keys)}
    with np.load(dataset(repo, part)) as old:
        idx = np.array([lookup[key] for key in zip(old['run'], old['eventID'])])
        data = {k: v[idx] for k, v in full.items()}
        for k in ['run', 'eventID', 'manifest_index']:
            np.testing.assert_array_equal(data[k], old[k])
        np.testing.assert_array_equal(data['reco_p_GeV'], old['ML_mu_p_GeV'])
        np.testing.assert_allclose(data['truth_E_GeV'], old['ML_truth_E_GeV'], rtol=1e-12)
        for axis in ['x', 'y', 'z']:
            np.testing.assert_array_equal(data['vertex_' + axis + '_mm'], old['truth_dec_' + axis + '_nu'])
        data['group'] = old['group']
    components = {int(r['index']): r['component'] for r in rows}
    data['component'] = np.array([components[int(i)] for i in data['manifest_index']])
    np.savez_compressed(cache(repo, part), **data, metadata_json=np.array(json.dumps(dict(cfg=cfg, created_utc=stamp()))))
    with np.load(cache(repo, part)) as check:
        for k, v in data.items():
            np.testing.assert_array_equal(v, check[k])
    out = reportdir(repo)
    write_table(out / f'{part}_extraction_files.tsv', reports)
    write_table(out / f'{part}_extraction_jobs.tsv', resources)
    features = track_configuration(repo)['features']
    write_table(out / f'{part}_feature_profile.tsv', profile(data, features))
    save_json(out / f'{part}_extraction_summary.json', dict(files=len(rows), events=len(idx), groups=len(np.unique(data['group'])),
              input_events=sum(r['input_events'] for r in reports), cache_bytes=cache(repo, part).stat().st_size,
              extraction_wall_s=sum(r['wall_s'] for r in resources), extraction_cpu_s=sum(r['cpu_s'] for r in resources),
              peak_rss_MiB=max(r['peak_rss_MiB'] for r in resources),
              all_19_finite=int(np.isfinite(np.column_stack([data[k] for k in features])).all(axis=1).sum()),
              lead_isForward_false=int((~data['lead_isForward']).sum()), readback_verified=True, created_utc=stamp()))


def logs(data):
    return {v: np.mean(np.stack([data[f'{v}_log_seed{i}'].astype(float) for i in range(3)]), axis=0) for v in ['F5', 'F6']}


def calibrate(repo):
    out = reportdir(repo)
    assert not (out / 'calibration_state.json').exists(), 'Calibration is already frozen'
    data = read_cache(repo, 'calibration')
    pred = logs(data)
    offset = {v: float(np.mean(np.log(data['truth_E_GeV']) - p)) for v, p in pred.items()}
    state = dict(created_utc=stamp(), events=len(data['run']), groups=len(np.unique(data['group'])), offset_log=offset,
                 multiplicative_scale={v: float(np.exp(c)) for v, c in offset.items()}, parameters=2,
                 definition=configuration(repo)['calibration'], frozen_before_test=True)
    save_json(out / 'calibration_state.json', state)
    print(json.dumps(state), flush=True)


def smoke(repo, filename, output):
    """Validation-only equality checks against all six already published predictions."""
    tick = time.perf_counter()
    with np.load(filename) as z:
        data = {k: z[k] for k in z.files if k != 'metadata_json'}
    key = list(zip(data['run'], data['eventID']))
    with np.load(repo / 'ntuples/energy_ml_stage31/validation_tracks.npz') as old:
        lookup = {k: i for i, k in enumerate(zip(old['run'], old['eventID']))}
        index = [lookup[k] for k in key]
        for k in track_configuration(repo)['features'] + ['reco_p_GeV', 'reco_charge', 'lead_isForward']:
            np.testing.assert_array_equal(data[k], old[k][index])
    with np.load(repo / 'ntuples/energy_ml_stage15/validation_truth.npz') as old:
        lookup = {k: i for i, k in enumerate(zip(old['run'], old['eventID']))}
        index = [lookup[k] for k in key]
        for k in ['primary_p_GeV', 'primary_valid', 'y_lepton', 'truth_E_GeV']:
            np.testing.assert_allclose(data[k], old[k][index], rtol=1e-12, atol=1e-12)
        np.testing.assert_array_equal(data['confirmed'], old['lead_primary_parent_confirmed'][index])
    differences = {}
    for v, folder, oldname in [('F5', 'stage30/main', 'A0'), ('F6', 'stage31', 'nu_F6')]:
        for seed in range(3):
            with np.load(repo / f'ml/artifacts/{folder}/seed_{seed}/predictions.npz') as old:
                lookup = {k: i for i, k in enumerate(zip(old['run'], old['eventID']))}
                index = [lookup[k] for k in key]
                pred = np.exp(data[f'{v}_log_seed{seed}'])
                np.testing.assert_array_equal(pred, old[oldname][index])
                differences[f'{v}_seed{seed}_max_abs_GeV'] = float(np.max(abs(pred - old[oldname][index])))
    save_json(output, dict(events=len(key), all_19_features_equal=True, truth_and_matching_equal=True,
                         predictions_equal=differences, wall_s=time.perf_counter() - tick, created_utc=stamp()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['extract', 'collect', 'calibrate', 'smoke'])
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--partition', choices=['validation', 'calibration', 'test', 'challenge'])
    parser.add_argument('--batch', type=int, default=0)
    parser.add_argument('--index', type=int)
    parser.add_argument('--input', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.action == 'extract':
        extract(args.repo, args.partition, args.batch, args.output, args.index)
    elif args.action == 'collect':
        collect(args.repo, args.partition)
    elif args.action == 'calibrate':
        calibrate(args.repo)
    else:
        smoke(args.repo, args.input, args.output)


if __name__ == '__main__':
    main()
