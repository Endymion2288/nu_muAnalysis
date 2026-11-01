#!/usr/bin/env python3
"""Package frozen response controls with exact source fixture and compact conditions."""
import json
import shutil
import tarfile
from pathlib import Path
repo=Path(__file__).resolve().parents[1]
cfg=json.loads((repo/'ml/configs/calonu_response.json').read_text())
paths=['setup_env.sh','ml/locate_calonu_native.py','ml/read_calonu_native.py','ml/report_calonu_native.py',
       'ml/calonu_weak_readout.py','ml/calonu_timed_readout.py','ml/run_calonu_noise_control.py',
       'ml/configs/calonu_response.json','workbook/stage40_energy_ml/source_control.cxx',
       'workbook/stage37_energy_ml/conditions_audit.json','workbook/stage36_energy_ml/geometry_audit.json']
paths += [f'workbook/stage40_energy_ml/request_{i}.json' for i in cfg['indices']]
payload=repo/'software/energy-ml-calonu-response-stage40.tar.gz'
with tarfile.open(payload,'w:gz') as tar:
    for path in paths:tar.add(repo/path,arcname=path)
spool=Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage40');(spool/'logs').mkdir(parents=True,exist_ok=True)
shutil.copy2(repo/'AnalysisZipFramework/submission/run_ml_calonu_response.sh',spool)
(spool/'run_ml_calonu_response.sh').chmod(0o755)
(repo/'ntuples/energy_ml_stage40/shards').mkdir(parents=True,exist_ok=True)
print(json.dumps(dict(payload=str(payload),bytes=payload.stat().st_size)))
