"""Frozen Stage100 input reconstruction and paired conditional statistics."""
import csv
import json
import resource
import time
from pathlib import Path

import numpy as np

from audited_features import build, clean, configuration

REPO = Path(__file__).resolve().parents[1]
OUT = REPO/'workbook/stage100_energy_ml'
CACHE = REPO/'ntuples/energy_ml_stage100'
ART = REPO/'ml/artifacts/stage100'
OLD = REPO/'ntuples/energy_ml_stage99'
SEED = 2026110499
ACTIVITY = [f's{s}_entries' for s in range(4)] + [
    f's{s}l{l}_{q}' for s in [1, 2, 3] for l in range(3)
    for q in ['entries', 'outside10', 'outside50', 'rms_radius_mm']
] + ['outside10_growth_s3_minus_s1', 'first_outside10_plane']


def load(path):
    with np.load(REPO/path) as z:
        return {k: z[k] for k in z.files}


def read(path):
    with Path(path).open() as stream:
        return list(csv.DictReader(stream, delimiter='\t'))


def save(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n')


def table(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(dict.fromkeys(k for r in rows for k in r)),
                                delimiter='\t', lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def cost(tick, cpu):
    return dict(wall_s=time.perf_counter()-tick, CPU_s=time.process_time()-cpu,
                peak_RSS_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)


def inputs(qa=False):
    cohort = json.loads((REPO/'ntuples/energy_ml_stage95/cohort.json').read_text())
    cases = [c for c in cohort['records'] if c['qa']][:40] if qa else cohort['records']
    assert len({c['key_id'] for c in cases}) == len(cases)
    split = load('ntuples/energy_ml_stage87/split.npz')
    rows = np.array([c['row'] for c in cases])
    for field in ['key_id', 'role', 'origin', 'origin_row', 'run', 'eventID', 'group', 'component']:
        np.testing.assert_array_equal(split[field][rows], [c[field] for c in cases])
    assert np.isin(split['role'][rows], [1, 2]).all()
    old = load('ntuples/energy_ml_stage55/dataset.npz')
    readout = load('ntuples/energy_ml_stage56/readout.npz')
    baseline = np.full((len(cases), 62), np.nan)
    for origin in sorted({c['origin'] for c in cases}):
        ids = np.array([i for i, c in enumerate(cases) if c['origin'] == origin])
        origin_rows = np.array([cases[i]['origin_row'] for i in ids])
        if origin == 55:
            idx = np.searchsorted(readout['row'], origin_rows)
            np.testing.assert_array_equal(readout['row'][idx], origin_rows)
            small = {k: v[idx] for k, v in readout.items() if k != 'metadata_json'}
            baseline[ids] = build(old, small)
        else:
            baseline[ids] = load(f'ntuples/energy_ml_stage{origin}/support.npz')['x'][origin_rows]
    cfg = configuration()
    assert len(cfg['features']) == 62
    for j, name in enumerate(cfg['features']):
        np.testing.assert_array_equal(baseline[:, j], clean(baseline[:, j], cfg['rules'][name]))
    assert not any(n in cfg['features'] for n in
                   ['ML_mu_p_GeV', 'ML_track_p1_GeV', 'ML_track_pz1_GeV', 'ML_track_log_p1_over_p0'])
    metadata = {int(c['row']): c for c in read(OLD/'B_identities.tsv')}
    feature = {int(c['row']): c for c in read(OLD/'B_collection_features.tsv')}
    available = np.array([int(metadata[c['row']]['available']) for c in cases])
    flags = np.array([c['status_other'] for c in cases])
    A = np.column_stack([baseline, np.isnan(baseline), flags, available, np.zeros(len(cases))])
    activity = np.array([[float(feature[c['row']][k]) for k in ACTIVITY] for c in cases])
    B = np.column_stack([A, activity, np.isnan(activity)])
    assert A.shape == (len(cases), 127) and B.shape == (len(cases), 211)
    assert not np.isinf(A).any() and not np.isinf(B).any()
    np.testing.assert_array_equal(A[:, 0], np.array([c['pz_GeV'] for c in cases], dtype=np.float32))
    return cases, A, B, available


def task(cases):
    energy = np.array([c['reference_truth_E_GeV'] for c in cases])
    pz = np.array([c['pz_GeV'] for c in cases])
    role = np.array([c['role'] for c in cases])
    labels = (energy >= 200).astype(int)
    domain = (pz > 50) & (pz < 100) & (((energy >= 50) & (energy < 100)) | (energy >= 200))
    train = domain & (role == 1)
    cal = domain & (role == 2)
    support = []
    for code, mask in [(1, train), (2, cal)]:
        for label in [0, 1]:
            selected = mask & (labels == label)
            support.append(dict(role=code, label=label, N=int(selected.sum()),
                                sources=len({c['source'] for c, z in zip(cases, selected) if z}),
                                incoming=len({c['key_id'] for c, z in zip(cases, selected) if z})))
    assert [r['N'] for r in support] == [65, 82, 20, 46]
    return labels, train, cal, support


def bootstrap(cases):
    key = np.array([c['key_id'] for c in cases])
    _, first, gid = np.unique(key, return_index=True, return_inverse=True)
    component = np.array([c['component'] for c in cases])[first]
    rng = np.random.default_rng(SEED)
    draws = np.zeros((500, len(first)), np.int16)
    for comp in sorted(set(component)):
        idx = np.flatnonzero(component == comp)
        draws[:, idx] = rng.multinomial(len(idx), np.full(len(idx), 1/len(idx)), size=500)
    return draws[:, gid]


def interval(values):
    a = np.asarray(values)
    a = a[np.isfinite(a)]
    return [float(x) for x in np.quantile(a, [.025, .975])]


def roc(scores, labels, weights):
    weights = np.asarray(weights, dtype=float)
    ix = np.argsort(-scores, kind='stable')
    s, y, w = scores[ix], labels[ix], weights[ix]
    ends = np.r_[np.flatnonzero(np.diff(s) != 0), len(s)-1]
    fp = np.r_[0, np.cumsum(w*(y == 0))[ends]]
    tp = np.r_[0, np.cumsum(w*(y == 1))[ends]]
    fp /= fp[-1]
    tp /= tp[-1]
    auc = float(np.trapezoid(tp, fp))
    x = np.r_[fp[fp < .1], .1]
    y = np.r_[tp[fp < .1], np.interp(.1, fp, tp)]
    return fp, tp, auc, float(np.trapezoid(y, x)/.1)


def threshold(train_scores, train_labels, alpha):
    low = train_scores[train_labels == 0]
    values = np.unique(low)
    rate = np.array([np.mean(low > t) for t in values])
    return float(values[np.flatnonzero(rate <= alpha+1e-14)[0]])
