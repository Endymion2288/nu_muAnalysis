#!/usr/bin/env python3
"""Package bounded CC controls; no models or large source checkout are transferred."""
import json
import shutil
import tarfile
from pathlib import Path

repo=Path(__file__).resolve().parents[1]
cfg=json.loads((repo/'ml/configs/calonu_cc_waveform.json').read_text())
paths=['setup_env.sh','ml/locate_calonu_native.py','ml/read_calonu_native.py','ml/report_calonu_native.py',
       'ml/configs/calonu_cc_waveform.json','workbook/stage37_energy_ml/conditions_audit.json',
       'workbook/stage36_energy_ml/geometry_audit.json']
paths += [f'workbook/stage39_energy_ml/request_{i}.json' for i in cfg['indices']]
target=repo/'software/energy-ml-calonu-cc-waveform-stage39.tar.gz'
with tarfile.open(target,'w:gz') as tar:
    for p in paths:tar.add(repo/p,arcname=p)
spool=Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage39');(spool/'logs').mkdir(parents=True,exist_ok=True)
shutil.copy2(repo/'AnalysisZipFramework/submission/run_ml_calonu_cc_waveform.sh',spool)
(spool/'run_ml_calonu_cc_waveform.sh').chmod(0o755)
(repo/'ntuples/energy_ml_stage39/shards').mkdir(parents=True,exist_ok=True)
print(dict(payload=str(target),bytes=target.stat().st_size))
