"""Native standard selection with four radius cuts deferred; compact vertex study."""
import argparse
import json
import multiprocessing as mp
import resource
import subprocess
import tempfile
import time
from pathlib import Path

import awkward as ak
import numpy as np
import uproot
import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'workbook/stage200_vertex'
CACHE = ROOT / 'ntuples/vertex_stage200'
RADII = {'truth': 'Truth dec r < 100 mm', 'max': 'Track R at max radius < 95 mm',
         'ift': 'Track R at IFT < 95 mm', 'vetonu': 'Track rVetoNu < 120 mm'}
EDGES = {'x': np.linspace(-115, 135, 51), 'y': np.linspace(-171, 129, 61),
         'z': np.linspace(-3000, -1950, 53), 'r': np.linspace(0, 220, 89)}
TRUTH = ['truth_' + k for k in ['pdg', 'barcode', 'px', 'py', 'pz', 'prod_x',
         'prod_y', 'prod_z', 'dec_x', 'dec_y', 'dec_z']]
MATCH = ['t_pdg', 't_barcode', 't_pdg_parent', 't_barcode_parent']
SCALARS = ['run', 'eventID', 'truth_dec_r', 'truth_dec_x_nu', 'truth_dec_y_nu',
           'truth_dec_z_nu', 'LeadTrack_r_atMaxRadius', 'LeadTrack_rIFT',
           'LeadTrack_rVetoNu', 'LeadTrack_Theta', 'LeadTrack_Idx']
TRACKS = ['Track_pz0'] + ['Track_' + axis + '_at' + plane
          for plane in ['VetoNu', 'VetoStation1'] for axis in ['X', 'Y', 'ThetaX', 'ThetaY']]


def save(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def first(a):
    return ak.to_numpy(ak.fill_none(ak.firsts(a), np.nan)).astype(float)


def box(x, y, z):
    x, y, z = [v.astype('float32') for v in (x, y, z)]
    return (x > -115) & (x < 135) & (y > -171) & (y < 129) & (z > -3000) & (z < -1950)


def initialize():
    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    cuts = yaml.safe_load((ROOT / 'AnalysisZipFramework/config/cuts.yaml').read_text())
    cuts['Histograms'] = []
    for v in cuts['Cuts'].values():
        v.pop('histograms', None)
    original = yaml.safe_load(yaml.safe_dump(cuts, sort_keys=False))
    for name in RADII.values():
        del cuts['Cuts'][name]
    (OUT / 'deferred_cuts.yaml').write_text(yaml.safe_dump(cuts, sort_keys=False))
    (OUT / 'standard_cuts.yaml').write_text(yaml.safe_dump(original, sort_keys=False))
    old = json.loads((ROOT / 'workbook/stage127_energy_ml/protocol.json').read_text())
    save(OUT / 'protocol.json', dict(sources=old['sources'], batches=16,
         starting_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
         units='positions mm; polar angles mrad; no flux/luminosity weighting',
         all_MC='Every input record with first neutrino truth vertex strictly inside FaserNuBox; no analysis cuts',
         theta_truth='Unique sign-compatible primary muon born within 0.0001 mm of neutrino vertex; atan2(pt,pz)',
         reference='cuts.yaml, truth/reco pz>100 GeV, truth r<100 mm; original Box OR LeadBlock retained'))


def native(source, tmp, cuts, keep):
    files = {'runs': {source['run']: {'data_paths': [source['input']], 'waveform_paths': []}}}
    output = {'nt': {'save_all_input_columns': False, 'save_all_defined_columns': False, 'keep': keep}}
    for name, v in [('files', files), ('output', output)]:
        (tmp / (name + '.yaml')).write_text(yaml.safe_dump(v, sort_keys=False))
    command = [str(ROOT / 'build/analysis'), '--isMC', '-r', str(source['run']), '-j', '1',
               '--file-config', str(tmp / 'files.yaml'), '--output-config', str(tmp / 'output.yaml'),
               '--definitions-config', str(ROOT / 'AnalysisZipFramework/config/definitions.yaml'),
               '--cuts-config', str(cuts), '--grl-config', str(ROOT / 'AnalysisZipFramework/config/grl_config.yaml'),
               '-o', str(tmp / 'selected.root')]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if result.returncode or 'not in the dataframe' in result.stdout:
        raise RuntimeError(result.stdout[-12000:])
    assert 'Reduced charge source: branches in the input NTuple.' in result.stdout
    with uproot.open(tmp / 'selected.root') as f:
        a = f['nt'].arrays(keep)
    return a, command


def masks(d, truth=100, rmax=95, ift=95, vetonu=120):
    # Infinity removes the upper bound, but invalid extrapolations remain excluded.
    result = np.ones(len(d['eventID']), bool)
    for k, bound in [('r', truth), ('rmax', rmax), ('rift', ift), ('rvetonu', vetonu)]:
        result &= np.isfinite(d[k]) & (d[k] < bound)
    return result


def work(source, pilot=False):
    start, cpu = time.perf_counter(), time.process_time()
    with tempfile.TemporaryDirectory(prefix='vertex200_') as dirname:
        tmp = Path(dirname)
        a, command = native(source, tmp, OUT / 'deferred_cuts.yaml', SCALARS + TRUTH + MATCH + TRACKS)
        d = {k: ak.to_numpy(a[col]).astype(float) for k, col in zip(
            ['x', 'y', 'z', 'r', 'rmax', 'rift', 'rvetonu', 'theta'],
            ['truth_dec_x_nu', 'truth_dec_y_nu', 'truth_dec_z_nu', 'truth_dec_r',
             'LeadTrack_r_atMaxRadius', 'LeadTrack_rIFT', 'LeadTrack_rVetoNu', 'LeadTrack_Theta'])}
        for k in ['run', 'eventID']:
            d[k] = ak.to_numpy(a[k])
        lead = ak.argmax(a.Track_pz0, axis=1, keepdims=True)
        for plane, label in [('VetoNu', 'vetonu'), ('VetoStation1', 'veto1')]:
            for axis in ['X', 'Y', 'ThetaX', 'ThetaY']:
                d[label + '_' + axis.lower()] = first(a['Track_' + axis + '_at' + plane][lead])
        candidate = a.truth_pdg == ak.firsts(a.truth_pdg) * 13 / 14
        for axis in 'xyz':
            candidate = candidate & (abs(a['truth_prod_' + axis] - ak.firsts(a['truth_dec_' + axis])) <= .0001)
        d['primary_candidates'] = ak.to_numpy(ak.sum(candidate, axis=1))
        primary = {k: first(a['truth_' + k][candidate]) for k in ['pdg', 'barcode', 'px', 'py', 'pz']}
        d['truth_theta'] = 1000 * np.arctan2(np.hypot(primary['px'], primary['py']), primary['pz'])
        d['truth_theta'][d['primary_candidates'] != 1] = np.nan
        d['nu_theta'] = 1000 * np.arctan2(np.hypot(first(a.truth_px), first(a.truth_py)), first(a.truth_pz))
        d['confirmed'] = d['primary_candidates'] == 1
        for k, v in [('t_pdg', primary['pdg']), ('t_barcode', primary['barcode']),
                     ('t_pdg_parent', first(a.truth_pdg)), ('t_barcode_parent', first(a.truth_barcode))]:
            d['confirmed'] &= first(a[k][lead]) == v
        d['source'] = np.full(len(d['x']), source['index'], np.int32)
        if pilot:
            standard, _ = native(source, tmp, OUT / 'standard_cuts.yaml', ['run', 'eventID'])
            np.testing.assert_array_equal(np.sort(ak.to_numpy(standard.eventID)), np.sort(d['eventID'][masks(d)]))
    hist = {}
    with uproot.open(source['input']) as f:
        raw = f['nt'].arrays(['truth_dec_' + axis for axis in 'xyz'])
        coords = {axis: first(raw['truth_dec_' + axis]) for axis in 'xyz'}
        coords['r'] = np.hypot(coords['x'], coords['y'])
        inside = box(coords['x'], coords['y'], coords['z'])
        for axis in 'xyzr':
            hist['raw_' + axis] = np.histogram(coords[axis][inside], EDGES[axis])[0]
        for u, v in [('x', 'y'), ('z', 'x'), ('z', 'y')]:
            hist['raw_' + u + v] = np.histogram2d(coords[u][inside], coords[v][inside],
                                                  bins=[EDGES[u], EDGES[v]])[0].astype('int64')
        requested = f.file.source.num_requested_bytes
        raw_N = f['nt'].num_entries
    assert hist['raw_xy'].sum() == inside.sum()
    meta = dict(index=source['index'], raw_N=raw_N, box_N=int(inside.sum()),
                box_r100_N=int((inside & (coords['r'] < 100)).sum()), candidates_N=len(d['x']),
                standard_N=int(masks(d).sum()), standard_box_N=int((masks(d) & box(d['x'], d['y'], d['z'])).sum()),
                wall_s=time.perf_counter()-start, python_CPU_s=time.process_time()-cpu,
                child_CPU_s=resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime + resource.getrusage(resource.RUSAGE_CHILDREN).ru_stime,
                peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                peak_child_RSS_KiB=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
                uproot_raw_requested_bytes=int(requested), native_read_bytes='未测量', native_command=command,
                pilot_native_standard_exact=pilot)
    return d, hist, meta


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--init', action='store_true')
    p.add_argument('--pilot', type=int)
    p.add_argument('--batch', type=int)
    p.add_argument('--workers', type=int, default=4)
    a = p.parse_args()
    if a.init:
        initialize()
        return
    protocol = json.loads((OUT / 'protocol.json').read_text())
    start = time.perf_counter()
    if a.pilot is not None:
        sources = [s for s in protocol['sources'] if s['index'] == a.pilot]
        results = [work(sources[0], True)]
        label = 'pilot_' + str(a.pilot)
    else:
        sources = protocol['sources'][a.batch::protocol['batches']]
        with mp.get_context('spawn').Pool(a.workers) as pool:
            results = pool.map(work, sources)
        label = 'batch_' + str(a.batch)
    d = {k: np.concatenate([r[0][k] for r in results]) for k in results[0][0]}
    d.update({k: np.sum([r[1][k] for r in results], axis=0) for k in results[0][1]})
    CACHE.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(CACHE / (label + '.npz'), **d)
    report = dict(files=[r[2] for r in results], wall_s=time.perf_counter()-start,
                  peak_parent_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    save(OUT / (label + '.json'), report)
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
