#!/usr/bin/env python3
"""Replay every strict-map backward-pass/merge-fail event with complete raw hit diagnostics."""
import argparse
import csv
import gzip
from pathlib import Path
import sys
import tarfile

import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from report_tracking_ablation import load_cache,subset


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--pilot',action='store_true');args=p.parse_args()
    repo=Path(__file__).resolve().parents[2];base=Path.home()/'condor/nu_muAnalysis/stage205_material'
    name='details_pilot' if args.pilot else 'details'
    submit=base/name;submit.mkdir(parents=True,exist_ok=True)
    output=repo/'ntuples/tracking_ablation_205_material'/name;output.mkdir(parents=True,exist_ok=True)
    with (repo/'workbook/stage205_material/full/mode_loss_events.tsv').open() as f:
        targets={(int(r['run']),int(r['eventID'])) for r in csv.DictReader(f,delimiter='\t')
                 if r['version']=='strict' and r['left']=='backward' and r['right']=='merge'}
    assert len(targets)==50
    if args.pilot:targets={min(targets)}
    found={}
    rows=[r.split('\t') for r in (base/'strict_final_manifest.tsv').read_text().splitlines()]
    for row in rows:
        path=Path(row[5].replace('/eos/user/x/xcheng/','/eos/home-x/xcheng/'))
        with np.load(path) as f:
            for key in targets.intersection(zip(f['run'].astype(int),f['eventID'].astype(int))):
                assert key not in found;found[key]=row
        if len(found)==len(targets):break
    assert set(found)==targets
    data=load_cache(repo/'workbook/stage205_material/full/strict.npz');manifest=[]
    refs=submit/'references';refs.mkdir(exist_ok=True)
    for (run,event),row in sorted(found.items()):
        a=subset(data,np.array([run*1000000000+event]));assert len(a['run'])==1
        a['manifest_index']=int(row[0]);np.savez_compressed(refs/f'{run}_{event}.npz',**a)
        result=str(output/f'{run}_{event}.json').replace('/eos/home-x/xcheng/','/eos/user/x/xcheng/')
        manifest.append([row[0],run,event,row[2],'-','references/'+f'{run}_{event}.npz',result])
    (submit/'manifest.tsv').write_text(''.join('\t'.join(map(str,r))+'\n' for r in manifest))
    files=['setup_env.sh','AnalysisZipFramework/config/cuts.yaml','AnalysisZipFramework/config/definitions.yaml']
    files += ['AnalysisZipFramework/include/'+n+'.h' for n in ['RDFDefines','TrackingTruthDiagnostic','TrackingDuplicateDiagnostic']]
    files += ['AnalysisZipFramework/scripts/'+n+'.py' for n in ['run_tracking_ablation','run_tracking_station','run_tracking_georotation','extract_tracking_station','extract_tracking_georotation','extract_tracking_georotation_details','compare_tracking','locate_tracking_event']]
    with tarfile.open(submit/'tracking-georotation-code.tar.gz','w:gz') as tar:
        for path in files:tar.add(repo/path,arcname=path)
        tar.add(refs,arcname='references')
        import io
        payload=gzip.decompress((repo/'software/stage205_material/material-manual-rowmajor.json.gz').read_bytes())
        info=tarfile.TarInfo('material-rotated.json');info.size=len(payload);tar.addfile(info,io.BytesIO(payload))
    worker=(repo/'AnalysisZipFramework/submission/run_tracking_georotation_details.sh').read_text()
    worker=worker.replace('cd "$detail_scratch"','cd "$detail_scratch"\ncp code/material-rotated.json material-rotated.json')
    worker=worker.replace('stage reference xrdcp --silent "root://eoshome-x.cern.ch/$reference" reference.npz','cp "$detail_scratch/code/$reference" reference.npz')
    worker=worker.replace('run_tracking_georotation.py" reco','run_tracking_ablation.py" material')
    worker=worker.replace('--repo "$detail_scratch/code" --reference reference.npz','--repo "$detail_scratch/code" --reference reference.npz --station-reference')
    (submit/'worker.sh').write_text(worker);(submit/'worker.sh').chmod(0o755)
    (submit/'jobs.sub').write_text(f'''universe = vanilla
initialdir = {submit}
executable = {submit}/worker.sh
arguments = $(index) $(run) $(event) $(rdo) $(old_merge) $(reference) $(result)
transfer_input_files = {submit}/tracking-georotation-code.tar.gz
should_transfer_files = YES
transfer_output_files = ""
request_cpus = 1
request_memory = 3000MB
request_disk = 4000MB
requirements = Machine != "b9p13p2679.cern.ch"
getenv = False
+JobFlavour = "microcentury"
+NuMuStage = "stage205_material_details"
log = {submit}/events.log
output = {submit}/$(ClusterId).$(ProcId).out
error = {submit}/$(ClusterId).$(ProcId).err
queue index,run,event,rdo,old_merge,reference,result from {submit}/manifest.tsv
''')
    print(len(manifest),'events',submit/'jobs.sub')


if __name__=='__main__':main()
