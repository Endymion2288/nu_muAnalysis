"""Three frozen policies, nine CPU fits, original calibration and sealed reserve."""
import json
import multiprocessing as mp
import resource
import time
from pathlib import Path

import numpy as np
import xgboost as xgb

from audited_features import configuration
from stage130_prepare import load

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'workbook/stage130_energy_ml'
ART = ROOT / 'ml/artifacts/stage130'
G = None


def one(spec):
    name, old_rows, new_rows, seed = spec
    old, new, protocol, old_use, new_use = G
    tick, cpu = time.perf_counter(), time.process_time()
    x = np.concatenate([old['x'][old_rows], new['x'][new_rows]])
    y = np.log(np.concatenate([old['truth_E_GeV'][old_rows], new['truth_E_GeV'][new_rows]]))
    incoming = np.concatenate([old['incoming'][old_rows], new['incoming'][new_rows]]).astype('float32')
    _, gid, counts = np.unique(incoming, axis=0, return_inverse=True, return_counts=True)
    w = 1 / counts[gid]
    names = configuration()['features']
    matrix = xgb.DMatrix(x, label=y, weight=w, feature_names=names, nthread=1)
    params = dict(protocol['xgboost'], seed=seed, base_score=float(np.average(y, weights=w)),
                  boost_from_average=0)
    model = xgb.train(params, matrix, num_boost_round=protocol['rounds'])
    model.save_model(ART / f'{name}_{seed}.ubj')
    a = model.predict(xgb.DMatrix(old['x'][old_use], feature_names=names, nthread=1)).astype(float)
    b = model.predict(xgb.DMatrix(new['x'][new_use], feature_names=names, nthread=1)).astype(float)
    check = xgb.Booster(params={'nthread': 1})
    check.load_model(ART / f'{name}_{seed}.ubj')
    np.testing.assert_array_equal(a, check.predict(xgb.DMatrix(old['x'][old_use], feature_names=names, nthread=1)))
    report = dict(name=name, seed=seed, old_train_N=len(old_rows), new_train_N=len(new_rows),
                  incoming_N=len(counts), weight_sum=float(w.sum()), CPU_s=time.process_time()-cpu,
                  wall_s=time.perf_counter()-tick, RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  reload_exact=True, params=params)
    return report, a, b


def main():
    global G
    tick = time.perf_counter()
    ART.mkdir(parents=True, exist_ok=True)
    assert not (OUT / 'fits.json').exists(), 'Do not repeat the frozen fit budget'
    old = load('ntuples/energy_ml_stage119/old_input.npz')
    new = load('ntuples/energy_ml_stage130/new_input.npz')
    members = load('ntuples/energy_ml_stage130/curve_membership.npz')
    protocol = json.loads((OUT / 'curve_protocol.json').read_text())['baseline']
    old_use = np.flatnonzero(old['role'] > 0)
    new_use = np.flatnonzero((new['role'] > 0) & (new['role'] < 4))
    tasks = [(name, members['old_' + name], members['new_' + name]) for name in ['N0', 'N2']]
    tasks.append(('augmented', np.flatnonzero(old['role'] == 1), np.flatnonzero(new['role'] == 1)))
    for _, a, b in tasks:
        assert np.all(old['role'][a] == 1) and np.all(new['role'][b] == 1)
    (OUT / 'fit_task_lock.json').write_text(json.dumps(dict(tasks=[dict(name=n, old_N=len(a), new_N=len(b))
        for n, a, b in tasks], seeds=protocol['seeds'], rounds=protocol['rounds'],
        new_reserve_predictions=0, quarantine_predictions=0, calibration='original cal only, one mean log offset'), indent=2)+'\n')
    # Verify the old baseline bit-for-bit and only then forward the same model
    # on unsealed new development rows. No new risk has selected this design.
    names = configuration()['features']
    original, fresh = [], []
    for seed in protocol['seeds']:
        model = xgb.Booster(params={'nthread': 1})
        model.load_model(ROOT / f'ml/artifacts/stage87/direct_{seed}.ubj')
        assert model.feature_names == names
        original.append(model.predict(xgb.DMatrix(old['x'][old_use], feature_names=names, nthread=1)).astype(float))
        fresh.append(model.predict(xgb.DMatrix(new['x'][new_use], feature_names=names, nthread=1)).astype(float))
    cached = load('ml/artifacts/stage87/predictions.npz')
    np.testing.assert_array_equal(cached['row'], old_use)
    np.testing.assert_array_equal(np.mean(original, axis=0), cached['direct_raw'])
    offsets = cached['direct_cal'] - cached['direct_raw']
    assert np.ptp(offsets) < 1e-12
    reference = np.full(len(new['role']), np.nan)
    reference[new_use] = np.mean(fresh, axis=0) + float(offsets[0])
    np.savez_compressed(ART / 'reference_new.npz', cal=reference)
    G = old, new, protocol, old_use, new_use
    specs = [(name, a, b, seed) for name, a, b in tasks for seed in protocol['seeds']]
    with mp.get_context('fork').Pool(8) as pool:
        results = pool.map(one, specs)
    reports, ensemble = [r[0] for r in results], []
    for name, _, _ in tasks:
        subset = [r for r in results if r[0]['name'] == name]
        a, b = [np.mean([r[k] for r in subset], axis=0) for k in [1, 2]]
        cal = old['role'][old_use] == 2
        offset = float(np.average(np.log(old['truth_E_GeV'][old_use][cal])-a[cal],
                                  weights=old['weight'][old_use][cal]))
        for side, data, use, pred in [('old', old, old_use, a), ('new', new, new_use, b)]:
            raw = np.full(len(data['role']), np.nan)
            raw[use] = pred
            suffix = '_new' if side == 'new' else ''
            np.savez_compressed(ART / f'quantity_{name}{suffix}_prediction.npz', raw=raw, cal=raw+offset)
            sealed = data['role'] == (4 if side == 'new' else 0)
            assert np.isnan(raw[sealed]).all()
        ensemble.append(dict(name=name, offset_log=offset))
    (OUT / 'fits.json').write_text(json.dumps(dict(results=reports, ensembles=ensemble,
        wall_s=time.perf_counter()-tick, old_reference_max_abs_log_difference=0,
        new_reserved_forward_N=0, old_quarantine_forward_N=0, GPU=0), indent=2)+'\n')
    print(ensemble, flush=True)


if __name__ == '__main__':
    main()
