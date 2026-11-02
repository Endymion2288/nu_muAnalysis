#!/usr/bin/env python3
"""Publish immutable input archives and workers, separately for each phase."""
import argparse
import tarfile
from pathlib import Path

from audited_features import REPO

p=argparse.ArgumentParser();p.add_argument('--phase',choices=['read','train'],required=True);a=p.parse_args()
paths=['ml/audited_features.py','ml/read_audited_features.py','ml/configs/audited_features.json',
       'ml/configs/low_energy_files.tsv','ml/configs/files.tsv','ntuples/energy_ml_stage55/dataset.npz']
if a.phase=='train':
    paths+=['ml/train_audited_features.py','ntuples/energy_ml_stage56/readout.npz']
spool=Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage56');(spool/'logs').mkdir(parents=True,exist_ok=True)
worker=(REPO/'AnalysisZipFramework/submission/run_ml_feature_audit.sh').read_bytes();dest=spool/'worker_v1.sh'
if dest.exists():assert dest.read_bytes()==worker,'Publish changed workers under a new version'
else:dest.write_bytes(worker)
(spool/'read.txt').write_text(''.join(str(i)+'\n' for i in range(6)))
(spool/'train.txt').write_text('0\n')
archive=REPO/'software/energy-ml-feature-audit-stage56.tar.gz'
# Do not replace a transport archive while a read job may still fetch it.
if archive.exists():raise RuntimeError('Remove a completed phase archive explicitly before packaging next phase')
with tarfile.open(archive,'w:gz',compresslevel=1) as tar:
    for path in paths:tar.add(REPO/path,arcname=path)
print(archive,archive.stat().st_size)
