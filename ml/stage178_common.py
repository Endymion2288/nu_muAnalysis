"""Outward-rounded state boxes and conservative S0-side labels."""
import gzip
import json
from pathlib import Path
import numpy as np

ROOT = Path.cwd()
OUT = ROOT / 'workbook/stage178_energy_ml'
CACHE = ROOT / 'ntuples/energy_ml_stage178'
FIELDS = ['ML_mu_' + a + '0_mm' for a in 'xyz'] + ['ML_mu_' + a + '0_GeV' for a in ['px', 'py', 'pz']]

def read_gz(path):
    with gzip.open(path, 'rt') as stream:
        return json.load(stream)

def cell(value):
    v = np.float32(value)
    lo = (float(np.nextafter(v, np.float32(-np.inf))) + float(v)) / 2
    hi = (float(np.nextafter(v, np.float32(np.inf))) + float(v)) / 2
    return [lo, hi]

def down(v):
    return np.nextafter(v, -np.inf)

def up(v):
    return np.nextafter(v, np.inf)

def mul(a, b):
    products = np.array([a[0]*b[0], a[0]*b[1], a[1]*b[0], a[1]*b[1]])
    return np.array([down(products.min(axis=0)), up(products.max(axis=0))])

def boxes():
    names = json.loads((ROOT / 'ml/configs/audited_features.json').read_text())['features']
    p = json.loads((OUT / 'protocol.json').read_text())
    with np.load(ROOT / 'ntuples/energy_ml_stage131/matched_input.npz') as data:
        result = []
        for index in [p['reference_index']] + p['replay_indices']:
            row = np.flatnonzero(data['frame_index'] == index)
            assert len(row) <= 1
            record = dict(index=index, supported=False, reason='original parent not reselected; no cached fitted plane')
            if len(row):
                i = int(row[0]); assert int(data['role'][i]) == 1
                state = data['x'][i, [names.index(k) for k in FIELDS]].astype(float)
                if np.isfinite(state).all() and not np.any(state == -999) and state[-1] > 50:
                    b = np.array([cell(v) for v in state])
                    b[3:, 0] = down(down(b[3:, 0]) * 1000)
                    b[3:, 1] = up(up(b[3:, 1]) * 1000)
                    # Normal direction interval. Sum positive squares with outward bounds.
                    mom = b[3:].T
                    squares = mul(mom, mom)
                    squares[0, (mom[0] <= 0) & (mom[1] >= 0)] = 0
                    normlo = down(np.sqrt(down(down(squares[0,0] + squares[0,1]) + squares[0,2])))
                    normhi = up(np.sqrt(up(up(squares[1,0] + squares[1,1]) + squares[1,2])))
                    normal = mul(mom, np.array([down(1/normhi), up(1/normlo)])[:,None])
                    record.update(supported=True, reason=None, fields=FIELDS, cached_values=state.tolist(),
                        xyz_mm_intervals=b[:3].tolist(), momentum_MeV_intervals=b[3:].tolist(), normal_intervals=normal.T.tolist(),
                        incoming=data['incoming'][i].tolist(), sampling_stratum=str(data['sampling_stratum'][i]), weight=float(data['weight'][i]))
                else:
                    record['reason'] = 'typed state missing, placeholder or invalid pz0'
            result.append(record)
    return result

def bounds(points, box):
    """Signed unnormalized p dot (r-center), in MeV*mm, enclosing all stored-state cells."""
    points = np.asarray(points, dtype=float).reshape(-1, 3)
    center = np.asarray(box['xyz_mm_intervals'])
    momentum = np.asarray(box['momentum_MeV_intervals']).T
    diff = np.array([down(points-center[:,1]), up(points-center[:,0])])
    terms = mul(diff, momentum[:,None,:])
    lo = down(down(terms[0,:,0] + terms[0,:,1]) + terms[0,:,2])
    hi = up(up(terms[1,:,0] + terms[1,:,1]) + terms[1,:,2])
    return np.column_stack([lo, hi])

def signs(intervals):
    intervals = np.asarray(intervals)
    return np.where(intervals[:,1] < 0, -1, np.where(intervals[:,0] > 0, 1, 0))

def classify(index, raw, box):
    groups = {0:'primary_muon_direct', -1:'other_root', -2:'unknown_root'}
    counts = {}; births = []; crossings = []
    primary = raw['muon_primaries']
    valid = box['supported'] and len(primary) == 1
    if valid:
        mom = np.asarray(box['momentum_MeV_intervals']).mean(axis=1)
        valid = float(np.dot(mom, primary[0][5:8])) > 0
    for b in raw['muon_births']:
        interval = bounds([b['xyz_mm']], box)[0] if valid else None
        sign = int(signs([interval])[0]) if valid else 0
        side = {-1:'before_S0', 0:'unknown_S0', 1:'after_S0'}[sign]
        groups[b['group']] = side
        key = side + ':' + b['process'] + ':' + str(b['pdg'])
        counts[key] = counts.get(key, 0) + 1
        births.append(dict(group=b['group'], side=side, sign_interval_MeV_mm=interval.tolist() if valid else None))
    unknown_endpoints = 0
    for ordinal, segment in enumerate(raw['muon_segments']):
        if len(primary) != 1 or int(segment[0]) != int(primary[0][0]):
            continue
        intervals = bounds([segment[1:4], segment[4:7]], box) if valid else None
        side = signs(intervals) if valid else np.zeros(2, dtype=int)
        unknown_endpoints += int(np.sum(side == 0))
        if side[0] * side[1] == -1:
            crossings.append(dict(ordinal=ordinal, forward=bool(side[0] < 0), endpoint_intervals_MeV_mm=intervals.tolist(),
                pre_post_total_energy_MeV=segment[7:9], pre_post_time_ns=segment[11:13]))
    partition = {}
    for name, hits in raw['daq_hits'].items():
        tags = raw['daq_birth_groups'][name]
        assert len(hits) == len(tags)
        c = {}; energy = {}
        for group, hit in zip(tags, hits):
            tag = groups[group]
            c[tag] = c.get(tag, 0) + 1
            energy[tag] = energy.get(tag, 0.) + hit[5]
        partition[name] = dict(hit_counts=c, corrected_SD_response_MeV=energy, all_hits=len(hits))
    return dict(index=index, state_supported=bool(valid), plane_box=box, births=births, birth_process_side_counts=counts,
        robust_crossings=crossings, unknown_segment_endpoints=unknown_endpoints, hit_source_partition=partition,
        meaning='All-time corrected SD response, not same-window analog charge or lost-muon-energy correction.', energy_fits=0)
