#!/usr/bin/env python3
"""Prepare and byte-verify the small stage26 Condor source/input payload."""
import argparse
import json
import tarfile
from pathlib import Path

from source_response import config


def main():
    parser = argparse.ArgumentParser(__doc__); parser.add_argument('--extension', action='store_true'); args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]; cfg = config(root)
    paths = ['ml/closure.py', 'ml/within_response.py', 'ml/profile_response.py', 'ml/source_response.py',
             'ml/run_source_response.py', 'ml/configs/closure.yaml', 'ml/configs/within_response.yaml',
             'ml/configs/profile_response.yaml', 'ml/configs/source_response.yaml',
             'workbook/stage23_energy_ml/folds.tsv', 'ntuples/energy_ml_stage12/dataset/validation.npz']
    paths += [s['path'] for s in cfg['models'].values() if 'path' in s]
    if args.extension: paths.append('ml/extend_source_response.py')
    payload = root / ('software/energy-ml-source-extension-stage26.tar.gz' if args.extension else 'software/energy-ml-source-stage26.tar.gz')
    with tarfile.open(payload, 'w:gz') as tar:
        for name in paths: tar.add(root / name, arcname=name)
    with tarfile.open(payload, 'r:gz') as tar:
        for name in paths: assert tar.extractfile(name).read() == (root / name).read_bytes()
    print(json.dumps(dict(payload=str(payload), bytes=payload.stat().st_size, members=paths, byte_verified=True)))


if __name__ == '__main__': main()
