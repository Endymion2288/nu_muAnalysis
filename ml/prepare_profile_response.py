#!/usr/bin/env python3
"""Build and byte-check the compact stage25 Condor payload."""
import json
import tarfile
from pathlib import Path

from profile_response import config


def main():
    root = Path(__file__).resolve().parents[1]; cfg = config(root)
    paths = ['ml/closure.py', 'ml/within_response.py', 'ml/profile_response.py', 'ml/run_profile_response.py',
             'ml/configs/closure.yaml', 'ml/configs/within_response.yaml', 'ml/configs/profile_response.yaml',
             'workbook/stage23_energy_ml/folds.tsv', 'ntuples/energy_ml_stage12/dataset/validation.npz']
    paths += [s['path'] for s in cfg['models'].values() if 'path' in s]
    payload = root / 'software/energy-ml-profile-stage25.tar.gz'
    with tarfile.open(payload, 'w:gz') as tar:
        for name in paths: tar.add(root / name, arcname=name)
    with tarfile.open(payload, 'r:gz') as tar:
        for name in paths: assert tar.extractfile(name).read() == (root / name).read_bytes()
    print(json.dumps(dict(payload=str(payload), bytes=payload.stat().st_size, files=paths, byte_verified=True)))


if __name__ == '__main__': main()
