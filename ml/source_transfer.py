"""Shared stage48 paths and unchanged-input source-external event join."""
import json
from pathlib import Path
import numpy as np

REPO=Path(__file__).resolve().parents[1]
CACHE=REPO/'ntuples/energy_ml_stage48'
OUT=REPO/'workbook/stage48_energy_ml'


def configuration():return json.loads((REPO/'ml/configs/source_transfer.json').read_text())


def load_inputs():
    with np.load(CACHE/'selection.npz') as z:rows=z['cache_row']
    with np.load(REPO/'ntuples/energy_ml_stage42/development.npz') as z:d={k:z[k][rows] for k in z.files}
    with np.load(CACHE/'features.npz') as z:
        np.testing.assert_array_equal(rows,z['cache_row'])
        for k in ['run','eventID']:np.testing.assert_array_equal(z[k],d[k])
        x=np.column_stack([d['x'],z['local']]).astype('float32')
    assert x.shape==(4000,87);x[~np.isfinite(x)]=np.nan
    return rows,d,x
