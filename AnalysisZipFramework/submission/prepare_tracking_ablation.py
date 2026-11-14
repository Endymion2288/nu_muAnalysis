#!/usr/bin/env python3
"""Freeze GENIE station-response controls in stage204, using existing reconstruction builds."""
import argparse
import csv
import gzip
import io
import json
from pathlib import Path
import shutil
import sys
import tarfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from run_tracking_ablation import VARIANTS


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--name', required=True)
    p.add_argument('--stage', default='stage204_causal')
    p.add_argument('--material-map', type=Path)
    p.add_argument('--all-inputs', action='store_true')
    p.add_argument('--chunk-size', type=int, default=5000)
    p.add_argument('--indices', type=int, nargs='+', default=[53])
    p.add_argument('--variants', nargs='+', choices=['old'] + list(VARIANTS), default=['old'] + list(VARIANTS))
    p.add_argument('--nevents', type=int, default=1000)
    p.add_argument('--skip', type=int, default=0)
    p.add_argument('--audit', action='store_true', help='Selected CKF/refit states; compact reduction before uploading')
    p.add_argument('--waveform', action='store_true', help='Keep official waveform fit/status branches for targeted diagnosis')
    args = p.parse_args()
    repo = Path(__file__).resolve().parents[2]
    submit = Path.home() / 'condor/nu_muAnalysis' / args.stage / args.name
    output_name = 'tracking_ablation_stage204' if args.stage == 'stage204_causal' else 'tracking_ablation_' + args.stage.removeprefix('stage')
    output = repo / 'ntuples' / output_name / args.name
    submit.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    manifest = [r.split('\t') for r in (repo / 'workbook/stage201_tracking/input_manifest.tsv').read_text().splitlines()]
    rows = []
    ranges = [(i, args.skip, args.nevents) for i in args.indices]
    if args.all_inputs:
        totals = {}
        with (repo / 'workbook/stage203_station_truth/files.tsv').open() as source:
            for row in csv.DictReader(source, delimiter='\t'):
                if row['version'] == 'old':
                    i = int(row['index'])
                    totals[i] = totals.get(i, 0) + int(row['events'])
        assert len(totals) == 342 and sum(totals.values()) == 3374987
        ranges = [(i, start, min(size, total-start)) for i, total in sorted(totals.items())
                  for size in [1000 if i in (53, 80) else args.chunk_size] for start in range(0, total, size)]
    for i, skip, nevents in ranges:
        assert i != 291
        for variant in args.variants:
            result = str(output / f'{variant}_{i:03d}_{skip:05d}.npz').replace('/eos/home-x/xcheng/', '/eos/user/x/xcheng/')
            rows.append([i, variant, manifest[i][3], nevents, skip, result])
    (submit / 'manifest.tsv').write_text(''.join('\t'.join(map(str, r)) + '\n' for r in rows))
    scripts = ['run_tracking_ablation', 'run_tracking_station', 'run_tracking_georotation', 'extract_tracking_station', 'compare_tracking', 'extract_tracking_ablation_audit', 'extract_tracking_waveform']
    files = ['setup_env.sh', 'AnalysisZipFramework/config/cuts.yaml', 'AnalysisZipFramework/config/definitions.yaml']
    files += [f'AnalysisZipFramework/include/{s}.h' for s in ['RDFDefines', 'TrackingStationDiagnostic', 'TrackingDuplicateDiagnostic', 'TrackingTruthDiagnostic']]
    files += [f'AnalysisZipFramework/scripts/{s}.py' for s in scripts]
    with tarfile.open(submit / 'tracking-station-code.tar.gz', 'w:gz') as tar:
        for name in files:
            tar.add(repo / name, arcname=name)
        material = args.material_map or repo / 'software/stage204_causal/material-rotated.json'
        payload = gzip.decompress(material.read_bytes()) if material.suffix == '.gz' else material.read_bytes()
        info = tarfile.TarInfo('material-rotated.json'); info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))
    shutil.copyfile(repo / 'AnalysisZipFramework/submission/run_tracking_ablation.sh', submit / 'worker.sh')
    if args.audit:
        worker = submit / 'worker.sh'
        worker.write_text(worker.read_text().replace('set -eo pipefail', 'set -eo pipefail\nexport TRACKING_ABLATION_AUDIT=1'))
    if args.waveform:
        worker = submit / 'worker.sh'
        worker.write_text(worker.read_text().replace('set -eo pipefail', 'set -eo pipefail\nexport TRACKING_ABLATION_WAVEFORM=1'))
    (submit / 'worker.sh').chmod(0o755)
    (submit / 'preparation.json').write_text(json.dumps(vars(args), indent=2, default=str) + '\n')
    (submit / 'jobs.sub').write_text(f'''universe = vanilla
initialdir = {submit}
executable = {submit}/worker.sh
arguments = $(index) $(variant) $(rdo) $(nevents) $(skip) $(result)
transfer_input_files = {submit}/tracking-station-code.tar.gz
should_transfer_files = YES
transfer_output_files = ""
when_to_transfer_output = ON_EXIT
request_cpus = 1
request_memory = 3000MB
request_disk = 6500MB
getenv = False
+JobFlavour = "workday"
+NuMuStage = "{args.stage}"
log = {submit}/events.log
output = {submit}/$(ClusterId).$(ProcId).out
error = {submit}/$(ClusterId).$(ProcId).err
queue index,variant,rdo,nevents,skip,result from {submit}/manifest.tsv
''')
    print(submit / 'jobs.sub')


if __name__ == '__main__':
    main()
