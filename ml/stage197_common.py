"""Original data cuts and descriptive observables; no model or event truth."""
import csv
import gzip
import json
import math
from pathlib import Path

import awkward as ak
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'workbook/stage197_energy_ml'
CACHE = ROOT / 'ntuples/energy_ml_stage197'
P = json.loads((OUT / 'protocol.json').read_text())
G = json.loads((ROOT / P['GRL']).read_text())
SCINT = ['VetoNu0','VetoNu1','Veto10','Veto20','Veto21'] + [f'Timing{k}' for k in range(4)] + ['Preshower0','Preshower1']
TRACK = ['pz0','px0','py0','Y_atTrig','nLayers','nDoF','Chi2','r_atMaxRadius','X_atVetoStation2','Y_atVetoStation2','X_atVetoNu','Y_atVetoNu']
CUTS = ['input','colliding','trigger','GoodTimes','notExcluded','longTracks','CaloNuStatus','Veto2','TimingCharge','Preshower','pz0_gt50','layers','nDoF','chi2','rMax','rIFT','rVetoNu','theta']


def write(name, obj):
    (OUT / name).write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')


def table(name, rows):
    if not rows:
        return
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with (OUT / name).open('w') as f:
        w = csv.DictWriter(f, fieldnames=keys, delimiter='\t', lineterminator='\n', quoting=csv.QUOTE_NONNUMERIC)
        w.writeheader(); w.writerows(rows)


def save_gz(path, value):
    with gzip.open(path, 'wt', compresslevel=1) as f:
        json.dump(value, f, separators=(',', ':'), allow_nan=False)


def read_gz(path):
    with gzip.open(path, 'rt') as f:
        return json.load(f)


def finite(value):
    return float(value) if math.isfinite(float(value)) else None


def schema(tree):
    names = set(tree.keys())
    required = ['run','eventID','eventTime','distanceToCollidingBCID','inputBits','longTracks','nClusters0']
    required += ['Track_' + name for name in TRACK]
    required += [d + '_' + suffix for d in SCINT for suffix in ['charge','raw_charge','status']]
    mapping = {}
    for name in required:
        choices = [name]
        if name.startswith('Veto') and not name.startswith('VetoNu'):
            choices.append(name.replace('Veto', 'VetoSt', 1))
        matches = [k for k in choices if k in names]
        if not matches:
            return dict(supported=False, missing=name, available=sorted(names)), {}
        mapping[name] = matches[0]
    native = all(f'VetoNu{k}_reduced_charge' in names for k in range(2))
    if native:
        for k in range(2):
            name = f'VetoNu{k}_reduced_charge'; mapping[name] = name
    return dict(supported=True, mapping=mapping, native_reduced=native), mapping


def leading(arrays):
    index = ak.argmax(arrays['Track_pz0'], axis=1, keepdims=True, mask_identity=True)
    result = {}
    for name in TRACK:
        # SafeAt semantics: if a particular vector is shorter, its field is unknown.
        lengths = ak.num(arrays['Track_' + name])
        valid = ak.fill_none(ak.firsts(index), -1) < lengths
        index_safe = ak.mask(index, valid)
        result[name] = ak.to_numpy(ak.fill_none(ak.firsts(arrays['Track_' + name][index_safe]), np.nan))
    return result


def cut_masks(arrays, lead):
    n = len(arrays['run'])
    scalar = lambda key: ak.to_numpy(arrays[key])
    stable = np.zeros(n, bool); excluded = stable.copy()
    times = scalar('eventTime')
    for lo, hi in G['stable_ranges_s']:
        stable |= (times >= lo) & (times <= hi)
    for lo, hi in G['excluded_ranges_s']:
        excluded |= (times >= lo) & (times <= hi)
    a, b = scalar('VetoNu0_status'), scalar('VetoNu1_status')
    good_nu = (np.isin(a,[0,1]) & np.isin(b,[0,1])) | ((a == 0) & (b == 16))
    clean = good_nu & (scalar('Veto20_status') != 528) & (scalar('Veto21_status') != 528)
    bottom = scalar('Timing0_charge') + scalar('Timing1_charge')
    top = scalar('Timing2_charge') + scalar('Timing3_charge')
    y = lead['Y_atTrig']
    timing = ((y > 20) & (top > 20)) | ((y < -20) & (bottom > 20)) | ((abs(y) < 20) & (top + bottom > 20))
    with np.errstate(divide='ignore', invalid='ignore'):
        theta = np.arctan(np.sqrt(lead['px0']**2 + lead['py0']**2) / lead['pz0']) * 1000
        chi2 = lead['Chi2'] / lead['nDoF']
    masks = [np.ones(n,bool), scalar('distanceToCollidingBCID') == 0, (scalar('inputBits') & 0x78) != 0,
             stable, ~excluded, scalar('longTracks') > 0, clean,
             (scalar('Veto20_charge') > 40) & (scalar('Veto21_charge') > 40), timing,
             (scalar('Preshower0_charge') > 2.5) & (scalar('Preshower1_charge') > 2.5),
             lead['pz0'] / 1000 > 50, lead['nLayers'] >= 7, lead['nDoF'] >= 9, chi2 < 15,
             lead['r_atMaxRadius'] < 95, np.hypot(lead['X_atVetoStation2'], lead['Y_atVetoStation2']) < 95,
             np.hypot(lead['X_atVetoNu'], lead['Y_atVetoNu']) < 120, theta < 25]
    cumulative = np.ones(n,bool); counts = []
    for m in masks:
        cumulative &= m; counts.append(int(cumulative.sum()))
    return cumulative, counts


def records(arrays, lead, indices, file_index, entry_start):
    result = []
    for i in indices:
        raw, status = [], []
        for d in SCINT:
            q = finite(arrays[d + '_raw_charge'][i]); s = int(arrays[d + '_status'][i])
            raw.append(q if not (s & 392) else None); status.append(s)
        reduced = [finite(arrays[f'VetoNu{k}_reduced_charge'][i]) for k in range(2)] if 'VetoNu0_reduced_charge' in arrays else None
        c = finite(arrays['nClusters0'][i])
        if c is not None and (c < 0 or c != int(c) or c >= 4294967295):
            c = None
        result.append(dict(file=file_index, entry=int(entry_start+i), run=int(arrays['run'][i]), eventID=int(arrays['eventID'][i]),
            pz0_GeV=float(lead['pz0'][i]/1000), nClusters0=c, raw_charge_pC=raw, original_status=status,
            original_raw_VetoNu=[finite(arrays[f'VetoNu{k}_raw_charge'][i]) for k in range(2)],
            native_reduced_pC=reduced,
            selection_TimingOK=any((int(arrays[d+'_status'][i]) & ~512) == 0 for d in ['Veto20','Veto21','Preshower0','Preshower1'])))
    return result


def final_selection(row, aux):
    if row['native_reduced_pC'] is not None:
        q = row['native_reduced_pC']
        if any(v is None for v in q):
            return 'native_nonfinite', None
        # Native original selection has no aux fallback. Do not reinterpret old cuts.
        return ('selected' if all(v < 30 for v in q) else 'vetoed'), q
    key = (row['run'], row['eventID'])
    if key not in aux:
        return 'aux_missing', None
    if aux[key] is None:
        return 'aux_ambiguous', None
    reduced = []
    for k, value in enumerate(aux[key]):
        raw = row['original_raw_VetoNu'][k]
        invalid = value is None or not row['selection_TimingOK'] or (value == 0 and raw is not None and raw > 30)
        if invalid:
            reduced.append(-1.)
            if raw is None:
                return 'fallback_nonfinite', reduced
            if not raw < 40:
                return 'vetoed', reduced
        else:
            reduced.append(max(value,0.))
            if not reduced[-1] < 30:
                return 'vetoed', reduced
    return 'selected', reduced


def cell(row):
    values = [row['pz0_GeV'], row['raw_charge_pC'][2], row['nClusters0']]
    edges = [P['pz_edges_GeV'], P['raw_Veto10_edges_pC'], P['nClusters0_edges']]
    return tuple(-1 if v is None else int(np.searchsorted(e, v, side='right')) for v,e in zip(values,edges))
