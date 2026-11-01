#!/usr/bin/env python3
import json,tarfile
from pathlib import Path
from mc_bootstrap import config

def main():
    root=Path(__file__).resolve().parents[1];cfg=config(root)
    paths=['ml/closure.py','ml/within_response.py','ml/profile_response.py','ml/independent_response.py','ml/mc_bootstrap.py','ml/run_mc_bootstrap.py','ml/configs/closure.yaml','ml/configs/within_response.yaml','ml/configs/profile_response.yaml','ml/configs/independent_response.yaml','ml/configs/mc_bootstrap.yaml','workbook/stage23_energy_ml/folds.tsv','ntuples/energy_ml_stage12/dataset/validation.npz']
    paths += [s['path'] for s in cfg['models'].values() if 'path' in s]
    payload=root/'software/energy-ml-mc-bootstrap-stage28.tar.gz'
    with tarfile.open(payload,'w:gz') as tar:
        for name in paths:tar.add(root/name,arcname=name)
    with tarfile.open(payload,'r:gz') as tar:
        for name in paths:assert tar.extractfile(name).read()==(root/name).read_bytes()
    print(json.dumps(dict(payload=str(payload),bytes=payload.stat().st_size,members=paths,byte_verified=True)))
if __name__=='__main__':main()
