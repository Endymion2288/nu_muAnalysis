#!/usr/bin/env python3
"""Freeze the master-integration pilot or full sample into an AFS batch submission."""
import argparse
from pathlib import Path
import shutil
import tarfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', required=True)
    parser.add_argument('--indices', nargs='*', type=int)
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--nevents', type=int, default=1000)
    parser.add_argument('--skip', type=int, default=0)
    parser.add_argument('--paired-old', action='store_true', help='Replay old on the same worker for a timing and cache control')
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    submit = Path.home() / 'condor/nu_muAnalysis/stage208_master_integration' / args.name
    submit.mkdir(parents=True, exist_ok=True)
    output = repo / 'ntuples/tracking_master_stage208' / args.name
    output.mkdir(parents=True, exist_ok=True)
    inputs = [r.split('\t') for r in (repo / 'workbook/stage201_tracking/input_manifest.tsv').read_text().splitlines()]
    indices = list(range(len(inputs))) if args.all else args.indices if args.indices is not None else [0]
    rows = []
    for index in indices:
        if index == 291:
            continue  # Same common population as the validated old/strict comparison.
        # A historical maker crash in this file is isolated with nonoverlapping slices.
        pieces = range(10) if index == 53 and args.nevents == -1 else [0]
        for piece in pieces:
            nevents = 1000 if len(pieces) > 1 else args.nevents
            skip = piece * 1000 if len(pieces) > 1 else args.skip
            result = str(output / f'latest_{index:03d}_{skip:05d}.npz').replace('/eos/home-x/xcheng/', '/eos/user/x/xcheng/')
            rows.append([index, 'new', inputs[index][3], nevents, skip, result])
    (submit / 'manifest.tsv').write_text(''.join('\t'.join(map(str, r)) + '\n' for r in rows))
    scripts = ['run_tracking_master_integration', 'run_tracking_station', 'run_tracking_georotation',
               'extract_tracking_station', 'compare_tracking']
    names = ['setup_env.sh', 'AnalysisZipFramework/config/cuts.yaml', 'AnalysisZipFramework/config/definitions.yaml',
             'AnalysisZipFramework/include/RDFDefines.h', 'AnalysisZipFramework/include/TrackingStationDiagnostic.h',
             'AnalysisZipFramework/include/TrackingDuplicateDiagnostic.h', 'AnalysisZipFramework/include/TrackingTruthDiagnostic.h']
    names += [f'AnalysisZipFramework/scripts/{name}.py' for name in scripts]
    with tarfile.open(submit / 'code.tar.gz', 'w:gz') as archive:
        for name in names:
            archive.add(repo / name, arcname=name)
        archive.add(repo / 'software/stage205_material/material-manual-rowmajor.json.gz', arcname='material-strict-reference.json.gz')
        archive.add(repo / 'workbook/stage208_master_integration/software_provenance.json', arcname='software_provenance.json')
    shutil.copyfile(repo / 'AnalysisZipFramework/submission/run_tracking_master_integration.sh', submit / 'worker.sh')
    (submit / 'worker.sh').chmod(0o755)
    (submit / 'jobs.sub').write_text(f'''universe = vanilla
initialdir = {submit}
executable = {submit}/worker.sh
arguments = $(index) $(rdo) $(nevents) $(skip) $(result) {int(args.paired_old)}
transfer_input_files = {submit}/code.tar.gz
should_transfer_files = YES
transfer_output_files = ""
when_to_transfer_output = ON_EXIT
request_cpus = 1
request_memory = 3500MB
request_disk = 7000MB
getenv = False
+JobFlavour = "{'workday' if args.nevents == -1 else 'microcentury'}"
+NuMuStage = "stage208_master_integration"
log = {submit}/events.log
output = {submit}/$(ClusterId).$(ProcId).out
error = {submit}/$(ClusterId).$(ProcId).err
queue index,version,rdo,nevents,skip,result from {submit}/manifest.tsv
''')
    print(submit / 'jobs.sub')


if __name__ == '__main__':
    main()
