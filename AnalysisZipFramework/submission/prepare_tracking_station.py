#!/usr/bin/env python3
"""Freeze paired old/new local-truth jobs, validating against the previous whole-sample cuts."""
import argparse
from pathlib import Path
import shutil
import tarfile
import numpy as np


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[2])
    p.add_argument('--all',action='store_true');p.add_argument('--name',default='pilot');p.add_argument('--indices',type=int,nargs='*')
    p.add_argument('--nevents',type=int,default=1000)
    args=p.parse_args();repo=args.repo.resolve()
    submit=Path.home()/'condor/nu_muAnalysis/stage203_station_truth'/args.name;submit.mkdir(parents=True,exist_ok=True)
    output=repo/'ntuples/tracking_station_stage203'/args.name;output.mkdir(parents=True,exist_ok=True)
    refs=submit/'references';refs.mkdir(exist_ok=True)
    manifest=[r.split('\t') for r in (repo/'workbook/stage201_tracking/input_manifest.tsv').read_text().splitlines()]
    indices=list(range(len(manifest))) if args.all else args.indices if args.indices is not None else [342]
    caches={}
    for version,path in [('old','workbook/stage10_tracking_z/fiducial_events.npz'),('new','workbook/stage201_tracking/fiducial_events.npz')]:
        with np.load(repo/path) as f:caches[version]={k:f[k] for k in ['manifest_indices','file_offsets','event_run','event_eventID','event_cut_bits']}
    rows=[]
    for i in indices:
        if i==291:continue  # no published/validated old production for this RDO
        r=manifest[i]
        for version in ['old','new']:
            a=caches[version];j=np.flatnonzero(a['manifest_indices']==i).item();lo,hi=a['file_offsets'][j:j+2]
            ref=f'{version}_{i:03d}.npz'
            np.savez_compressed(refs/ref,run=a['event_run'][lo:hi],eventID=a['event_eventID'][lo:hi],event_cut_bits=a['event_cut_bits'][lo:hi])
            slices=range(10) if i==53 and args.nevents==-1 and version=='new' else [0]
            for part in slices:
                skip=part*1000;nevents=1000 if len(slices)>1 else args.nevents
                result=str(output/f'{version}_{i:03d}_{part:02d}.npz').replace('/eos/home-x/xcheng/','/eos/user/x/xcheng/')
                rows.append([i,version,r[3],nevents,skip,result,ref])
    (submit/'manifest.tsv').write_text(''.join('\t'.join(map(str,r))+'\n' for r in rows))
    scripts=['run_tracking_station','run_tracking_georotation','extract_tracking_station','compare_tracking']
    files=['setup_env.sh','AnalysisZipFramework/config/cuts.yaml','AnalysisZipFramework/config/definitions.yaml',
           'AnalysisZipFramework/include/RDFDefines.h','AnalysisZipFramework/include/TrackingStationDiagnostic.h',
           'AnalysisZipFramework/include/TrackingDuplicateDiagnostic.h','AnalysisZipFramework/include/TrackingTruthDiagnostic.h']
    files += [f'AnalysisZipFramework/scripts/{s}.py' for s in scripts]
    with tarfile.open(submit/'tracking-station-code.tar.gz','w:gz') as tar:
        for name in files:tar.add(repo/name,arcname=name)
        tar.add(refs,arcname='references')
    shutil.copyfile(repo/'AnalysisZipFramework/submission/run_tracking_station.sh',submit/'worker.sh');(submit/'worker.sh').chmod(0o755)
    (submit/'jobs.sub').write_text(f'''universe = vanilla
initialdir = {submit}
executable = {submit}/worker.sh
arguments = $(index) $(version) $(rdo) $(nevents) $(skip) $(result) $(reference)
transfer_input_files = {submit}/tracking-station-code.tar.gz
should_transfer_files = YES
transfer_output_files = ""
when_to_transfer_output = ON_EXIT
request_cpus = 1
request_memory = 3000MB
request_disk = 6500MB
getenv = False
+JobFlavour = "{'workday' if args.nevents==-1 else 'microcentury'}"
+NuMuStage = "stage203_station_truth"
log = {submit}/events.log
output = {submit}/$(ClusterId).$(ProcId).out
error = {submit}/$(ClusterId).$(ProcId).err
queue index,version,rdo,nevents,skip,result,reference from {submit}/manifest.tsv
''')
    print(submit/'jobs.sub')


if __name__=='__main__':main()
