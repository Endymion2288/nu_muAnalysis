#!/usr/bin/env python3
"""Small stage36 extraction payload; no ROOT inputs or ML model artifacts."""
import shutil
import tarfile
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
paths = ['ml/calonu_muon_control.py'] + ['ml/configs/' + f for f in ['calonu_muon_control.json', 'calonu_muon_files.tsv', 'calonu_muon_grl.json']]
path = repo / 'software/energy-ml-calonu-muon-stage36.tar.gz'
with tarfile.open(path, 'w:gz') as tar:
    for name in paths:
        tar.add(repo / name, arcname=name)
spool = Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage36')
(spool / 'logs').mkdir(parents=True, exist_ok=True)
shutil.copy2(repo / 'AnalysisZipFramework/submission/run_ml_calonu_muon.sh', spool)
(spool / 'run_ml_calonu_muon.sh').chmod(0o755)
(repo / 'ntuples/energy_ml_stage36/shards').mkdir(parents=True, exist_ok=True)
print(dict(payload=str(path), bytes=path.stat().st_size))
