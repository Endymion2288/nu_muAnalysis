#!/usr/bin/env python3
"""Package the reader and existing frozen sample, without reading physics inputs."""
import argparse
import json
import tarfile
from pathlib import Path


parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--sample',type=Path,default=Path('ntuples/energy_ml_stage85/sample.json'))
parser.add_argument('--output',type=Path,default=Path('software/energy-ml-tracker-readout-stage85.tar.gz'))
args=parser.parse_args()
sample=json.loads(args.sample.read_text())
assert len(sample['sources'])==18
assert [sum(len(s['cases']) for s in sample['sources'] if s['sample']==kind)
        for kind in ['MC','data']]==[2048,2048]
assert sum(len(s['native_files']) for s in sample['sources'])==312
repo=Path(__file__).resolve().parents[1]
args.output.parent.mkdir(parents=True,exist_ok=True)
with tarfile.open(args.output,'w:gz') as archive:
    for name in ['setup_env.sh','ml/read_tracker_readout.py','ml/tracker_readout_control.h']:
        archive.add(repo/name,arcname=name)
    archive.add(args.sample,arcname='sample.json')
print(f'payload={args.output} bytes={args.output.stat().st_size}; zero ROOT reads/fits')
