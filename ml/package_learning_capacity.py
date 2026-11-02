#!/usr/bin/env python3
"""One short Condor job; package only full development cache, config and runner."""
import json
import shutil
import tarfile
from pathlib import Path
from learning_capacity import REPO

paths=['ml/learning_capacity.py','ml/run_learning_capacity.py','ml/configs/learning_capacity.json','ntuples/energy_ml_stage42/development.npz']
payload=REPO/'software/energy-ml-learning-capacity-stage50.tar.gz'
with tarfile.open(payload,'w:gz') as t:
    for path in paths:t.add(REPO/path,arcname=path)
spool=Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage50');(spool/'logs').mkdir(parents=True,exist_ok=True)
shutil.copy2(REPO/'AnalysisZipFramework/submission/run_ml_learning_capacity.sh',spool)
for f in range(3):(REPO/f'ml/artifacts/stage50/formal/{f}').mkdir(parents=True,exist_ok=True)
print(json.dumps(dict(payload=str(payload),bytes=payload.stat().st_size,jobs=1,formal_fits=9)))
