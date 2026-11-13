#!/usr/bin/env python3
"""Freeze the analysis payload and prepare AFS HTCondor submission for stage201."""
import argparse
import json
from pathlib import Path
import shutil
import tarfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--name', default='production')
    parser.add_argument('--indices', type=int, nargs='*')
    parser.add_argument('--nevents', type=int, default=-1)
    parser.add_argument('--flavour', default='workday')
    args = parser.parse_args()
    repo = args.repo.resolve()
    submit = Path.home() / 'condor/nu_muAnalysis/stage201_tracking' / args.name
    submit.mkdir(parents=True, exist_ok=True)
    outputs = repo / 'ntuples/tracking_georotation_stage201' / args.name
    outputs.mkdir(parents=True, exist_ok=True)
    inputs = [line.split('\t') for line in
              (repo / 'AnalysisZipFramework/submission/merge_manifest.tsv').read_text().splitlines()]
    indices = args.indices if args.indices is not None else list(range(len(inputs)))
    manifest = []
    for i in indices:
        run, _, geom, rdo, old_merge, *_ = inputs[i]
        assert geom == 'TI12MC04'
        result = str(outputs / f'{i:03d}.npz').replace('/eos/home-x/xcheng/', '/eos/user/x/xcheng/')
        manifest.append([i, run, geom, rdo, old_merge, result])
    (submit / 'manifest.tsv').write_text(''.join('\t'.join(map(str, row))+'\n' for row in manifest))
    with tarfile.open(submit / 'tracking-georotation-code.tar.gz', 'w:gz') as archive:
        files = ['setup_env.sh', 'workbook/stage201_tracking/software_provenance.json',
                 'AnalysisZipFramework/scripts/compare_tracking.py',
                 'AnalysisZipFramework/scripts/run_tracking_georotation.py',
                 'AnalysisZipFramework/scripts/extract_tracking_georotation.py',
                 'AnalysisZipFramework/include/TrackingDuplicateDiagnostic.h',
                 'AnalysisZipFramework/include/TrackingTruthDiagnostic.h',
                 'AnalysisZipFramework/include/RDFDefines.h',
                 'AnalysisZipFramework/config/cuts.yaml', 'AnalysisZipFramework/config/definitions.yaml']
        for name in files:
            archive.add(repo / name, arcname=name)
    shutil.copyfile(repo / 'AnalysisZipFramework/submission/run_tracking_georotation.sh', submit / 'worker.sh')
    (submit / 'worker.sh').chmod(0o755)
    (submit / 'jobs.sub').write_text(f'''universe = vanilla
initialdir = {submit}
executable = {submit}/worker.sh
arguments = $(index) $(rdo) {args.nevents} $(result)
transfer_input_files = {submit}/tracking-georotation-code.tar.gz
should_transfer_files = YES
when_to_transfer_output = ON_EXIT
transfer_output_files = ""
request_cpus = 1
request_memory = 3000MB
request_disk = 6000MB
getenv = False
+JobFlavour = "{args.flavour}"
+NuMuStage = "stage201_georotation"
+NuMuRun = $(run)
+NuMuIndex = $(index)
+NuMuCalypsoCommit = "88c457c1e4bf4154e67b96114ee8e7020d9b1a97"
log = {submit}/events.log
output = {submit}/$(ClusterId).$(ProcId).out
error = {submit}/$(ClusterId).$(ProcId).err
queue index,run,geometry,rdo,old_merge,result from {submit}/manifest.tsv
''')
    (submit / 'preparation.json').write_text(json.dumps(dict(repo=str(repo), jobs=len(indices),
            indices=indices, nevents=args.nevents, outputs=str(outputs)), indent=2)+'\n')
    print(submit / 'jobs.sub')


if __name__ == '__main__':
    main()
