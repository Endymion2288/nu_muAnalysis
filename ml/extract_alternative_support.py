#!/usr/bin/env python3
"""Stage70 original low-pz selection plus the unchanged 62 audited readouts."""
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

from audited_features import REPO, SCINTILLATORS, build, configuration
from frozen_evaluation import truth_diagnostics
from track_response import TRACK_BRANCHES, derive, configuration as track_configuration


def extract(index, input_path, output, qa=False, source=None):
    start, cpu = time.perf_counter(), time.process_time()
    if source is None:
        source = json.loads((REPO/'ml/configs/alternative_support_pilot.json').read_text())['sources'][index]
    base = yaml.safe_load((REPO/'ml/configs/baseline.yaml').read_text())
    names = sum([base['feature_groups'][k] for k in base['feature_versions']['F5']], [])
    extra = track_configuration(REPO)['features']
    scalars = ['run', 'eventID'] + [s+'_'+k for s in SCINTILLATORS for k in ['charge', 'raw_charge', 'status']]
    scalars += [f'Calo{i}_status' for i in range(4)]
    with tempfile.TemporaryDirectory(prefix='stage70_selection_') as temporary:
        tmp = Path(temporary)
        defs = yaml.safe_load((REPO/'AnalysisZipFramework/config/definitions.yaml').read_text())
        defs['Definitions'].update(yaml.safe_load((REPO/'AnalysisZipFramework/config/ml_definitions.yaml').read_text())['Definitions'])
        (tmp/'definitions.yaml').write_text(yaml.safe_dump(defs, sort_keys=False))
        (tmp/'files.yaml').write_text(yaml.safe_dump({'runs': {source['run']: {'data_paths': [str(input_path)], 'waveform_paths': []}}}))
        command = [str(REPO/'build/analysis'), '--isMC', '-r', str(source['run']), '-j', '1',
                   '--file-config', str(tmp/'files.yaml'), '--definitions-config', str(tmp/'definitions.yaml'),
                   '--cuts-config', str(REPO/'AnalysisZipFramework/config/ml_low_energy_cuts.yaml'),
                   '--grl-config', str(REPO/'AnalysisZipFramework/config/grl_config.yaml'),
                   '--output-config', str(REPO/'AnalysisZipFramework/config/ml_output_columns.yaml'), '-o', str(tmp/'selected.root')]
        run = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if run.returncode or 'not in the dataframe' in run.stdout:
            raise RuntimeError(run.stdout[-16000:])
        with uproot.open(tmp/'selected.root') as f:
            selected = f['nt'].arrays(library='np')
            cutflow = f['cutflow'].arrays(library='np')
        branches = ['run', 'eventID', 'Track_PropagationError', 'Track_isForward'] + TRACK_BRANCHES
        branches += ['truth_'+k for k in ['pdg', 'barcode', 'px', 'py', 'pz', 'm', 'prod_x', 'prod_y', 'prod_z', 'dec_x', 'dec_y', 'dec_z']]
        branches += ['t_pdg', 't_barcode', 't_pdg_parent', 't_barcode_parent']
        with uproot.open(input_path) as f:
            tree = f['nt']
            raw_N = tree.num_entries
            assert raw_N <= 20000
            raw = tree.arrays(scalars, library='np')
            assert len(set(raw['eventID'])) == raw_N and np.all(raw['run'] == source['run'])
            take = np.isin(raw['eventID'], selected['eventID'])
            arr = tree.arrays(branches)[take]
            requested = int(f.file.source.num_requested_bytes)
        lookup = {int(e):i for i,e in enumerate(selected['eventID'])}
        order = np.array([lookup[int(e)] for e in ak.to_numpy(arr.eventID)], dtype=int)
        assert len(order) == len(lookup)
        track = derive(arr, extra)
        truth = truth_diagnostics(arr, .0001)
        np.testing.assert_array_equal(track['reco_p_GeV'], selected['ML_mu_p_GeV'][order])
        np.testing.assert_allclose(truth['truth_E_GeV'], selected['ML_truth_E_GeV'][order], rtol=1e-12)
        old_x = np.column_stack([selected[k][order] for k in names] + [track[k] for k in extra]).astype('float32')
        old_x[~np.isfinite(old_x)] = np.nan
        n = len(order)
        dataset = dict(x=old_x, metadata_json=np.array(json.dumps(dict(features=names+extra))),
                       reco_p_GeV=track['reco_p_GeV'], reco_pz_GeV=selected['LeadTrack_pz0'][order])
        supplement = dict(row=np.arange(n),
                          raw_charge=np.column_stack([raw[s+'_raw_charge'][take] for s in SCINTILLATORS]),
                          status=np.column_stack([raw[s+'_status'][take] for s in SCINTILLATORS]),
                          calo_status=np.column_stack([raw[f'Calo{i}_status'][take] for i in range(4)]))
        for detector in SCINTILLATORS:
            fit = raw[detector+'_charge'][take].astype('float32')
            fit[~np.isfinite(fit)] = np.nan
            np.testing.assert_array_equal(fit, old_x[:,(names+extra).index(detector+'_charge')])
        x = build(dataset, supplement)
        assert x.shape == (n, 62)
        np.testing.assert_array_equal(x[:,0], dataset['reco_pz_GeV'].astype('float32'))
        assert np.all(dataset['reco_pz_GeV'] > 50) and np.all(selected['ML_truth_pz_MeV'][order]/1000 > 50)
        incoming = np.column_stack([selected[k][order] for k in ['ML_truth_pdg', 'ML_truth_px_MeV', 'ML_truth_py_MeV', 'ML_truth_pz_MeV']])
        data = dict(x=x, **truth, run=track['run'], eventID=track['eventID'],
                    input_entry=np.flatnonzero(take), reco_pz_GeV=dataset['reco_pz_GeV'], incoming=incoming,
                    raw_charge=supplement['raw_charge'], status=supplement['status'], calo_status=supplement['calo_status'])
        metadata = dict(source=source, qa=qa, raw_N=raw_N, selected_N=n,
                        features=configuration()['features'], feature_version=configuration()['version'],
                        cutflow_passed=cutflow['passed'].tolist(), cutflow_names=cutflow['cut_name'].astype(str).tolist(),
                        requested_uproot_bytes=requested, analysis_ROOT_requested_bytes='未测量',
                        all_raw_schema_present=True, all_raw_finite_N={s:int(np.isfinite(raw[s+'_raw_charge']).sum()) for s in SCINTILLATORS},
                        all_status_values={s:np.unique(raw[s+'_status']).astype(int).tolist() for s in SCINTILLATORS},
                        actual_command=command, wall_s=time.perf_counter()-start, cpu_s=time.process_time()-cpu,
                        child_user_s=resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime,
                        child_system_s=resource.getrusage(resource.RUSAGE_CHILDREN).ru_stime,
                        peak_parent_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                        peak_analysis_rss_MiB=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss/1024,
                        unit_contract='native MeV/mm; analysis momentum/E divided by1000; scintillator pC; incoming exact key in native MeV')
        output.parent.mkdir(parents=True, exist_ok=True)
        assert not output.exists()
        np.savez_compressed(output, **data, metadata_json=np.array(json.dumps(metadata)))
        with np.load(output) as z:
            for key,value in data.items():
                np.testing.assert_array_equal(z[key], value)
        print('STAGE70_EXTRACT', json.dumps(metadata), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', type=int, required=True, choices=[0, 1])
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--qa', action='store_true')
    args = parser.parse_args()
    extract(args.index, args.input, args.output, args.qa)
