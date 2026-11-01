#!/usr/bin/env python3
"""Small reproducible stage44 Condor payload; never packages old test samples."""
import argparse
import tarfile
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('--part',choices=['extract','train'],required=True);a=p.parse_args()
r=Path(__file__).resolve().parents[1]
out=r/'software/energy-ml-local-activity-stage44.tar.gz'
with tarfile.open(out,'w:gz') as t:
    for path in sorted((r/'ml').glob('*.py')):t.add(path,arcname=str(path.relative_to(r)))
    for path in sorted((r/'ml/configs').glob('*')):
        if path.is_file():t.add(path,arcname=str(path.relative_to(r)))
    t.add(r/'ntuples/energy_ml_stage42/development.npz',arcname='ntuples/energy_ml_stage42/development.npz')
    if a.part=='train':t.add(r/'ntuples/energy_ml_stage44/features.npz',arcname='ntuples/energy_ml_stage44/features.npz')
print(out, out.stat().st_size)
