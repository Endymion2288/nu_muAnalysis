#!/usr/bin/env python3
"""Ship one frozen scalar cache to one CPU training job with fifteen fixed fits."""
import tarfile
from pathlib import Path
repo=Path(__file__).resolve().parents[1]
assert (repo/'workbook/stage55_energy_ml/dataset_summary.json').exists()
paths=['ml/train_low_energy.py','ml/configs/low_energy.json','ntuples/energy_ml_stage55/dataset.npz']
archive=repo/'software/energy-ml-low-energy-train-stage55.tar.gz'
with tarfile.open(archive,'w:gz',compresslevel=1) as tar:
 for p in paths:tar.add(repo/p,arcname=p)
worker=(repo/'AnalysisZipFramework/submission/run_ml_low_energy_train.sh').read_bytes()
worker_path=Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage55/train_v1.sh')
if worker_path.exists():
 assert worker_path.read_bytes()==worker,'Use a new immutable worker version for changed code'
else:worker_path.write_bytes(worker)
print(archive,archive.stat().st_size)
