#!/usr/bin/env python3
"""Freeze the report job after all stage201 reconstruction summaries are available."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tarfile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--production',default='productionv2')
    parser.add_argument('--details',action='store_true')
    parser.add_argument('--validate',action='store_true')
    args=parser.parse_args()
    repo=args.repo.resolve()
    base=Path.home()/'condor/nu_muAnalysis/stage201_tracking'
    manifest=base/('details' if args.details else args.production)/'manifest.tsv'
    records=[line.split('\t') for line in manifest.read_text().splitlines()]
    results=[r[-1] if args.details else r[5] for r in records]
    existing=set()
    for parent in {str(Path(r).parent) for r in results}:
        existing.update(subprocess.check_output(['xrdfs','root://eoshome-x.cern.ch','ls',parent],text=True).splitlines())
    missing=[r[0] for r,result in zip(records,results) if result not in existing]
    if missing:raise RuntimeError(f'Summaries missing: {missing}')
    submit=base/('storage_validation' if args.validate else 'details_report' if args.details else 'report')
    submit.mkdir(parents=True,exist_ok=True)
    scripts=['report_tracking_georotation','report_tracking_comparison','report_tracking_z',
             'compare_tracking','extract_tracking_georotation','run_tracking_georotation','report_tracking_loss']
    scripts+=['report_tracking_georotation_details','report_tracking_loss_details','report_tracking_truth']
    scripts+=['validate_tracking_georotation_storage']
    files=[f'AnalysisZipFramework/scripts/{name}.py' for name in scripts]
    files+=['AnalysisZipFramework/config/cuts.yaml','AnalysisZipFramework/config/definitions.yaml',
            'workbook/stage10_tracking_z/fiducial_events.npz','AnalysisZipFramework/scripts/tracking_loss_viewer.html',
            'workbook/stage201_tracking/software_provenance.json','workbook/stage201_tracking/recovery53_audit.json']
    with tarfile.open(submit/'tracking-georotation-report.tar.gz','w:gz') as archive:
        for name in files:archive.add(repo/name,arcname=name)
        archive.add(manifest,arcname='manifest.tsv')
        if args.validate:archive.add(base/'details/manifest.tsv',arcname='details_manifest.tsv')
    shutil.copyfile(repo/'AnalysisZipFramework/submission/run_tracking_georotation_report.sh',submit/'worker.sh')
    (submit/'worker.sh').chmod(0o755)
    (submit/'report.sub').write_text(f'''universe = vanilla
initialdir = {submit}
executable = {submit}/worker.sh
arguments = {'validate' if args.validate else 'details' if args.details else 'overview'}
transfer_input_files = {submit}/tracking-georotation-report.tar.gz
should_transfer_files = YES
when_to_transfer_output = ON_EXIT
transfer_output_files = ""
request_cpus = 2
request_memory = 6000MB
request_disk = 6000MB
getenv = False
+JobFlavour = "microcentury"
+NuMuStage = "stage201_report"
log = {submit}/events.log
output = {submit}/$(ClusterId).out
error = {submit}/$(ClusterId).err
queue
''')
    print(submit/'report.sub')


if __name__=='__main__':
    main()
