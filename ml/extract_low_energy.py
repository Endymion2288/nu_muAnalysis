#!/usr/bin/env python3
"""Run the existing Analysis definitions with the two explicit 50 GeV cuts.

One full PHYS file per task. A temporary scalar ROOT snapshot is removed after
joining selected identities to the original track/truth vectors. No xAOD kept.
"""
import argparse
import csv
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
from frozen_evaluation import truth_diagnostics
from track_response import TRACK_BRANCHES, configuration, derive

REPO = Path(__file__).resolve().parents[1]


def extract(index, input_path, output, smoke=False):
    tick, cpu = time.perf_counter(), time.process_time()
    row = list(csv.DictReader((REPO/'ml/configs/low_energy_files.tsv').open(), delimiter='\t'))[index]
    base = yaml.safe_load((REPO/'ml/configs/baseline.yaml').read_text())
    names = sum([base['feature_groups'][k] for k in base['feature_versions']['F5']], [])
    extra = configuration(REPO)['features']
    with tempfile.TemporaryDirectory(prefix='low_energy_') as temporary:
        tmp = Path(temporary)
        defs = yaml.safe_load((REPO/'AnalysisZipFramework/config/definitions.yaml').read_text())
        defs['Definitions'].update(yaml.safe_load((REPO/'AnalysisZipFramework/config/ml_definitions.yaml').read_text())['Definitions'])
        (tmp/'definitions.yaml').write_text(yaml.safe_dump(defs, sort_keys=False))
        with uproot.open(input_path) as source:
            tree = source['nt']
            raw_N = tree.num_entries
        (tmp/'files.yaml').write_text(yaml.safe_dump({'runs':{int(row['run']):{'data_paths':[str(input_path)], 'waveform_paths':[]}}}))
        command = [str(REPO/'build/analysis'), '--isMC', '-r', row['run'], '-j', '1',
                   '--file-config', str(tmp/'files.yaml'), '--definitions-config', str(tmp/'definitions.yaml'),
                   '--cuts-config', str(REPO/'AnalysisZipFramework/config/ml_low_energy_cuts.yaml'),
                   '--grl-config', str(REPO/'AnalysisZipFramework/config/grl_config.yaml'),
                   '--output-config', str(REPO/'AnalysisZipFramework/config/ml_output_columns.yaml'), '-o', str(tmp/'selected.root')]
        run = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if run.returncode or 'not in the dataframe' in run.stdout:
            raise RuntimeError(run.stdout[-16000:])
        with uproot.open(tmp/'selected.root') as source:
            selected = source['nt'].arrays(library='np')
            cutflow = source['cutflow'].arrays(library='np')
        branches = ['run','eventID','Track_PropagationError','Track_isForward'] + TRACK_BRANCHES
        branches += ['truth_'+k for k in ['pdg','barcode','px','py','pz','m','prod_x','prod_y','prod_z','dec_x','dec_y','dec_z']]
        branches += ['t_pdg','t_barcode','t_pdg_parent','t_barcode_parent']
        with uproot.open(input_path) as source:
            tree = source['nt']; ids = tree['eventID'].array(library='np')
            arr = tree.arrays(branches)[np.isin(ids, selected['eventID'])]
            requested = int(source.file.source.num_requested_bytes)
        lookup = {int(e):i for i,e in enumerate(selected['eventID'])}
        order = np.array([lookup[int(e)] for e in ak.to_numpy(arr.eventID)], dtype=int)
        assert len(order) == len(lookup) and len(set(ak.to_list(arr.eventID))) == len(order)
        track = derive(arr, extra); truth = truth_diagnostics(arr, .0001)
        np.testing.assert_array_equal(track['reco_p_GeV'], selected['ML_mu_p_GeV'][order])
        np.testing.assert_allclose(truth['truth_E_GeV'], selected['ML_truth_E_GeV'][order], rtol=1e-12)
        x = np.column_stack([selected[k][order] for k in names] + [track[k] for k in extra]).astype('float32')
        x[~np.isfinite(x)] = np.nan
        data = dict(x=x, **truth, run=track['run'], eventID=track['eventID'],
                    reco_p_GeV=track['reco_p_GeV'], reco_pz_GeV=selected['LeadTrack_pz0'][order],
                    truth_pz_GeV=selected['ML_truth_pz_MeV'][order]/1000,
                    incoming=np.column_stack([selected[k][order] for k in ['ML_truth_pdg','ML_truth_px_MeV','ML_truth_py_MeV','ML_truth_pz_MeV']]),
                    source=np.full(len(order),index,dtype='int32'))
        assert np.all(data['reco_pz_GeV']>50) and np.all(data['truth_pz_GeV']>50)
        old = (data['reco_pz_GeV']>100)&(data['truth_pz_GeV']>100)
        verification = {}
        old_path = REPO/f"ntuples/energy_ml_stage12/shards/{int(row['old_index']):03d}.npz"
        if old_path.exists():
            with np.load(old_path) as z:
                old_lookup = {int(e):i for i,e in enumerate(z['eventID'])}
                assert set(data['eventID'][old]) == set(old_lookup)
                old_order = np.array([old_lookup[int(e)] for e in data['eventID'][old]])
                old_x = np.column_stack([z[k][old_order] for k in names]).astype('float32')
                old_x[~np.isfinite(old_x)] = np.nan
                np.testing.assert_array_equal(x[old,:len(names)], old_x)
            verification = dict(old_selected_N=int(old.sum()), old_identity_and_46_features_exact=True)
        md = dict(index=index, row=row, input=str(input_path), raw_N=raw_N, selected_N=len(order),
                  new_selection_N=int((~old).sum()), reco_p50_100_N=int(((data['reco_p_GeV']>=50)&(data['reco_p_GeV']<100)).sum()),
                  truth_E50_100_N=int(((data['truth_E_GeV']>=50)&(data['truth_E_GeV']<100)).sum()),
                  features=names+extra, cutflow_passed=cutflow['passed'].tolist(), cutflow_names=cutflow['cut_name'].astype(str).tolist(),
                  wall_s=time.perf_counter()-tick, cpu_s=time.process_time()-cpu,
                  peak_parent_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                  peak_analysis_rss_MiB=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss/1024,
                  uproot_requested_bytes=requested, analysis_requested_bytes='not instrumented', smoke=smoke, **verification)
        output.parent.mkdir(parents=True,exist_ok=True)
        assert not output.exists(), 'Refuse to overwrite successful extraction'
        np.savez_compressed(output, **data, metadata_json=np.array(json.dumps(md)))
        with np.load(output) as saved:
            for k,v in data.items(): np.testing.assert_array_equal(saved[k],v)
        print(json.dumps(md),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--index',type=int,required=True);p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--smoke',action='store_true')
    a=p.parse_args();extract(a.index,a.input,a.output,a.smoke)
