"""Frozen stage87 direct62 inference outside the training truth-radius selection."""
import argparse
import contextlib
import json
import multiprocessing as mp
import resource
import tempfile
import time
from pathlib import Path

import numpy as np
import xgboost as xgb

from audited_features import REPO, configuration, load
from extract_alternative_support import extract

OUT = REPO/'workbook/stage126_energy_ml'
CACHE = REPO/'ntuples/energy_ml_stage126'
MODELS = None
OLD = None


def initialize():
    global MODELS, OLD
    p = json.loads((OUT/'protocol.json').read_text())
    MODELS = []
    for seed in p['seeds']:
        model = xgb.Booster(params={'nthread': 1})
        model.load_model(REPO/f'ml/artifacts/stage87/direct_{seed}.ubj')
        MODELS.append(model)
    d, s, x = load()
    OLD = (d, s, x)


def work(source):
    tick = time.perf_counter()
    index = source['index']
    with tempfile.TemporaryDirectory(prefix='radius126_') as dirname:
        tmp = Path(dirname)
        with (tmp/'extract.log').open('w') as log, contextlib.redirect_stdout(log):
            extract(index, Path(source['input']), tmp/'features.npz', source=source,
                    cuts_config=OUT/'scan_cuts.yaml', threads=1)
        with np.load(tmp/'features.npz') as z:
            d = {k: z[k] for k in z.files if k != 'metadata_json'}
            md = json.loads(str(z['metadata_json']))
        r = np.hypot(d['vertex_x_mm'], d['vertex_y_mm'])
        old, supplement, expected = OLD
        take = np.flatnonzero(old['source'] == index)
        lookup = {int(e): j for j, e in enumerate(d['eventID'])}
        order = np.array([lookup[int(e)] for e in old['eventID'][take]], int)
        assert set(d['eventID'][r < 100]) == set(old['eventID'][take])
        np.testing.assert_array_equal(d['truth_E_GeV'][order], old['truth_E_GeV'][take])
        sr = np.flatnonzero(old['source'][supplement['row']] == index)
        er = np.array([lookup[int(e)] for e in old['eventID'][supplement['row'][sr]]], int)
        np.testing.assert_array_equal(d['x'][er], expected[sr])
        target = xgb.DMatrix(d['x'], feature_names=configuration()['features'], nthread=1)
        raw = np.mean([m.predict(target).astype(float) for m in MODELS], axis=0)
        p = json.loads((OUT/'protocol.json').read_text())
        keep = ['run', 'eventID', 'input_entry', 'truth_E_GeV', 'reco_pz_GeV',
                'incoming', 'vertex_z_mm', 'y_lepton', 'confirmed', 'primary_valid']
        result = {k: d[k] for k in keep}
        result.update(radius_mm=r, direct_raw=raw, direct_cal=raw+p['offset'],
                      source=np.full(len(r), index, np.int32))
        md.update(source=source, baseline_identity_exact=True, baseline62_exact_N=len(sr),
                  wall_total_s=time.perf_counter()-tick, new_fits=0)
        dest = CACHE/f'source_{index}.npz'
        np.savez_compressed(dest, **result, metadata_json=np.array(json.dumps(md)))
        return dict(index=index, N=len(r), N100=int((r<100).sum()),
                    baseline62_exact_N=len(sr), wall_s=md['wall_total_s'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch', type=int)
    parser.add_argument('--pilot', type=int)
    parser.add_argument('--workers', type=int, default=4)
    a = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    p = json.loads((OUT/'protocol.json').read_text())
    sources = ([s for s in p['sources'] if s['index'] == a.pilot] if a.pilot is not None
               else p['sources'][a.batch::p['batches']])
    start = time.perf_counter()
    if a.pilot is not None:
        initialize()
        results = [work(s) for s in sources]
    else:
        with mp.get_context('spawn').Pool(a.workers, initializer=initialize) as pool:
            results = pool.map(work, sources)
    report = dict(results=results, wall_s=time.perf_counter()-start, workers=a.workers,
                  self_CPU_s=time.process_time(), peak_parent_RSS_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    label = f'pilot_{a.pilot}' if a.pilot is not None else f'batch_{a.batch}'
    (OUT/f'{label}.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
