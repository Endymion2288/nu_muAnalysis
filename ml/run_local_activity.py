#!/usr/bin/env python3
"""Frozen stage44 reco-only local activity ablation."""
import argparse
import json
import resource
import time
from pathlib import Path
import numpy as np
import xgboost as xgb
from information_gap import scalar_mapping
from run_calonu_information import WallLimit


def main():
    p = argparse.ArgumentParser(); p.add_argument('--fold', type=int, choices=range(3), required=True)
    p.add_argument('--smoke', action='store_true'); a = p.parse_args()
    tick, cpu = time.perf_counter(), time.process_time(); repo = Path(__file__).resolve().parents[1]
    cfg = json.loads((repo/'ml/configs/local_activity.json').read_text())
    with np.load(repo/'ntuples/energy_ml_stage42/development.npz') as z: d = {k: z[k] for k in z.files}
    chosen = np.flatnonzero(d['selected']); x = d['x'][chosen]; y = np.log(d['truth_E_GeV'][chosen]); fold = d['fold'][chosen]
    if a.smoke:
        with np.load(repo/'ntuples/energy_ml_stage44/pilot.npz') as z:
            pilot = z['local']
            for key in ['run','eventID']: np.testing.assert_array_equal(z[key], d[key][chosen[:len(pilot)]])
        x, y, fold = x[:len(pilot)], y[:len(pilot)], fold[:len(pilot)]
        candidates = {'local': np.column_stack([x, pilot]).astype('float32')}
    else:
        with np.load(repo/'ntuples/energy_ml_stage44/features.npz') as z:
            np.testing.assert_array_equal(z['cache_row'], chosen); np.testing.assert_array_equal(z['eventID'], d['eventID'][chosen])
            np.testing.assert_array_equal(z['run'], d['run'][chosen])
            assert json.loads(str(z['metadata_json']))['config'] == cfg
            candidates = {k: np.column_stack([x, z[k]]).astype('float32') for k in cfg['candidates']}
    tr = np.flatnonzero(fold == (a.fold+1)%3); ca = np.flatnonzero(fold == (a.fold+2)%3); ev = np.flatnonzero(fold == a.fold)
    if a.smoke:
        tr, ca, ev = np.arange(4), np.arange(4,6), np.arange(6,8)
    for l, r in [(tr, ca), (tr, ev), (ca, ev)]: assert a.smoke or not set(d['group'][chosen[l]]) & set(d['group'][chosen[r]])
    labels = np.searchsorted(cfg['energy_edges_GeV'], np.exp(y), side='right')-1
    assert ((labels >= 0) & (labels < 6)).all()
    prior = np.bincount(labels[ca], minlength=6)/len(ca)
    out = repo/'ml/artifacts/stage44'/('smoke' if a.smoke else 'formal')/str(a.fold); out.mkdir(parents=True, exist_ok=True)
    saved = {'cache_row': chosen[ev], 'prior': prior}; records = []
    for name, values in candidates.items():
        start, cp = time.perf_counter(), time.process_time(); values[~np.isfinite(values)] = np.nan
        dt = xgb.DMatrix(values[tr], label=y[tr]); dc = xgb.DMatrix(values[ca]); de = xgb.DMatrix(values[ev])
        model = xgb.train(dict(cfg['xgboost'], seed=cfg['seed']+a.fold), dt,
                          num_boost_round=20 if a.smoke else cfg['rounds'], callbacks=[WallLimit(cfg['fit_wall_limit_s'])])
        cal, pred = model.predict(dc), model.predict(de); offset = float(np.mean(y[ca]-cal))
        saved[name] = np.exp(pred.astype(float)+offset)
        ms = time.perf_counter(); iterations = None
        if (prior > 0).all():
            saved['q_'+name], iterations = scalar_mapping(cal.astype(float)+offset, labels[ca], pred.astype(float)+offset, prior)
        mapping_wall = time.perf_counter()-ms
        model.save_model(out/(name+'.ubj'))
        records.append(dict(model=name, fold=a.fold, train_N=len(tr), calibration_N=len(ca), evaluation_N=len(ev), columns=values.shape[1],
                            rounds=model.num_boosted_rounds(), log_offset=offset, mapping_iterations=iterations,
                            mapping_wall_s=mapping_wall, wall_s=time.perf_counter()-start, cpu_s=time.process_time()-cp))
        print(json.dumps(records[-1]), flush=True)
    metadata = dict(stage=44, fold=a.fold, smoke=a.smoke, records=records, config=cfg, wall_s=time.perf_counter()-tick,
                    cpu_s=time.process_time()-cpu, peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                    xgboost_version=xgb.__version__, numpy_version=np.__version__)
    np.savez_compressed(out/'predictions.npz', **saved, metadata_json=np.array(json.dumps(metadata)))
    print(json.dumps({k: v for k, v in metadata.items() if k not in ['config', 'records']}), flush=True)


if __name__ == '__main__': main()
