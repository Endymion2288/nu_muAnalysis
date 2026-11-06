"""Immutable worker/package and scoped HTCondor submissions."""
import argparse
import json
import subprocess
import tarfile
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage125_energy_ml'
SPOOL=Path('/afs/cern.ch/user/x/xcheng/condor/nu_muAnalysis/stage125')

def main():
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['pilot','production']);p.add_argument('--indices',nargs='+',type=int);p.add_argument('--exclude-machine');a=p.parse_args()
    protocol=json.loads((OUT/'protocol.json').read_text())
    if a.phase=='pilot':
        indices=[next(s['index'] for s in protocol['sources'] if s['run']==r['run']) for r in protocol['inventory']]
    else:indices=list(range(len(protocol['sources'])))
    if a.indices is not None:indices=a.indices
    package=ROOT/'software/energy-ml-stage125.tar.gz'
    if a.phase=='pilot' or not package.exists():
        with tarfile.open(package,'w:gz') as t:
            for f in sorted((ROOT/'ml').glob('*.py')):t.add(f,arcname=str(f.relative_to(ROOT)))
            for f in ['ml/configs','AnalysisZipFramework/config','AnalysisZipFramework/include','build/analysis','setup_env.sh','workbook/stage125_energy_ml/protocol.json']:
                t.add(ROOT/f,arcname=f)
    stamp=time.time_ns();worker=SPOOL/f'worker_{stamp}.sh';worker.write_bytes((ROOT/'AnalysisZipFramework/submission/run_ml_stage125.sh').read_bytes())
    descriptor=f'''universe = vanilla
initialdir = {SPOOL}
executable = /bin/bash
transfer_executable = False
arguments = {worker} $(source_index) {a.phase}
transfer_input_files = root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/software/energy-ml-stage125.tar.gz
should_transfer_files = YES
transfer_output_files = ""
request_cpus = 1
request_memory = 3000MB
request_disk = 8000MB
max_retries = 0
+MaxRuntime = 7200
+NuMuStage = "energy-ml-stage125"
log = {SPOOL}/logs/$(ClusterId).log
output = {SPOOL}/logs/$(ClusterId).$(ProcId).out
error = {SPOOL}/logs/$(ClusterId).$(ProcId).err
queue source_index in {','.join(map(str,indices))}
'''
    if a.exclude_machine:
        assert all(c.isalnum() or c in '.-' for c in a.exclude_machine)
        descriptor=descriptor.replace('queue source_index',f'requirements = Machine != "{a.exclude_machine}"\nqueue source_index')
    path=SPOOL/f'{a.phase}_{stamp}.sub';path.write_text(descriptor)
    result=subprocess.check_output(['condor_submit','-terse',str(path)],text=True)
    record=dict(phase=a.phase,result=result,indices=indices,descriptor=descriptor,package_bytes=package.stat().st_size)
    (OUT/f'{a.phase}_submission_{stamp}.json').write_text(json.dumps(record,indent=2)+'\n');print(result)

if __name__=='__main__':main()
