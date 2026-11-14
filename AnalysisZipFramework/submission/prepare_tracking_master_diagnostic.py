#!/usr/bin/env python3
"""Prepare targeted stage209 replays with explicit diagnostic controls."""
import argparse
from pathlib import Path
import shutil
import tarfile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name',required=True)
    parser.add_argument('--spec',type=Path,required=True,
        help='TSV: index skip nevents control audit_library event_ids (no header)')
    args=parser.parse_args();repo=Path(__file__).resolve().parents[2]
    submit=Path.home()/'condor/nu_muAnalysis/stage209_master_causes'/args.name
    submit.mkdir(parents=True,exist_ok=True)
    output=repo/'ntuples/tracking_causes_stage209'/args.name;output.mkdir(parents=True,exist_ok=True)
    inputs=[line.split('\t') for line in (repo/'workbook/stage201_tracking/input_manifest.tsv').read_text().splitlines()]
    rows=[]
    for number,line in enumerate(args.spec.read_text().splitlines()):
        index,skip,nevents,control,audit,events=line.split('\t');index=int(index)
        result=str(output/f'{number:03d}_{index}_{skip}_{control}_a{audit}.npz').replace('/eos/home-x/xcheng/','/eos/user/x/xcheng/')
        rows.append([index,inputs[index][3],nevents,skip,result,control,events,audit])
    (submit/'manifest.tsv').write_text(''.join('\t'.join(map(str,row))+'\n' for row in rows))
    scripts=['run_tracking_master_diagnostic','run_tracking_station','run_tracking_georotation','extract_tracking_station','compare_tracking']
    names=['setup_env.sh','AnalysisZipFramework/config/cuts.yaml','AnalysisZipFramework/config/definitions.yaml',
        'AnalysisZipFramework/include/RDFDefines.h','AnalysisZipFramework/include/TrackingStationDiagnostic.h',
        'AnalysisZipFramework/include/TrackingDuplicateDiagnostic.h','AnalysisZipFramework/include/TrackingTruthDiagnostic.h',
        'AnalysisZipFramework/include/TrackingMomentumQuality.h']
    names += [f'AnalysisZipFramework/scripts/{name}.py' for name in scripts]
    with tarfile.open(submit/'code.tar.gz','w:gz') as archive:
        for name in names:archive.add(repo/name,arcname=name)
        archive.add(repo/'software/stage205_material/material-manual-rowmajor.json.gz',arcname='material-strict-reference.json.gz')
        archive.add(repo/'workbook/stage208_master_integration/software_provenance.json',arcname='software_provenance.json')
    shutil.copyfile(repo/'AnalysisZipFramework/submission/run_tracking_master_diagnostic.sh',submit/'worker.sh')
    (submit/'worker.sh').chmod(0o755)
    (submit/'jobs.sub').write_text(f'''universe = vanilla
initialdir = {submit}
executable = {submit}/worker.sh
arguments = $(index) $(rdo) $(nevents) $(skip) $(result) $(control) $(events) $(audit)
transfer_input_files = {submit}/code.tar.gz
should_transfer_files = YES
transfer_output_files = ""
request_cpus = 1
request_memory = 3500MB
request_disk = 7000MB
getenv = False
+JobFlavour = "workday"
+NuMuStage = "stage209_master_causes"
log = {submit}/events.log
output = {submit}/$(ClusterId).$(ProcId).out
error = {submit}/$(ClusterId).$(ProcId).err
queue index,rdo,nevents,skip,result,control,events,audit from {submit}/manifest.tsv
''')
    print(submit/'jobs.sub')


if __name__=='__main__':main()
