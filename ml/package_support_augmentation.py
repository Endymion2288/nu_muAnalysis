#!/usr/bin/env python3
"""Publish the already frozen stage71 code and one compact scalar cache."""
import tarfile
from pathlib import Path
from support_augmentation import REPO, OUT, save

p=REPO/'software/energy-ml-support-augmentation-stage71.tar.gz'
assert (OUT/'protocol.json').exists() and not p.exists()
paths=['ml/support_augmentation.py','ml/fit_support_augmentation.py','ntuples/energy_ml_stage71/input.npz','workbook/stage71_energy_ml/protocol.json']
with tarfile.open(p,'w:gz',compresslevel=1) as tar:
    for path in paths:tar.add(REPO/path,arcname=path)
spool=Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage71');(spool/'logs').mkdir(parents=True,exist_ok=True)
worker=spool/'worker_v1.sh';assert not worker.exists()
worker.write_bytes((REPO/'AnalysisZipFramework/submission/run_ml_support_augmentation.sh').read_bytes())
save(OUT/'package.json',dict(paths=paths,payload_bytes=p.stat().st_size,event_inputs='one prepared scalar cache; no ROOT/RDO',new_F7_inference=0))
print(p,p.stat().st_size)
