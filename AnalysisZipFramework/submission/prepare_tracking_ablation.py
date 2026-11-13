#!/usr/bin/env python3
"""Freeze GENIE station-response controls in stage204, using existing reconstruction builds."""
import argparse
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
    p.add_argument('--indices', type=int, nargs='+', default=[53])
    p.add_argument('--variants', nargs='+', choices=['old'] + list(VARIANTS), default=['old'] + list(VARIANTS))
    p.add_argument('--nevents', type=int, default=1000)
    p.add_argument('--skip', type=int, default=0)
    p.add_argument('--audit', action='store_true', help='Selected CKF/refit states; compact reduction before uploading')
    p.add_argument('--waveform', action='store_true', help='Keep official waveform fit/status branches for targeted diagnosis')
    args = p.parse_args()
    repo = Path(__file__).resolve().parents[2]
    submit = Path.home() / 'condor/nu_muAnalysis/stage204_causal' / args.name
    output = repo / 'ntuples/tracking_ablation_stage204' / args.name
    submit.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    manifest = [r.split('\t') for r in (repo / 'workbook/stage201_tracking/input_manifest.tsv').read_text().splitlines()]
    rows = []
    for i in args.indices:
        assert i != 291
        for variant in args.variants:
            result = str(output / f'{variant}_{i:03d}_{args.skip:05d}.npz').replace('/eos/home-x/xcheng/', '/eos/user/x/xcheng/')
            rows.append([i, variant, manifest[i][3], args.nevents, args.skip, result])
    (submit / 'manifest.tsv').write_text(''.join('\t'.join(map(str, r)) + '\n' for r in rows))
    scripts = ['run_tracking_ablation', 'run_tracking_station', 'run_tracking_georotation', 'extract_tracking_station', 'compare_tracking', 'extract_tracking_ablation_audit', 'extract_tracking_waveform']
    files = ['setup_env.sh', 'AnalysisZipFramework/config/cuts.yaml', 'AnalysisZipFramework/config/definitions.yaml']
    files += [f'AnalysisZipFramework/include/{s}.h' for s in ['RDFDefines', 'TrackingStationDiagnostic', 'TrackingDuplicateDiagnostic', 'TrackingTruthDiagnostic']]
    files += [f'AnalysisZipFramework/scripts/{s}.py' for s in scripts]
    with tarfile.open(submit / 'tracking-station-code.tar.gz', 'w:gz') as tar:
        for name in files:
            tar.add(repo / name, arcname=name)
        tar.add(repo / 'software/stage204_causal/material-rotated.json', arcname='material-rotated.json')
    shutil.copyfile(repo / 'AnalysisZipFramework/submission/run_tracking_ablation.sh', submit / 'worker.sh')
    if args.audit:
        worker = submit / 'worker.sh'
        worker.write_text(worker.read_text().replace('set -eo pipefail', 'set -eo pipefail\nexport TRACKING_ABLATION_AUDIT=1'))
    if args.waveform:
        worker = submit / 'worker.sh'
        worker.write_text(worker.read_text().replace('set -eo pipefail', 'set -eo pipefail\nexport TRACKING_ABLATION_WAVEFORM=1'))
    (submit / 'worker.sh').chmod(0o755)
    (submit / 'preparation.json').write_text(json.dumps(vars(args), indent=2) + '\n')
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
+NuMuStage = "stage204_causal"
log = {submit}/events.log
output = {submit}/$(ClusterId).$(ProcId).out
error = {submit}/$(ClusterId).$(ProcId).err
queue index,variant,rdo,nevents,skip,result from {submit}/manifest.tsv
''')
    print(submit / 'jobs.sub')


if __name__ == '__main__':
    main()
