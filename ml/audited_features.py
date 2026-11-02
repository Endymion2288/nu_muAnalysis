"""Versioned feature policy: pz0, raw scintillator charges and typed missingness."""
import json
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
SCINTILLATORS = ['VetoNu0', 'VetoNu1', 'Veto10', 'Veto20', 'Veto21'] + [f'Timing{i}' for i in range(4)] + ['Preshower0', 'Preshower1']
WAVE_INVALID = 8 | 128 | 256  # baseline failure, missing or invalid waveform
FIT_INVALID = WAVE_INVALID | 16 | 32 | 4  # fit failure or censored fit
REMOVED = ['ML_track_p1_GeV', 'ML_track_pz1_GeV', 'ML_track_log_p1_over_p0']


def configuration():
    return json.loads((REPO/'ml/configs/audited_features.json').read_text())


def clean(values, rule):
    """Rules apply in the declared feature units; signed values stay signed."""
    v = np.asarray(values, dtype=float).copy()
    invalid = ~np.isfinite(v)
    invalid |= np.isin(v, rule.get('sentinels', []))
    if 'allowed_values' in rule:
        invalid |= ~np.isin(v, rule['allowed_values'])
    domain = rule['domain']
    if domain == 'positive':
        invalid |= v <= 0
    elif domain in ['nonnegative', 'count']:
        invalid |= v < 0
    if domain == 'count':
        invalid |= (v != np.floor(v)) | (v >= 4294967295)
    elif domain == 'charge_sign':
        invalid |= ~np.isin(v, [-1, 1])
    elif domain == 'boolean':
        invalid |= ~np.isin(v, [0, 1])
    v[invalid] = np.nan
    return v


def matrix(values, cfg=None):
    """Same typed cleaning for training and inference, followed by float32 cast."""
    cfg = cfg or configuration()
    return np.column_stack([clean(values[n], cfg['rules'][n]) for n in cfg['features']]).astype('float32')


def build(dataset, supplement):
    """Join the frozen selected cohort; raw/status columns come from PHYS."""
    cfg = configuration()
    rows = supplement['row']
    names = json.loads(str(dataset['metadata_json']))['features']
    old = dataset['x'][rows]
    values = {n:old[:,j].astype(float) for j,n in enumerate(names)}
    values['ML_mu_pz0_GeV'] = dataset['reco_pz_GeV'][rows]
    status = supplement['status'].astype(np.int64)
    for j, detector in enumerate(SCINTILLATORS):
        q = supplement['raw_charge'][:,j].astype(float).copy()
        q[(status[:,j] & WAVE_INVALID) != 0] = np.nan
        values[detector+'_raw_charge'] = q
    for j in range(2):
        n = f'VetoNu{j}_reduced_charge'
        values[n][(status[:,j] & WAVE_INVALID) != 0] = np.nan
    # Clean primitive geometry before calculating differences and ratios.
    geometry = ['ML_mu_'+k+'_mm' for k in ['x0','y0','z0']] + ['ML_track_'+k+'_mm' for k in ['x1','y1','z1']]
    for n in geometry:
        values[n] = clean(values[n], cfg['rules'][n])
    dz = values['ML_track_z1_mm'] - values['ML_mu_z0_mm']
    dz[dz <= 0] = np.nan
    values['ML_track_span_z_mm'] = dz
    with np.errstate(divide='ignore', invalid='ignore'):
        for axis in ['x','y']:
            values['ML_track_chord_slope_'+axis] = (values['ML_track_'+axis+'1_mm'] - values['ML_mu_'+axis+'0_mm']) / dz
    # p0/p1 are only validity dependencies of permitted q/p inputs, never features.
    bad_charge = ~np.isin(values['LeadTrack_charge'], [-1, 1])
    p0 = dataset['reco_p_GeV'][rows];p1 = values['ML_track_p1_GeV']
    values['ML_track_qOverP0_GeVinv'][bad_charge | ~np.isfinite(p0) | (p0 <= 0)] = np.nan
    values['ML_track_qOverP1_GeVinv'][bad_charge | ~np.isfinite(p1) | (p1 <= 0)] = np.nan
    pz0 = values['ML_mu_pz0_GeV'];pz1 = values['ML_track_pz1_GeV']
    bad_back = ~np.isfinite(pz1) | (pz1 <= 0) | ~np.isfinite(pz0) | (pz0 <= 0)
    for axis in ['x','y']:
        values['ML_track_bend_'+axis][bad_back] = np.nan
    for j in range(4):
        n = f'ML_calo{j}_E_EM_GeV'
        values[n][(supplement['calo_status'][:,j].astype(np.int64) & FIT_INVALID) != 0] = np.nan
    # A missing module must not become a plausible smaller total via nansum.
    values['ML_calo_total_E_EM_GeV'] = np.sum([values[f'ML_calo{j}_E_EM_GeV'] for j in range(4)], axis=0)
    x = matrix(values, cfg)
    assert x.shape == (len(rows), len(cfg['features']))
    assert not any(n in cfg['features'] for n in REMOVED+['ML_mu_p_GeV'])
    return x


def load():
    with np.load(REPO/'ntuples/energy_ml_stage55/dataset.npz') as z:
        dataset = {k:z[k] for k in z.files}
    with np.load(REPO/'ntuples/energy_ml_stage56/readout.npz') as z:
        supplement = {k:z[k] for k in z.files if k != 'metadata_json'}
    return dataset, supplement, build(dataset, supplement)
