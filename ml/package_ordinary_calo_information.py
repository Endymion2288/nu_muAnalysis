#!/usr/bin/env python3
"""Separate immutable extraction/training payloads; no held-out samples."""
import argparse
import json
import shutil
import tarfile
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('--mode',choices=['hits','train'],required=True);a=p.parse_args()
r=Path(__file__).resolve().parents[1];cfg=json.loads((r/'ml/configs/ordinary_calo_information.json').read_text())
out=r/f'software/energy-ml-ordinary-calo-stage47-{a.mode}.tar.gz'
paths=['setup_env.sh','ml/read_ordinary_calo_sensitive.py','ml/locate_calonu_native.py',
       'ml/configs/ordinary_calo_information.json','ntuples/energy_ml_stage42/requests.tar.gz']
if a.mode=='train':
    paths += [str(p.relative_to(r)) for p in sorted((r/'ml').glob('*.py'))]
    paths += ['ntuples/energy_ml_stage42/development.npz','ntuples/energy_ml_stage44/features.npz','ntuples/energy_ml_stage47/sensitive.npz']
with tarfile.open(out,'w:gz') as t:
    for path in dict.fromkeys(paths):t.add(r/path,arcname=path)
spool=Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage47');(spool/'logs').mkdir(parents=True,exist_ok=True)
shutil.copy2(r/'AnalysisZipFramework/submission/run_ml_ordinary_calo_information.sh',spool)
(spool/f'{a.mode}.jobs').write_text('train all\n' if a.mode=='train' else ''.join(f'hits {i}\n' for i in cfg['indices']))
print(json.dumps(dict(payload=str(out),bytes=out.stat().st_size,mode=a.mode,jobs=1 if a.mode=='train' else len(cfg['indices']))))
