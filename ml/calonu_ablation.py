#!/usr/bin/env python3
"""Six fixed-budget CaloNu readout fits, with calibration before held-out prediction."""
import argparse
import json
import resource
import time
from pathlib import Path

import numpy as np
import xgboost as xgb
import yaml

from calonu_inputs import configuration, extract, feature_names, load, manifest
from frozen_evaluation import save_json, stamp
from train_bdt import write_table


def root(repo):
    return repo / 'ntuples/energy_ml_stage35'


def reports(repo):
    path = repo / 'workbook/stage35_energy_ml'
    path.mkdir(parents=True, exist_ok=True)
    return path


def collect(repo):
    cfg = configuration(repo)
    rows = manifest(repo)
    shards = []
    files = []
    jobs = []
    for batch in range((len(rows) + cfg['batch_size'] - 1) // cfg['batch_size']):
        with np.load(root(repo) / f'shards/{batch}.npz') as z:
            meta = json.loads(str(z['metadata_json']))
            assert meta['cfg'] == cfg
            shards.append({k: z[k] for k in z.files if k != 'metadata_json'})
            files += meta['reports']
            jobs.append({k: meta[k] for k in ['wall_s', 'cpu_s', 'peak_rss_MiB']})
    assert sorted(f['index'] for f in files) == list(range(len(rows)))
    full = {k: np.concatenate([s[k] for s in shards]) for k in shards[0]}
    assert len(set(zip(full['run'], full['eventID']))) == len(full['run'])
    summary = dict(files=len(rows), input_events=sum(f['input_events'] for f in files),
                   selected_events=len(full['run']), extraction_wall_s=sum(j['wall_s'] for j in jobs),
                   extraction_cpu_s=sum(j['cpu_s'] for j in jobs), peak_rss_MiB=max(j['peak_rss_MiB'] for j in jobs), partitions={})
    for part in cfg['partitions']:
        keep = full['partition'] == part
        order = np.flatnonzero(keep)
        order = order[np.lexsort((full['eventID'][order], full['run'][order]))]
        data = {k: v[order] for k, v in full.items()}
        path = root(repo) / f'{part}.npz'
        np.savez_compressed(path, **data, metadata_json=np.array(json.dumps(dict(cfg=cfg, created_utc=stamp()))))
        with np.load(path) as z:
            for k, v in data.items():
                np.testing.assert_array_equal(v, z[k])
        summary['partitions'][part] = dict(events=len(order), groups=len(np.unique(data['group'])), bytes=path.stat().st_size,
                                           readback_verified=True)
    cutnames = [r['cut'] for r in __import__('csv').DictReader((repo / 'workbook/stage09_tracking_comparison/cut_definitions.tsv').open(), delimiter='\t')]
    cutflow = np.sum([f['cutflow'] for f in files], axis=0)
    write_table(reports(repo) / 'extraction_cutflow.tsv', [dict(cut=c, passed=int(n)) for c, n in zip(['input'] + cutnames, cutflow)])
    write_table(reports(repo) / 'extraction_files.tsv', [{k: v for k, v in f.items() if k != 'cutflow'} for f in files])
    write_table(reports(repo) / 'extraction_jobs.tsv', jobs)
    # Deliberately no held-out distribution profiling here; only technical collection.
    save_json(reports(repo) / 'extraction_summary.json', summary)
    print(json.dumps(summary), flush=True)


class Limit(xgb.callback.TrainingCallback):
    def __init__(self, seconds):
        self.start = time.perf_counter()
        self.seconds = seconds
        self.hit = False

    def after_iteration(self, model, epoch, evals_log):
        self.hit = time.perf_counter() - self.start >= self.seconds
        return self.hit


def matrix(data, names):
    x = np.column_stack([data[k] for k in names]).astype(np.float32)
    x[~np.isfinite(x)] = np.nan
    return x


def train(repo, seed_index, output, smoke=False):
    cfg = configuration(repo)
    tick = time.perf_counter()
    cpu = time.process_time()
    # This process never opens calibration/test files.
    fit, stop = [load(repo, p) for p in ['fit', 'stop']]
    assert not set(fit['group']) & set(stop['group'])
    if smoke:
        fit = {k: v[:900] for k, v in fit.items()}
        stop = {k: v[:400] for k, v in stop.items()}
    seed = cfg['seeds'][seed_index]
    names, extra = feature_names(repo)
    features = names + extra
    params = yaml.safe_load((repo / 'ml/configs/baseline.yaml').read_text())['xgboost']
    params = {k: v for k, v in params.items() if k not in ['n_estimators', 'early_stopping_rounds', 'n_jobs']}
    params.update(max_depth=cfg['xgboost']['max_depth'], seed=seed, nthread=cfg['xgboost']['nthread'], objective='reg:squarederror')
    output.mkdir(parents=True, exist_ok=True)
    costs = []
    traces = {}
    for version in cfg['models']:
        ordered = features + (cfg['features'] if version == 'C1' else [])
        assert not any(k.startswith(('truth', 't_', 'run', 'event', 'primary')) for k in ordered)
        dfit = xgb.DMatrix(matrix(fit, ordered), label=np.log(fit['truth_E_GeV']), feature_names=ordered, nthread=4)
        dstop = xgb.DMatrix(matrix(stop, ordered), label=np.log(stop['truth_E_GeV']), feature_names=ordered, nthread=4)
        history = {}
        start = time.perf_counter()
        cstart = time.process_time()
        limit = Limit(cfg['max_fit_wall_s'])
        model = xgb.train(params, dfit, num_boost_round=20 if smoke else cfg['xgboost']['rounds'],
                          evals=[(dfit, 'fit'), (dstop, 'stop')], early_stopping_rounds=cfg['xgboost']['patience'],
                          evals_result=history, callbacks=[limit], verbose_eval=False)
        wall = time.perf_counter() - start
        used = time.process_time() - cstart
        model.save_model(output / (version + '.ubj'))
        traces[version] = history
        costs.append(dict(model=version, seed_index=seed_index, seed=seed, features=len(ordered), fit_events=len(fit['run']),
                          stop_events=len(stop['run']), best_iteration=model.best_iteration, stored_trees=model.num_boosted_rounds(),
                          stop_reason='time' if limit.hit else 'rounds' if model.num_boosted_rounds() == (20 if smoke else cfg['xgboost']['rounds']) else 'patience',
                          fit_wall_s=wall, fit_cpu_s=used, model_bytes=(output / (version + '.ubj')).stat().st_size))
        print(json.dumps(costs[-1]), flush=True)
    write_table(output / 'costs.tsv', costs)
    save_json(output / 'learning_traces.json', traces)
    save_json(output / 'summary.json', dict(cfg=cfg, seed_index=seed_index, seed=seed, smoke=smoke, created_utc=stamp(),
              fit_groups=sorted(np.unique(fit['group']).tolist()), stop_groups=sorted(np.unique(stop['group']).tolist()),
              calibration_test_read=False, wall_s=time.perf_counter() - tick, cpu_s=time.process_time() - cpu,
              peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024))


def predict(repo, data):
    cfg = configuration(repo)
    names, extra = feature_names(repo)
    result = {}
    for version in cfg['models']:
        ordered = names + extra + (cfg['features'] if version == 'C1' else [])
        x = matrix(data, ordered)
        raw = []
        for i in range(3):
            model = xgb.Booster(params={'nthread': 1})
            model.load_model(repo / f'ml/artifacts/stage35/seed_{i}/{version}.ubj')
            assert model.feature_names == ordered
            raw.append(model.inplace_predict(x, iteration_range=(0, model.best_iteration + 1)).astype(float))
        result[version] = np.mean(raw, axis=0)
    return result


def calibrate(repo):
    state = reports(repo) / 'calibration_state.json'
    assert not state.exists()
    cfg = configuration(repo)
    for i in range(3):
        saved = json.loads((reports(repo) / f'seed_{i}/summary.json').read_text())
        if 'shared_training_file' in saved:
            saved = {**json.loads((reports(repo) / saved['shared_training_file']).read_text()), **saved}
        assert saved['cfg'] == cfg and not saved['smoke'] and not saved['calibration_test_read']
    data = load(repo, 'calibration')
    tick = time.perf_counter()
    pred = predict(repo, data)
    np.savez_compressed(root(repo) / 'calibration_predictions.npz', **pred)
    offsets = {v: float(np.mean(np.log(data['truth_E_GeV']) - p)) for v, p in pred.items()}
    save_json(state, dict(created_utc=stamp(), offset_log=offsets, events=len(data['run']), groups=len(np.unique(data['group'])),
                         multiplicative_scale={v: float(np.exp(c)) for v, c in offsets.items()},
                         parameters=2, six_models_frozen=True, test_not_evaluated=True,
                         inference_wall_s=time.perf_counter() - tick))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['extract', 'collect', 'train', 'calibrate'])
    p.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--batch', type=int, default=0)
    p.add_argument('--index', type=int)
    p.add_argument('--seed-index', type=int, default=0)
    p.add_argument('--smoke', action='store_true')
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    if a.action == 'extract':
        extract(a.repo, a.batch, a.output, a.index)
    elif a.action == 'collect':
        collect(a.repo)
    elif a.action == 'train':
        train(a.repo, a.seed_index, a.output, a.smoke)
    else:
        calibrate(a.repo)


if __name__ == '__main__':
    main()
