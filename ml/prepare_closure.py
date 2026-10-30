#!/usr/bin/env python3
"""Build and byte-check the compact stage23 Condor payload from frozen inputs."""
import json
import tarfile
from pathlib import Path

import yaml


def main():
    root = Path(__file__).resolve().parents[1]
    cfg = yaml.safe_load((root / 'ml/configs/closure.yaml').read_text())
    paths = ['ml/closure.py', 'ml/run_closure.py', 'ml/configs/closure.yaml',
             'workbook/stage23_energy_ml/folds.tsv', 'ntuples/energy_ml_stage12/dataset/validation.npz']
    paths += [spec['path'] for spec in cfg['models'].values() if 'path' in spec]
    payload = root / 'software/energy-ml-closure-stage23.tar.gz'
    with tarfile.open(payload, 'w:gz') as tar:
        for name in paths:
            tar.add(root / name, arcname=name)
    with tarfile.open(payload, 'r:gz') as tar:
        for name in paths:
            assert tar.extractfile(name).read() == (root / name).read_bytes()
    print(json.dumps(dict(payload=str(payload), bytes=payload.stat().st_size, files=paths, byte_verified=True)))


if __name__ == '__main__':
    main()
