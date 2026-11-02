#!/usr/bin/env python3
"""Package the frozen tracker mechanism experiment without detector-file copies."""
import argparse
import io
import json
import shutil
import tarfile
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--part', choices=['prepare', 'replay'], required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
spool = Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage53')
(spool/'logs').mkdir(parents=True, exist_ok=True)
if args.part == 'prepare':
    paths = ['ml/prepare_tracker_noise.py', 'ml/read_f6_muon_response.py',
             'ml/calonu_muon_control.py', 'ml/configs/f6_muon_response.json',
             'ml/configs/calonu_muon_files.tsv', 'ml/configs/calonu_muon_grl.json']
    payload = repo/'software/energy-ml-tracker-noise-prepare-stage53.tar.gz'
    runner = 'run_ml_tracker_noise_prepare.sh'
    target = 'prepare.sh'
else:
    paths = ['setup_env.sh', 'ml/replay_tracker_noise.py',
             'ml/build_tracker_noise_helper.py', 'ml/tracker_noise_summary.h']
    payload = repo/'software/energy-ml-tracker-noise-stage53.tar.gz'
    runner = target = 'run_ml_tracker_noise.sh'
with tarfile.open(payload, 'w:gz') as archive:
    for path in paths:
        archive.add(repo/path, arcname=path)
    if args.part == 'replay':
        sample = repo/'ntuples/energy_ml_stage53/sample.json'
        if sample.is_file():
            archive.add(sample, arcname='sample.json')
        else:
            with tarfile.open(sample.parent/'replay_results.tar.gz') as results:
                data = results.extractfile('sample.json').read()
            info = tarfile.TarInfo('sample.json'); info.size = len(data)
            archive.addfile(info,io.BytesIO(data))
        header = repo.parent/'calypso/Tracker/TrackerEventCnv/TrackerEventAthenaPool/src/FaserSCT3_RawDataCnv_p4.h'
        archive.add(header, arcname=header.name)
shutil.copy2(repo/'AnalysisZipFramework/submission'/runner, spool/target)
(spool/target).chmod(0o755)
print(json.dumps(dict(part=args.part, payload=str(payload), bytes=payload.stat().st_size)))
