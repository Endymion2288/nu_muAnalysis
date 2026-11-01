#!/usr/bin/env python3
"""The stage35 training payload contains fit/stop only, never calibration/test."""
import argparse
import shutil
import tarfile
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--action', choices=['extract', 'train'], required=True)
    p.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    a = p.parse_args()
    paths = [f'ml/{name}.py' for name in ['calonu_inputs', 'calonu_ablation', 'frozen_evaluation', 'track_response', 'train_bdt']]
    paths += [f'ml/configs/{name}' for name in ['calonu_ablation.yaml', 'calonu_files.tsv', 'baseline.yaml', 'track_response.yaml']]
    if a.action == 'train':
        paths += [f'ntuples/energy_ml_stage35/{part}.npz' for part in ['fit', 'stop']]
    path = a.repo / f'software/energy-ml-calonu-stage35-{a.action}.tar.gz'
    with tarfile.open(path, 'w:gz') as archive:
        for name in paths:
            archive.add(a.repo / name, arcname=name)
    spool = Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage35')
    (spool / 'logs').mkdir(parents=True, exist_ok=True)
    wrapper = spool / 'run_ml_calonu.sh'
    shutil.copy2(a.repo / 'AnalysisZipFramework/submission' / wrapper.name, wrapper)
    wrapper.chmod(0o755)
    (a.repo / 'ntuples/energy_ml_stage35/shards').mkdir(parents=True, exist_ok=True)
    for i in range(3):
        (a.repo / f'ml/artifacts/stage35/seed_{i}').mkdir(parents=True, exist_ok=True)
        (a.repo / f'workbook/stage35_energy_ml/seed_{i}').mkdir(parents=True, exist_ok=True)
    print(dict(action=a.action, payload=str(path), bytes=path.stat().st_size))


if __name__ == '__main__':
    main()
