#!/usr/bin/env python3
"""Minimal extraction/training payloads, no ROOT copies or legacy models."""
import argparse
import json
import shutil
import tarfile
from pathlib import Path
from segment_information import REPO,CACHE,configuration
p=argparse.ArgumentParser();p.add_argument('--mode',choices=['extract','train'],required=True);a=p.parse_args();cfg=configuration()
paths=['ml/segment_information.py','ml/learning_capacity.py','ml/configs/segment_information.json','ntuples/energy_ml_stage42/development.npz']
if a.mode=='extract':
    paths+=['ml/read_segment_information.py','ml/local_activity.py','ml/calonu_inputs.py','ml/track_response.py','ml/configs/calonu_files.tsv','ml/configs/local_activity.json','workbook/stage42_energy_ml/preparation.json']
    (CACHE/'shards').mkdir(parents=True,exist_ok=True)
else:
    paths+=['ml/run_segment_information.py','ml/run_learning_capacity.py','ntuples/energy_ml_stage51/features.npz']
    for f in range(3):(REPO/f'ml/artifacts/stage51/formal/{f}').mkdir(parents=True,exist_ok=True)
payload=REPO/f'software/energy-ml-segment-information-stage51-{a.mode}.tar.gz';assert not payload.exists()
with tarfile.open(payload,'w:gz') as t:
    for path in paths:t.add(REPO/path,arcname=path)
spool=Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage51');(spool/'logs').mkdir(parents=True,exist_ok=True)
shutil.copy2(REPO/'AnalysisZipFramework/submission/run_ml_segment_information.sh',spool)
(spool/f'{a.mode}.jobs').write_text(''.join(f'extract {i}\n' for i in range(9)) if a.mode=='extract' else 'train all\n')
print(json.dumps(dict(payload=str(payload),bytes=payload.stat().st_size,mode=a.mode,jobs=9 if a.mode=='extract' else 1)))
