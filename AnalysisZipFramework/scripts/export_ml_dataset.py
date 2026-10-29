#!/usr/bin/env python3
"""Extract one official MC file with the existing Analysis executable and frozen cuts.

Only a scalar NPZ survives. Temporary ROOT snapshots (including cut flags) are
removed after cutflow and selected IDs have been checked against stage09/10.
"""
import argparse
import json
import resource
import subprocess
import tempfile
import time
from pathlib import Path

import awkward as ak
import numpy as np
import uproot
import yaml


def audit_input(path):
    start = time.perf_counter()
    with uproot.open(path) as source:
        tree = source['nt']
        columns = ['run', 'eventID', 'truth_pdg', 'truth_barcode', 'truth_P',
                   'truth_px', 'truth_py', 'truth_pz', 'truth_m', 'GenWeights',
                   'CrossSection', 'SpacePoint_x', 'SpacePoint_y', 'SpacePoint_z',
                   'Track_pz0', 'Track_p0', 'Track_px0', 'Track_py0', 'Track_Chi2',
                   'Track_nDoF', 'Track_nLayers', 'Track_charge', 'Track_x0',
                   'Track_y0', 'Track_z0', 'Track_X_atVetoNu', 'Track_Y_atVetoNu',
                   'Track_X_atCalo', 'Track_Y_atCalo']
        arrays = tree.arrays(columns)
        n = tree.num_entries
    count = lambda x: int(ak.sum(x))
    lengths = lambda x: ak.num(arrays[x])
    truth_mismatch = np.zeros(n, dtype=bool)
    track_mismatch = {}
    for col in columns:
        if col.startswith('truth_'):
            truth_mismatch |= ak.to_numpy(lengths(col) != lengths('truth_pdg'))
        if col.startswith('Track_'):
            track_mismatch[col] = count(lengths(col) != lengths('Track_pz0'))
    if truth_mismatch.any() or any(track_mismatch.values()):
        raise RuntimeError('Label/used-track vector alignment failure')
    if count((lengths('SpacePoint_x') != lengths('SpacePoint_y')) |
             (lengths('SpacePoint_x') != lengths('SpacePoint_z'))):
        raise RuntimeError('SpacePoint xyz lengths disagree')
    first = {c: ak.to_numpy(ak.fill_none(ak.firsts(arrays[c]), np.nan))
             for c in columns if c.startswith('truth_')}
    energy = np.sqrt(sum(first[c]**2 for c in ['truth_px', 'truth_py', 'truth_pz', 'truth_m']))/1000
    p = np.sqrt(sum(first[c]**2 for c in ['truth_px', 'truth_py', 'truth_pz']))
    valid = np.isfinite(energy) & (energy > 0)
    relative = np.abs(p-first['truth_P'])/np.maximum(p, 1)
    weights = ak.to_numpy(ak.flatten(arrays.GenWeights))
    keys = np.column_stack([ak.to_numpy(arrays.run), ak.to_numpy(arrays.eventID)])
    if len(np.unique(keys, axis=0)) != n:
        raise RuntimeError('Duplicate input (run,eventID)')
    report = dict(events=n, truth_alignment_failures=int(truth_mismatch.sum()),
                  used_track_alignment_failures=track_mismatch,
                  truth_first_pdg_counts={str(int(v)):int(k) for v,k in zip(*np.unique(first['truth_pdg'],return_counts=True))},
                  invalid_first_energy=int((~valid).sum()),
                  truth_P_component_max_relative_difference=float(np.nanmax(relative)),
                  truth_E_minus_pz_max_GeV=float(np.nanmax(energy-first['truth_pz']/1000)),
                  genweight_values=np.unique(weights).tolist(),
                  genweight_lengths=np.unique(ak.to_numpy(ak.num(arrays.GenWeights))).tolist(),
                  cross_sections=np.unique(ak.to_numpy(arrays.CrossSection)).tolist(),
                  spacepoints_max=int(ak.max(lengths('SpacePoint_x'))),
                  audit_wall_s=time.perf_counter()-start)
    return report, keys, energy


def extract(args):
    started = time.perf_counter()
    repo = args.repo.resolve()
    cfg = yaml.safe_load((repo/'ml/configs/baseline.yaml').read_text())
    features = sum(cfg['feature_groups'].values(), [])
    audit, raw_keys, energy = audit_input(args.input)
    with tempfile.TemporaryDirectory(prefix='nu_energy_') as tmp:
        tmp = Path(tmp)
        defs = yaml.safe_load((repo/'AnalysisZipFramework/config/definitions.yaml').read_text())
        extra = yaml.safe_load((repo/'AnalysisZipFramework/config/ml_definitions.yaml').read_text())
        if defs['Definitions'].keys() & extra['Definitions'].keys():
            raise RuntimeError('Duplicate additional definition')
        defs['Definitions'].update(extra['Definitions'])
        (tmp/'definitions.yaml').write_text(yaml.safe_dump(defs,sort_keys=False))
        run = int(raw_keys[0,0])
        (tmp/'files.yaml').write_text(yaml.safe_dump({'runs':{run:{'data_paths':[str(args.input)],'waveform_paths':[]}}}))
        command = [str(args.executable.resolve()), '--isMC', '-r', str(run),
                   '--file-config', str(tmp/'files.yaml'), '--definitions-config', str(tmp/'definitions.yaml'),
                   '--cuts-config', str(repo/'AnalysisZipFramework/config/cuts.yaml'),
                   '--grl-config', str(repo/'AnalysisZipFramework/config/grl_config.yaml'),
                   '--output-config', str(repo/'AnalysisZipFramework/config/ml_output_columns.yaml'),
                   '-o', str(tmp/'selected.root'), '-j', str(args.threads)]
        analysis_start = time.perf_counter()
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if result.returncode:
            raise RuntimeError(result.stdout[-12000:])
        if 'does not match any' in result.stdout or 'not in the dataframe' in result.stdout:
            raise RuntimeError(result.stdout)
        analysis_wall = time.perf_counter()-analysis_start
        with uproot.open(tmp/'selected.root') as source:
            data = source['nt'].arrays(library='np')
            cutflow = source['cutflow'].arrays(library='np')
            flags = source['eventID_pass'].arrays(library='np')
        order = np.lexsort((data['eventID'],data['run']))
        data = {k:v[order] for k,v in data.items()}
        input_order = np.lexsort((raw_keys[:,1],raw_keys[:,0]))
        selected_keys = np.column_stack([data['run'],data['eventID']])
        raw_lookup = {tuple(k): i for i,k in enumerate(raw_keys)}
        selected_raw = np.array([raw_lookup[tuple(k)] for k in selected_keys], dtype=int)
        if not np.allclose(data[cfg['target']],energy[selected_raw],rtol=2e-7,atol=1e-7):
            raise RuntimeError('Independent numpy/C++ label cross-check failed')
        if not np.all((data['ML_truth_E_GeV'] > 0) & np.isfinite(data['ML_truth_E_GeV'])):
            raise RuntimeError('Invalid selected label')
        if not np.all((data['ML_mu_p_GeV'] > 0) & np.isfinite(data['ML_mu_p_GeV'])):
            raise RuntimeError('Invalid selected muon momentum')
        if not np.all(np.abs(data['ML_truth_pdg']) == 14):
            raise RuntimeError('Selected incoming particle is not a muon neutrino')
        if len(flags['run']) != len(raw_keys):
            raise RuntimeError('Cut flags do not cover input')
        flag_order = np.lexsort((flags['eventID'],flags['run']))
        for i,k in enumerate(['run','eventID']):
            if not np.array_equal(flags[k][flag_order],raw_keys[input_order,i]):
                raise RuntimeError('Cut flag/input ID mismatch')
        ref_path = repo/'workbook/stage09_tracking_comparison/paired_results.npz'
        with np.load(ref_path) as ref:
            idx = np.flatnonzero(ref['manifest_indices']==args.index).item()
            expected = ref['counts'][idx,2]
        if not np.array_equal(cutflow['passed'],expected[1:]):
            raise RuntimeError(f'Stage09 cutflow mismatch: {cutflow["passed"]} versus {expected}')
        # Stage10 saved all truth-fiducial keys and each reco-cut bit. Check the exact final set.
        reference = args.event_reference or repo/'workbook/stage10_tracking_z/fiducial_events.npz'
        with np.load(reference) as ref:
            if 'file_offsets' in ref:
                j = np.flatnonzero(ref['manifest_indices']==args.index).item()
                start,stop = ref['file_offsets'][j:j+2]
                indices = np.arange(start,stop)
            else:
                indices = np.arange(len(ref['event_run']))
            keep = indices[ref['event_cut_bits'][indices,2] == (2**14-1)]
            ref_keys = np.column_stack([ref['event_run'][keep],ref['event_eventID'][keep]])
            ref_keys = ref_keys[np.lexsort((ref_keys[:,1],ref_keys[:,0]))]
        if not np.array_equal(selected_keys,ref_keys):
            raise RuntimeError('Stage10 exact final event set mismatch')
        missing = set(features+[cfg['target']]+cfg['metadata_columns'])-set(data)
        if missing:
            raise RuntimeError(f'Missing configured columns: {missing}')
        bad_features = {k:int((~np.isfinite(data[k])).sum()) for k in features}
        # XGBoost has explicit missing-value handling; no imputation fitted on validation/test.
        for k in features:
            if bad_features[k]:
                data[k] = data[k].astype(float)
                data[k][~np.isfinite(data[k])] = np.nan
        report = dict(input=str(args.input), index=args.index, run=run, threads=args.threads,
                      selected_events=len(order), raw_audit=audit,
                      feature_nonfinite_counts=bad_features,
                      label_E_minus_pz_quantiles_GeV=np.quantile(data[cfg['target']]-data['truth_pz_nu'],[0,.5,.99,1]).tolist() if len(order) else [],
                      max_label_relative_component_difference=float(np.max(np.abs(data[cfg['target']]-energy[selected_raw])/energy[selected_raw])) if len(order) else 0,
                      stage09_cutflow_verified=True, stage10_selected_keys_verified=True,
                      analysis_wall_s=analysis_wall, total_wall_s=time.perf_counter()-started,
                      parent_peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                      analysis_peak_rss_MiB=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss/1024,
                      config=cfg, definitions=defs, command=command)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        np.savez_compressed(args.output, **data, manifest_index=np.full(len(order),args.index,dtype=np.int32),
                            cutflow_passed=cutflow['passed'], cutflow_names=cutflow['cut_name'].astype(str),
                            metadata_json=np.array(json.dumps(report)))
    print(json.dumps({k:v for k,v in report.items() if k not in ['config','definitions','command']},ensure_ascii=False),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[2])
    p.add_argument('--executable',type=Path,required=True)
    p.add_argument('--input',required=True)
    p.add_argument('--index',type=int,required=True)
    p.add_argument('--event-reference',type=Path)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--threads',type=int,default=1)
    args=p.parse_args()
    if args.threads<1: p.error('threads must be positive')
    extract(args)


if __name__=='__main__':
    main()
