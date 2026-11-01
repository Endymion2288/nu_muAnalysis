#!/usr/bin/env python3
"""Small immutable stage42 job payload, excluding old held-out samples."""
import argparse
import json
import shutil
import tarfile
from pathlib import Path
p=argparse.ArgumentParser(); p.add_argument('--part',choices=['A','B','C','hits'],required=True); a=p.parse_args()
repo=Path(__file__).resolve().parents[1]; cfg=json.loads((repo/'ml/configs/calonu_information.json').read_text())
paths=['setup_env.sh','ml/read_calonu_sensitive_summary.py','ml/locate_calonu_native.py','ml/run_calonu_information.py',
       'ml/information_gap.py','ml/train_bdt.py','ml/configs/calonu_information.json',
       'workbook/stage37_energy_ml/conditions_audit.json','ntuples/energy_ml_stage42/development.npz']
paths += [f'ntuples/energy_ml_stage42/requests/request_{i}.json' for i in cfg['indices']]
if a.part in ['B','C']: paths += ['ntuples/energy_ml_stage42/sensitive.npz']
if a.part=='C': paths += ['ntuples/energy_ml_stage42/synthetic.npz']
payload=repo/'software/energy-ml-calonu-information-stage42.tar.gz'
with tarfile.open(payload,'w:gz') as tar:
    for path in paths: tar.add(repo/path,arcname=path)
spool=Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage42'); (spool/'logs').mkdir(parents=True,exist_ok=True)
shutil.copy2(repo/'AnalysisZipFramework/submission/run_ml_calonu_information.sh',spool)
(spool/'run_ml_calonu_information.sh').chmod(0o755)
indices=cfg['indices'] if a.part=='hits' else range(3)
(spool/f'{a.part}.jobs').write_text(f'{a.part} all\n' if a.part in ['B','C'] else ''.join(f'{a.part} {i}\n' for i in indices))
for i in indices:
    if a.part!='hits': (repo/f'ml/artifacts/stage42/{a.part}/{i}').mkdir(parents=True,exist_ok=True)
print(json.dumps(dict(payload=str(payload),bytes=payload.stat().st_size,part=a.part,jobs=1 if a.part in ['B','C'] else len(indices))))
