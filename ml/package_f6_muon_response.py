#!/usr/bin/env python3
"""Package a minimal six-job full-range muon response extraction."""
import json
import shutil
import tarfile
from pathlib import Path

repo=Path(__file__).resolve().parents[1]
paths=['ml/read_f6_muon_response.py','ml/calonu_muon_control.py','ml/configs/f6_muon_response.json',
       'ml/configs/calonu_muon_files.tsv','ml/configs/calonu_muon_grl.json']
payload=repo/'software/energy-ml-f6-muon-response-stage52.tar.gz'
assert not (repo/'ntuples/energy_ml_stage52/source_histograms.tar.gz').exists(), 'Stage52 extraction already complete'
assert not any((repo/'ntuples/energy_ml_stage52/shards').glob('*.npz'))
with tarfile.open(payload,'w:gz') as tar:
    for path in paths:tar.add(repo/path,arcname=path)
spool=Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage52');(spool/'logs').mkdir(parents=True,exist_ok=True)
shutil.copy2(repo/'AnalysisZipFramework/submission/run_ml_f6_muon_response.sh',spool)
(spool/'run_ml_f6_muon_response.sh').chmod(0o755)
(repo/'ntuples/energy_ml_stage52/shards').mkdir(parents=True,exist_ok=True)
print(json.dumps(dict(payload=str(payload),bytes=payload.stat().st_size,jobs=6,files=18)))
