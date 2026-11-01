"""Stage35: the same CaloNu event supports both readout-on/off candidates."""
import csv
import json
import resource
import time
from pathlib import Path

import awkward as ak
import numpy as np
import uproot
import yaml

from track_response import TRACK_BRANCHES, derive


def configuration(repo):
    return yaml.safe_load((repo / 'ml/configs/calonu_ablation.yaml').read_text())


def manifest(repo):
    return list(csv.DictReader((repo / 'ml/configs/calonu_files.tsv').open(), delimiter='\t'))


def feature_names(repo):
    base = yaml.safe_load((repo / 'ml/configs/baseline.yaml').read_text())
    extra = yaml.safe_load((repo / 'ml/configs/track_response.yaml').read_text())['features']
    names = sum([base['feature_groups'][g] for g in base['feature_versions']['F5']], [])
    return names, extra


def first(arr, name):
    return ak.to_numpy(ak.fill_none(ak.firsts(arr[name]), np.nan)).astype(float)


def truth_diagnostics(arr):
    # This older PHYS has no truth_barcode: never invent a barcode-confirmed flag.
    for key in ['px', 'py', 'pz', 'm', 'prod_x', 'prod_y', 'prod_z', 'dec_x', 'dec_y', 'dec_z']:
        assert bool(ak.all(ak.num(arr['truth_' + key]) == ak.num(arr['truth_pdg'])))
    candidate = arr['truth_pdg'] == ak.firsts(arr['truth_pdg']) * 13 / 14
    for axis in ['x', 'y', 'z']:
        candidate = candidate & (abs(arr['truth_prod_' + axis] - ak.firsts(arr['truth_dec_' + axis])) <= .0001)
    n = ak.to_numpy(ak.sum(candidate, axis=1))
    valid = n == 1

    def primary(key):
        value = ak.to_numpy(ak.fill_none(ak.firsts(arr['truth_' + key][candidate]), np.nan)).astype(float)
        value[~valid] = np.nan
        return value

    enu = np.sqrt(sum(first(arr, 'truth_' + a) ** 2 for a in ['px', 'py', 'pz', 'm'])) / 1000
    p = np.sqrt(sum(primary(a) ** 2 for a in ['px', 'py', 'pz'])) / 1000
    e = np.sqrt((p * 1000) ** 2 + primary('m') ** 2) / 1000
    lead = ak.argmax(arr['Track_pz0'], axis=1, keepdims=True)
    proxy = valid.copy()
    for field in ['pdg', 'pdg_parent', 'px', 'py', 'pz', 'prodVtx_x', 'prodVtx_y', 'prodVtx_z']:
        assert bool(ak.all(ak.num(arr['t_' + field]) == ak.num(arr['Track_pz0'])))
        value = ak.to_numpy(ak.flatten(arr['t_' + field][lead])).astype(float)
        if field == 'pdg_parent':
            proxy &= value == first(arr, 'truth_pdg')
        elif field.startswith('prodVtx_'):
            proxy &= abs(value - primary('prod_' + field[-1])) <= .0001
        elif field == 'pdg':
            proxy &= value == primary('pdg')
        else:
            proxy &= np.isclose(value, primary(field), rtol=2e-6, atol=.001)
    result = dict(primary_p_GeV=p, primary_valid=valid, primary_candidates=n, truth_E_GeV=enu,
                  y_lepton=1 - e / enu, primary_kinematic_parent_proxy=proxy,
                  barcode_confirmation_available=np.zeros(len(arr), bool))
    for axis in ['x', 'y', 'z']:
        result['vertex_' + axis + '_mm'] = first(arr, 'truth_dec_' + axis)
    return result


def select_and_features(arr, repo):
    """Numpy translation checked event-for-event against the repository C++ cuts."""
    names, extra = feature_names(repo)
    lead = ak.argmax(arr['Track_pz0'], axis=1, keepdims=True, mask_identity=True)

    def get(name):
        return ak.to_numpy(ak.fill_none(ak.firsts(arr[name][lead]), np.nan)).astype(float)

    def scalar(name):
        return ak.to_numpy(arr[name]).astype(float)

    x, y, z = [first(arr, 'truth_dec_' + axis) for axis in ['x', 'y', 'z']]
    fidbox = (x > -115) & (x < 135) & (y > -171) & (y < 129) & (z > -3000) & (z < -1950)
    fidlead = (abs(x) < 300) & (abs(y) < 300) & (z > -1769.65) & (z < -1619.65)
    pz = get('Track_pz0')
    with np.errstate(divide='ignore', invalid='ignore'):
        theta = np.arctan(np.hypot(get('Track_px0'), get('Track_py0')) / pz) * 1000
        chi = get('Track_Chi2') / get('Track_nDoF')
    rnu = np.hypot(get('Track_X_atVetoNu'), get('Track_Y_atVetoNu'))
    rift = np.hypot(get('Track_X_atVetoStation2'), get('Track_Y_atVetoStation2'))
    trig_y = get('Track_Y_atTrig')
    bottom = scalar('Timing0_charge') + scalar('Timing1_charge')
    top = scalar('Timing2_charge') + scalar('Timing3_charge')
    timing = ((trig_y > 20) & (top > 20)) | ((trig_y < -20) & (bottom > 20)) | ((abs(trig_y) < 20) & (top + bottom > 20))
    cc = ak.to_numpy(ak.any((abs(arr['truth_pdg']) == 11) | (abs(arr['truth_pdg']) == 13) | (abs(arr['truth_pdg']) == 15), axis=1))
    cuts = [~((z >= -2928) & (z <= -2812)), cc, abs(first(arr, 'truth_pdg')) == 14,
            fidbox | fidlead, np.hypot(x, y) < 100, first(arr, 'truth_pz') > 100000,
            scalar('longTracks') > 0, (scalar('Veto20_charge') > 40) & (scalar('Veto21_charge') > 40),
            timing, (scalar('Preshower0_charge') > 2.5) & (scalar('Preshower1_charge') > 2.5),
            pz > 100000, get('Track_nLayers') >= 7, get('Track_nDoF') >= 9, chi < 15,
            get('Track_r_atMaxRadius') < 95, rift < 95, rnu < 120, theta < 25,
            scalar('VetoNu0_reduced_charge') < 30, scalar('VetoNu1_reduced_charge') < 30]
    cumulative = np.logical_and.accumulate(np.column_stack([np.ones(len(arr), bool)] + cuts), axis=1)
    keep = cumulative[:, -1]
    selected = arr[keep]
    values = derive(selected, extra, diagnostic=False)
    values.update(truth_diagnostics(selected))
    derived = {'LeadTrack_Theta': theta, 'LeadTrack_Chi2_NDF': chi, 'LeadTrack_rVetoNu': rnu}
    for suffix in ['charge', 'nDoF', 'nLayers', 'r_atMaxRadius']:
        derived['LeadTrack_' + suffix] = get('Track_' + suffix)
    for key, source in [('p_GeV', 'p0'), ('px0_GeV', 'px0'), ('py0_GeV', 'py0')]:
        derived['ML_mu_' + key] = get('Track_' + source) / 1000
    for suffix, source in [('x0_mm', 'x0'), ('y0_mm', 'y0'), ('z0_mm', 'z0'),
                           ('X_atVetoNu_mm', 'X_atVetoNu'), ('Y_atVetoNu_mm', 'Y_atVetoNu'),
                           ('X_atCalo_mm', 'X_atCalo'), ('Y_atCalo_mm', 'Y_atCalo')]:
        derived['ML_mu_' + suffix] = get('Track_' + source)
    for channel in ['0', '1', '2', '3', '_total']:
        derived['ML_calo' + channel + '_E_EM_GeV'] = scalar('Calo' + channel + '_E_EM') / 1000
    for axis in ['x', 'y']:
        a = arr['SpacePoint_' + axis]
        mean = ak.to_numpy(ak.fill_none(ak.mean(a, axis=1), np.nan)).astype(float)
        mean2 = ak.to_numpy(ak.fill_none(ak.mean(a * a, axis=1), np.nan)).astype(float)
        derived['ML_sp_mean_' + axis + '_mm'] = mean
        derived['ML_sp_rms_' + axis + '_mm'] = np.sqrt(np.maximum(0, mean2 - mean * mean))
    for name in names:
        values[name] = derived[name][keep] if name in derived else scalar(name)[keep]
    for i in ['0', '1', '2', '3', '_total']:
        values['ML_calonu' + i + '_E_EM_GeV'] = scalar('CaloNu' + i + '_E_EM')[keep] / 1000
    # Audit channels/status/zero handling; none of these diagnostics enters features.
    for i in range(4):
        for suffix in ['charge', 'raw_charge', 'status', 'nMIP', 'E_dep', 'E_EM']:
            values[f'CaloNu{i}_{suffix}'] = scalar(f'CaloNu{i}_{suffix}')[keep]
    for name in ['CaloNu_total_fit_E_EM', 'CaloNu_total_raw_E_EM', 'CaloNu_total_E_EM']:
        values[name] = scalar(name)[keep]
    assert np.isfinite(values['truth_E_GeV']).all() and (values['truth_E_GeV'] > 0).all()
    np.testing.assert_array_equal(values['reco_p_GeV'], values['ML_mu_p_GeV'])
    return values, cumulative


def branches(repo):
    names, _ = feature_names(repo)
    simple = [n for n in names if not n.startswith(('ML_', 'LeadTrack_'))]
    truth = ['truth_' + k for k in ['pdg', 'px', 'py', 'pz', 'm']]
    truth += [f'truth_{kind}_{axis}' for kind in ['prod', 'dec'] for axis in ['x', 'y', 'z']]
    tracks = TRACK_BRANCHES + ['Track_' + k for k in ['nDoF', 'nLayers', 'Chi2', 'r_atMaxRadius', 'X_atVetoNu',
               'Y_atVetoNu', 'X_atVetoStation2', 'Y_atVetoStation2', 'Y_atTrig', 'X_atCalo', 'Y_atCalo']]
    calo = ['Calo' + i + '_E_EM' for i in ['0', '1', '2', '3', '_total']]
    calonu = [f'CaloNu{i}_{k}' for i in range(4) for k in ['charge', 'raw_charge', 'status', 'nMIP', 'E_dep', 'E_EM']]
    calonu += ['CaloNu_total_fit_E_EM', 'CaloNu_total_raw_E_EM', 'CaloNu_total_E_EM']
    return sorted(set(['run', 'eventID', 'Track_PropagationError', 'SpacePoint_x', 'SpacePoint_y', 'SpacePoint_z',
                       't_pdg', 't_pdg_parent', 't_px', 't_py', 't_pz', 't_prodVtx_x', 't_prodVtx_y', 't_prodVtx_z'] + simple + truth + tracks + calo + calonu))


def extract_one(repo, row):
    tick = time.perf_counter()
    with uproot.open(row['input']) as source:
        tree = source['nt']
        arr = tree.arrays(branches(repo))
        entries = tree.num_entries
    for field in branches(repo):
        if field.startswith('Track_') and field != 'Track_PropagationError':
            assert bool(ak.all(ak.num(arr[field]) == ak.num(arr['Track_pz0'])))
    for axis in ['y', 'z']:
        assert bool(ak.all(ak.num(arr['SpacePoint_x']) == ak.num(arr['SpacePoint_' + axis])))
    assert bool(ak.all(ak.num(arr['SpacePoint_x']) == arr['SpacePoints']))
    values, cumulative = select_and_features(arr, repo)
    n = len(values['run'])
    values.update(manifest_index=np.full(n, int(row['index']), np.int32),
                  group=np.full(n, row['group']), partition=np.full(n, row['partition']), component=np.full(n, row['component']))
    assert len(set(zip(values['run'], values['eventID']))) == n
    report = dict(index=int(row['index']), input=row['input'], partition=row['partition'], input_events=entries,
                  selected_events=n, cutflow=cumulative.sum(axis=0).tolist(),
                  calonu_nonzero=int((np.isfinite(values['CaloNu_total_E_EM']) & (values['CaloNu_total_E_EM'] != 0)).sum()),
                  calonu_nonfinite=int((~np.isfinite(values['CaloNu_total_E_EM'])).sum()),
                  wall_s=time.perf_counter() - tick)
    return values, report


def extract(repo, batch, output, index=None):
    cfg = configuration(repo)
    tick = time.perf_counter()
    cpu = time.process_time()
    rows = manifest(repo)
    rows = [r for r in rows if int(r['index']) == index] if index is not None else rows[batch * cfg['batch_size']:(batch + 1) * cfg['batch_size']]
    assert rows
    sets = []
    reports = []
    for row in rows:
        values, report = extract_one(repo, row)
        sets.append(values)
        reports.append(report)
        print(json.dumps(report), flush=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    metadata = dict(cfg=cfg, reports=reports, wall_s=time.perf_counter() - tick, cpu_s=time.process_time() - cpu,
                    peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
    np.savez_compressed(output, **{k: np.concatenate([v[k] for v in sets]) for k in sets[0]}, metadata_json=np.array(json.dumps(metadata)))


def load(repo, part):
    with np.load(repo / f'ntuples/energy_ml_stage35/{part}.npz') as z:
        return {k: z[k] for k in z.files if k != 'metadata_json'}
