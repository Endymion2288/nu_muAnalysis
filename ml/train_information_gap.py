#!/usr/bin/env python3
"""Fixed-capacity, same-event oracle factorial and train-isolated representations."""
import argparse
import json
import resource
import time
from pathlib import Path

import numpy as np
import xgboost as xgb

from information_gap import (calibrate, calibrated, class_index, configuration, inputs,
                             scalar_mapping, split_groups, ten_bin_mapping)
from train_bdt import write_table


class Limit(xgb.callback.TrainingCallback):
    def __init__(self, seconds):
        self.start = time.perf_counter(); self.seconds = seconds; self.hit = False

    def after_iteration(self, model, epoch, evals_log):
        self.hit = time.perf_counter() - self.start >= self.seconds
        return self.hit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--seed-index', type=int, required=True)
    parser.add_argument('--mode', choices=['main', 'controls'], default='main')
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args(); cfg = configuration(args.repo)
    tick = time.perf_counter(); cpu = time.process_time()
    out = args.output_dir; out.mkdir(parents=True, exist_ok=True)
    base, names, (train, val) = inputs(args.repo)
    role, assignment = split_groups(train['groups'], cfg)
    masks = {k: role == k for k in ['fit', 'stop', 'map']}
    if args.smoke:
        rng = np.random.default_rng(42)
        for key, mask in masks.items():
            idx = rng.choice(np.flatnonzero(mask), min(900, mask.sum()), replace=False)
            masks[key] = np.isin(np.arange(len(role)), idx)
        idx = rng.choice(len(val['y']), 600, replace=False)
        for k in ['x', 'y', 'groups', 'p']: val[k] = val[k][idx]
        for k in val['truth']: val['truth'][k] = val['truth'][k][idx]
        for k in val['oracle']: val['oracle'][k] = val['oracle'][k][idx]
    fit, stop, mapping = [masks[k] for k in ['fit', 'stop', 'map']]
    assert not (fit & stop).any() and not (mapping & (fit | stop)).any()
    seed = cfg['seeds'][args.seed_index]; costs = []; traces = {}; predictions = {}
    meta = dict(seed=seed, seed_index=args.seed_index, mode=args.mode, smoke=args.smoke,
                features=names, source_assignment=assignment,
                split_counts={k: int(m.sum()) for k, m in masks.items()},
                split_class_counts={k: np.bincount(class_index(train['y'][m], cfg), minlength=6).tolist()
                                    for k, m in masks.items()}, cfg=cfg,
                calibration_test_challenge_evaluated=False)
    specs = cfg['oracle'] if args.mode == 'main' else cfg['controls']
    for model_name, extras in list(specs.items()) + ([('classifier', [])] if args.mode == 'main' else []):
        classification = model_name == 'classifier'
        assert set(extras) <= {'primary_log_p_GeV', 'vertex_x_mm', 'vertex_y_mm', 'vertex_z_mm'}
        xt = np.column_stack([train['x']] + [train['oracle'][k] for k in extras]).astype('float32')
        xv = np.column_stack([val['x']] + [val['oracle'][k] for k in extras]).astype('float32')
        labels = class_index(train['y'], cfg) if classification else np.log(train['y'])
        dfit = xgb.DMatrix(xt[fit], label=labels[fit], feature_names=names + extras, nthread=4)
        dstop = xgb.DMatrix(xt[stop], label=labels[stop], feature_names=names + extras, nthread=4)
        params = {k: v for k, v in base['xgboost'].items()
                  if k not in ['n_estimators', 'early_stopping_rounds', 'n_jobs']}
        params.update(max_depth=cfg['xgboost']['max_depth'], seed=seed, nthread=4,
                      objective='multi:softprob' if classification else 'reg:squarederror')
        if classification: params.update(num_class=6, eval_metric='mlogloss')
        limit = Limit(cfg['max_classifier_wall_s' if classification else 'max_regression_wall_s'])
        history = {}; start = time.perf_counter(); startcpu = time.process_time()
        rounds = 20 if args.smoke else cfg['xgboost']['rounds']
        model = xgb.train(params, dfit, num_boost_round=rounds, evals=[(dfit, 'fit'), (dstop, 'stop')],
                          early_stopping_rounds=cfg['xgboost']['patience'], callbacks=[limit],
                          evals_result=history, verbose_eval=False)
        wall = time.perf_counter() - start; used = time.process_time() - startcpu
        ir = (0, model.best_iteration + 1)
        times = []
        for repeat in range(4):
            start = time.perf_counter(); raw = model.inplace_predict(xv, iteration_range=ir)
            if repeat: times.append(time.perf_counter() - start)
        mapped = model.inplace_predict(xt[mapping], iteration_range=ir)
        path = out / f'{model_name}.ubj'; model.save_model(path)
        predictions[model_name] = raw if classification else np.exp(raw)
        predictions[f'{model_name}_map'] = mapped if classification else np.exp(mapped)
        traces[model_name] = history
        cost = dict(model=model_name, seed=seed, features=len(names + extras),
                    best_iteration=model.best_iteration, iterations=len(next(iter(history['fit'].values()))),
                    stop_reason='time' if limit.hit else 'rounds' if model.num_boosted_rounds() == rounds else 'patience',
                    train_wall_s=wall, train_cpu_s=used, inference_wall_s=float(np.median(times)),
                    inference_events_per_s=len(val['y']) / float(np.median(times)), model_bytes=path.stat().st_size)
        costs.append(cost); print(json.dumps(cost), flush=True)
    if args.mode == 'main':
        start = time.perf_counter()
        bfit = class_index(train['y'][fit], cfg); bm = class_index(train['y'][mapping], cfg)
        prior = np.bincount(bfit, minlength=6) / len(bfit)
        qm = predictions['classifier_map']; qv = predictions['classifier']
        state = calibrate(qm, bm, prior)
        predictions['q_full'] = calibrated(qv, state)
        # Cross-calibrated map predictions: even temperature/intercepts never see their labels.
        mg = train['groups'][mapping]; unique = np.unique(mg)
        half = np.isin(mg, unique[::2]); qcf = np.empty_like(qm)
        cross_states = []
        for mask in [half, ~half]:
            st = calibrate(qm[~mask], bm[~mask], prior)
            qcf[mask] = calibrated(qm[mask], st); cross_states.append(st)
        centers = np.log(np.sqrt(np.array(cfg['energy_edges_GeV'][:-1]) * cfg['energy_edges_GeV'][1:]))
        meanmap = qcf @ centers; meanval = predictions['q_full'] @ centers
        predictions['q_mean'], it = scalar_mapping(meanmap, bm, meanval, prior)
        predictions['mean_log_energy'] = meanval
        predictions['q_scalar'], its = scalar_mapping(np.log(predictions['A0_map']), bm,
                                                       np.log(predictions['A0']), prior)
        edges = [200, 200*np.sqrt(2), 400, 400*np.sqrt(2), 800, 800*np.sqrt(2), 1600, 1600*np.sqrt(2), 3200]
        predictions['q_ten'], empty = ten_bin_mapping(np.log(predictions['A0_map']), bm,
                                                     np.log(predictions['A0']), prior, edges)
        predictions.update(prior=prior, map_labels=bm, map_groups=mg, map_p=train['p'][mapping])
        meta.update(calibration=state, cross_calibration=cross_states,
                    mapping_iterations=dict(mean=it, scalar=its), ten_empty_evaluation_events=empty,
                    mapping_wall_s=time.perf_counter()-start)
    predictions.update(run=val['truth']['run'], eventID=val['truth']['eventID'],
                       truth_E_GeV=val['y'], group=val['groups'])
    np.savez_compressed(out / 'predictions.npz', **predictions)
    write_table(out / 'costs.tsv', costs)
    (out / 'learning_traces.json').write_text(json.dumps(traces) + '\n')
    meta.update(wall_s=time.perf_counter()-tick, cpu_s=time.process_time()-cpu,
                peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    (out / 'summary.json').write_text(json.dumps(meta, indent=2) + '\n')
    print(json.dumps({k: meta[k] for k in ['wall_s', 'cpu_s', 'peak_rss_MiB', 'split_counts']}), flush=True)


if __name__ == '__main__':
    main()
