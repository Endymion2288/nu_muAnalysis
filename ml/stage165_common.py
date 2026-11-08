"""Frozen source labels and table I/O for a zero-fit transport diagnostic."""
import csv
import json
from pathlib import Path

import numpy as np
from stage119_curve_common import masks

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'workbook/stage165_energy_ml'
CACHE = ROOT / 'ntuples/energy_ml_stage165'


def load(path):
    with np.load(ROOT / path, allow_pickle=False) as source:
        return {k: source[k] for k in source.files if k != 'metadata_json'}


def protocol():
    return json.loads((OUT / 'protocol.json').read_text())


def table(name, rows):
    names = list(dict.fromkeys(k for row in rows for k in row))
    with (OUT / name).open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=names, delimiter='\t', lineterminator='\n')
        writer.writeheader()
        writer.writerows({k: 'NA' if v is None else v for k, v in row.items()} for row in rows)


def inputs():
    assert (OUT / 'protocol.json').read_bytes() == (ROOT / 'workbook/stage164_energy_ml/next_execution_contract.json').read_bytes()
    d = load('ntuples/energy_ml_stage131/matched_input.npz')
    assert len(d['role']) == 3002
    assert [int((d['role'] == r).sum()) for r in [1, 2, 3]] == [1708, 653, 641]
    assert np.all(d['pz'] > 50) and np.all(d['weight'] > 0) and np.isfinite(d['weight']).all()
    assert len(np.unique(d['incoming'].astype('float32'), axis=0)) == 3002
    manifest = json.loads((ROOT / 'workbook/stage130_energy_ml/source_protocol.json').read_text())['sources']
    sources = {r['index']: r for r in manifest}
    assert len(sources) == len(manifest)
    assert all(int(i) == i and int(i) in sources for i in d['source'])
    records = [sources[int(i)] for i in d['source']]
    assert all(type(r['nominal']) is bool for r in records)
    np.testing.assert_array_equal(d['component'], [r['component'] for r in records])
    nominal = np.array([r['nominal'] for r in records], dtype=bool)
    group = dict(inclusive=np.ones(3002, dtype=bool))
    group.update({f'component:{c}': d['component'] == c for c in protocol()['groups']['component']})
    group.update({'flux_context:nominal': nominal, 'flux_context:alternative': ~nominal})
    np.testing.assert_array_equal(sum(group['component:' + c].astype(int) for c in ['pi', 'k', 'charm']), np.ones(3002))
    pred = load('ml/artifacts/stage164/energy_predictions.npz')
    for name in ['AZH', 'AZ', 'H', 'A']:
        assert pred[name].shape == (3002,) and np.isfinite(pred[name]).all()
    return d, pred, group
