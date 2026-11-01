#!/usr/bin/env python3
"""Minimal immutable payload; excludes old tests and large detector files."""
import argparse
import json
import shutil
import subprocess
import tarfile
from pathlib import Path

p = argparse.ArgumentParser(); p.add_argument('--part', choices=['extract', 'train'], required=True); a = p.parse_args()
repo = Path(__file__).resolve().parents[1]; out = repo/'workbook/stage43_energy_ml'
paths = ['ml/calonu_data_noise.py', 'ml/run_calonu_data_noise.py', 'ml/run_calonu_information.py',
         'ml/information_gap.py', 'ml/train_bdt.py', 'ml/calonu_weak_readout.py', 'ml/report_calonu_native.py',
         'ml/configs/calonu_data_noise.json', 'workbook/stage43_energy_ml/raw_manifest.json']
if a.part == 'train': paths += ['ntuples/energy_ml_stage42/development.npz', 'ntuples/energy_ml_stage43/response.npz']
payload = repo/'software/energy-ml-calonu-data-noise-stage43.tar.gz'
with tarfile.open(payload, 'w:gz') as tar:
    for path in paths: tar.add(repo/path, arcname=path)
    if a.part == 'extract': tar.add('/tmp/xcheng/read_calonu_raw_noise', arcname='ml/calonu_raw_reader')
spool = Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage43'); (spool/'logs').mkdir(parents=True, exist_ok=True)
shutil.copy2(repo/'AnalysisZipFramework/submission/run_ml_calonu_data_noise.sh', spool)
(spool/'run_ml_calonu_data_noise.sh').chmod(0o755)
(spool/f'{a.part}.jobs').write_text(a.part+'\n')
for f in range(3): (repo/f'ml/artifacts/stage43/formal/{f}').mkdir(parents=True, exist_ok=True)
record = dict(part=a.part, payload=str(payload), bytes=payload.stat().st_size, paths=paths,
              reader_headers='official Calypso d32b0ff3 installed EventFormats and Exceptions; Logging include from source',
              reader_compiler=subprocess.check_output(['readelf', '-p', '.comment', '/tmp/xcheng/read_calonu_raw_noise'], text=True).strip(),
              packager_compiler=subprocess.check_output(['g++', '--version'], text=True).splitlines()[0])
(out/f'{a.part}_payload.json').write_text(json.dumps(record, indent=2)+'\n'); print(json.dumps(record))
