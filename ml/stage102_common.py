"""Frozen Stage102 paths and shared input reconstruction; no fitting on import."""
import json
import os
from pathlib import Path

import numpy as np

from support_augmentation import arrays, begin, resources, save, table

REPO = Path(__file__).resolve().parents[1]
OUT = REPO/'workbook/stage102_energy_ml'
ART = REPO/'ml/artifacts/stage102'
CACHE = REPO/'ntuples/energy_ml_stage102'
SEED = 2026110494
OLD_B = .02017839294662559
GATES = ['E50_100', 'E100_200', 'all', 'E200_inf', 'pz50_100',
         'pz50_100_trueE200', 'high_y', 'unconfirmed']


def atomic_json(path, value):
    temporary = path.with_suffix('.tmp')
    save(temporary, value)
    assert json.loads(temporary.read_text()) == value
    os.replace(temporary, path)


def frozen_inputs(rows):
    from compare_energy_architectures import representation
    from retrain_accurate_posterior import reconstruct
    from audited_features import clean, configuration
    d = reconstruct(rows)
    state = json.loads((REPO/'workbook/stage94_energy_ml/preprocessing.json').read_text())['E']
    cfg = configuration()
    assert len(state['features']) == 62 and state['features'] == cfg['features']
    assert not any(n in cfg['features'] for n in ['ML_mu_p_GeV', 'ML_track_p1_GeV',
                   'ML_track_pz1_GeV', 'ML_track_log_p1_over_p0'])
    for j, name in enumerate(cfg['features']):
        np.testing.assert_array_equal(d['x'][:, j], clean(d['x'][:, j], cfg['rules'][name]))
    x, same, _ = representation(d, 'E', state=state)
    assert same == state and x.shape == (len(rows), 127)
    return d, x, state


def partition(d):
    part = arrays(REPO/'ntuples/energy_ml_stage94/cal_partition.npz')
    cal = np.flatnonzero(d['role'] == 2)
    ix = np.searchsorted(part['row'], d['row'][cal])
    np.testing.assert_array_equal(part['row'][ix], d['row'][cal])
    return cal, part['subrole'][ix], part['weight'][ix]
