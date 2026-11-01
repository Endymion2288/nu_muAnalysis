#!/usr/bin/env python3
"""Package bounded reader and immutable requests; reuse the existing read-only runtime."""
import shutil
import tarfile
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
paths = ['setup_env.sh', 'ml/locate_calonu_native.py', 'ml/read_calonu_native.py',
         'ml/configs/calonu_native_control.json']
paths += [f'workbook/stage37_energy_ml/request_{index}.json' for index in [0, 5, 6, 11]]
target = repo/'software/energy-ml-calonu-native-stage37.tar.gz'
with tarfile.open(target, 'w:gz') as tar:
    for name in paths:
        tar.add(repo/name, arcname=name)
spool = Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage37')
(spool/'logs').mkdir(parents=True, exist_ok=True)
shutil.copy2(repo/'AnalysisZipFramework/submission/run_ml_calonu_native.sh', spool)
(spool/'run_ml_calonu_native.sh').chmod(0o755)
(repo/'ntuples/energy_ml_stage37/shards').mkdir(parents=True, exist_ok=True)
print(dict(payload=str(target), bytes=target.stat().st_size))
