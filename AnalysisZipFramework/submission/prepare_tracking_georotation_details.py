#!/usr/bin/env python3
"""Prepare same-software event reruns for new losses, historical losses and the old NaN case."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tarfile

import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--pilot',action='store_true')
    parser.add_argument('--available',action='store_true',help='Prepare an explicitly partial batch while production finishes')
    parser.add_argument('--name',help='Submission directory; outputs always use the common details directory')
    parser.add_argument('--summary-directory',type=Path,help='Validated local XRootD readback cache')
    parser.add_argument('--exclude-submitted',type=Path,nargs='*',default=[],help='Earlier manifests whose jobs may still be running')
    parser.add_argument('--event',action='append',default=[],help='Restrict a diagnostic submission to run/event')
    args = parser.parse_args()
    repo = args.repo.resolve()
    base = Path.home()/'condor/nu_muAnalysis/stage201_tracking'
    records = [line.split('\t') for line in (base/'productionv2/manifest.tsv').read_text().splitlines()]
    with np.load(repo/'workbook/stage10_tracking_z/fiducial_events.npz') as old:
        mask=(old['event_cut_bits'][:,1]==16383)&(old['event_cut_bits'][:,2]!=16383)
        historical=set(zip(old['event_run'][mask],old['event_eventID'][mask]))
    targets=[]
    for record in records:
        summary_path=args.summary_directory/Path(record[5]).name if args.summary_directory else Path(record[5])
        if not summary_path.exists():
            if args.pilot or args.available:continue
            raise RuntimeError(f'Missing full-production reference {record[0]}')
        with np.load(summary_path) as s:
            for run,event,bits in zip(s['event_run'],s['event_eventID'],s['event_cut_bits']):
                reasons=[]
                if bits[1]==16383 and bits[2]!=16383:reasons.append('new_backward_only')
                if (run,event) in historical:reasons.append('old89')
                if (run,event)==(200094,401649):reasons.append('old_nan')
                if reasons:
                    targets.append([record[0],int(run),int(event),record[3],record[4],record[5],'+'.join(reasons)])
            if int(record[0])==291 and 401649 not in s['event_eventID']:
                assert ((s['tracks'][:,0]==200094)&(s['tracks'][:,1]==401649)).any()
                targets.append([record[0],200094,401649,record[3],record[4],record[5],'old_nan'])
    if args.event:
        requested={tuple(map(int,key.split('/'))) for key in args.event}
        targets=[r for r in targets if (r[1],r[2]) in requested]
        assert {(r[1],r[2]) for r in targets}==requested
    if args.pilot:
        targets=[next(r for r in targets if 'new_backward_only' in r[-1])]
    output_name='details_pilot' if args.pilot else 'details'
    submit=base/(args.name or output_name);submit.mkdir(parents=True,exist_ok=True)
    output=repo/'ntuples/tracking_georotation_stage201'/output_name;output.mkdir(parents=True,exist_ok=True)
    for r in targets:r.append(str(output/f'{r[1]}_{r[2]}.json').replace('/eos/home-x/xcheng/','/eos/user/x/xcheng/'))
    (submit/'manifest.tsv').write_text(''.join('\t'.join(map(str,r))+'\n' for r in targets))
    remote_output=str(output).replace('/eos/home-x/xcheng/','/eos/user/x/xcheng/')
    existing=set(subprocess.check_output(['xrdfs','root://eoshome-x.cern.ch','ls',remote_output],text=True).splitlines())
    submitted={line.split('\t')[-1] for p in args.exclude_submitted for line in p.read_text().splitlines()}
    pending=[r for r in targets if r[-1] not in existing and r[-1] not in submitted]
    (submit/'pending.tsv').write_text(''.join('\t'.join(map(str,r))+'\n' for r in pending))
    with tarfile.open(submit/'tracking-georotation-code.tar.gz','w:gz') as archive:
        files=['setup_env.sh','workbook/stage201_tracking/software_provenance.json',
               'AnalysisZipFramework/config/cuts.yaml','AnalysisZipFramework/config/definitions.yaml',
               'AnalysisZipFramework/include/RDFDefines.h','AnalysisZipFramework/include/TrackingTruthDiagnostic.h',
               'AnalysisZipFramework/include/TrackingDuplicateDiagnostic.h']
        files += [f'AnalysisZipFramework/scripts/{s}.py' for s in
                  ('run_tracking_georotation','extract_tracking_georotation',
                   'extract_tracking_georotation_details','compare_tracking')]
        files.append('AnalysisZipFramework/scripts/locate_tracking_event.py')
        for name in files:archive.add(repo/name,arcname=name)
    shutil.copyfile(repo/'AnalysisZipFramework/submission/run_tracking_georotation_details.sh',submit/'worker.sh')
    (submit/'worker.sh').chmod(0o755)
    (submit/'jobs.sub').write_text(f'''universe = vanilla
initialdir = {submit}
executable = {submit}/worker.sh
arguments = $(index) $(run) $(event) $(rdo) $(old_merge) $(reference) $(result)
transfer_input_files = {submit}/tracking-georotation-code.tar.gz
should_transfer_files = YES
when_to_transfer_output = ON_EXIT
transfer_output_files = ""
request_cpus = 1
request_memory = 3000MB
request_disk = 4000MB
getenv = False
+JobFlavour = "microcentury"
+NuMuStage = "stage201_spatial_details"
+NuMuReasons = "$(reasons)"
log = {submit}/events.log
output = {submit}/$(ClusterId).$(ProcId).out
error = {submit}/$(ClusterId).$(ProcId).err
queue index,run,event,rdo,old_merge,reference,reasons,result from {submit}/pending.tsv
''')
    print(f'{len(targets)} selected events, {len(pending)} pending: {submit}/jobs.sub')


if __name__=='__main__':
    main()
