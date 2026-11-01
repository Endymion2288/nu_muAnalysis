#!/usr/bin/env python3
"""Temporary stage48 payloads, only frozen development identities and old models."""
import argparse
import json
import shutil
import tarfile
from pathlib import Path
from source_transfer import REPO,configuration

p=argparse.ArgumentParser();p.add_argument('--mode',choices=['extract','infer'],required=True);a=p.parse_args()
paths=['ml/source_transfer.py','ml/configs/source_transfer.json']
if a.mode=='extract':
    paths+=['ml/read_source_transfer_features.py','ml/run_source_transfer_batch.py','ml/local_activity.py',
            'ml/calonu_inputs.py','ml/track_response.py','ml/configs/local_activity.json','ml/configs/calonu_files.tsv',
            'ntuples/energy_ml_stage48/selection.npz']
else:
    paths+=['ml/infer_source_transfer.py','ntuples/energy_ml_stage48/selection.npz','ntuples/energy_ml_stage48/features.npz',
            'ntuples/energy_ml_stage48/original_maps.joblib','ntuples/energy_ml_stage42/development.npz']
    paths+=[f'ml/artifacts/stage{s}/formal/{f}/{name}.ubj' for f in range(3) for s,name in [(44,'local'),(45,'oracle_z')]]
out=REPO/f'software/energy-ml-source-transfer-stage48-{a.mode}.tar.gz'
with tarfile.open(out,'w:gz') as t:
    for path in paths:t.add(REPO/path,arcname=path)
spool=Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage48');(spool/'logs').mkdir(parents=True,exist_ok=True)
shutil.copy2(REPO/'AnalysisZipFramework/submission/run_ml_source_transfer.sh',spool)
(spool/f'{a.mode}.jobs').write_text(''.join(f'extract {i}\n' for i in range(6)) if a.mode=='extract' else 'infer all\n')
print(json.dumps(dict(mode=a.mode,payload=str(out),bytes=out.stat().st_size,jobs=6 if a.mode=='extract' else 1)))
