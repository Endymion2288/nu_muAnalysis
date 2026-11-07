"""Immutable batched original coverage computation, no application short limit."""
import argparse
import json
import subprocess
import tarfile
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'workbook/stage140_energy_ml'
SPOOL=Path.home()/'condor/nu_muAnalysis/stage140'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['batch','profile','summary'])
    args=parser.parse_args();phase=args.phase
    assert not (OUT/f'{phase}_submission.json').exists(),'Inspect previous attempt before resubmission'
    assert json.loads((OUT/'pilot_results.json').read_text())['results']
    stamp=time.time_ns();relative=f'software/stage140/{stamp}/energy-ml-stage140.tar.gz'
    package=ROOT/relative;package.parent.mkdir(parents=True)
    files=[str(p.relative_to(ROOT)) for p in (ROOT/'ml').glob('stage140_*.py')]
    files+=['ml/stage139_likelihood.py','ml/stage139_optimizer.py',
            'workbook/stage140_energy_ml/protocol.json',
            'workbook/stage140_energy_ml/pilot_results.json',
            'ntuples/energy_ml_stage139/template_counts.npz']
    if phase=='summary':
        for kind,count in [('batch',60),('profile',6)]:
            extra=[f'ntuples/energy_ml_stage140/{kind}_{i}_result.tar.gz' for i in range(count)]
            assert all((ROOT/p).exists() for p in extra)
            files+=extra
    with tarfile.open(package,'w:gz') as archive:
        for name in files:archive.add(ROOT/name,arcname=name)
    SPOOL.mkdir(parents=True,exist_ok=True);(SPOOL/'logs').mkdir(exist_ok=True)
    worker=SPOOL/f'worker_{stamp}.sh'
    worker.write_bytes((ROOT/'AnalysisZipFramework/submission/run_ml_stage140_formal.sh').read_bytes())
    count=60 if phase=='batch' else 6 if phase=='profile' else 1
    cpus=8 if phase=='batch' else 1
    descriptor=f'''universe = vanilla
initialdir = {SPOOL}
executable = /bin/bash
transfer_executable = False
arguments = {worker} {phase} $(task_index)
transfer_input_files = root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/{relative}
should_transfer_files = YES
transfer_output_files = ""
request_cpus = {cpus}
request_memory = 12000MB
request_disk = 2000MB
max_retries = 0
+MaxRuntime = 86400
+NuMuStage = "energy-ml-stage140"
log = {SPOOL}/logs/$(ClusterId).$(ProcId).log
output = {SPOOL}/logs/$(ClusterId).$(ProcId).out
error = {SPOOL}/logs/$(ClusterId).$(ProcId).err
max_materialize = 12
max_idle = 12
queue task_index in {','.join(str(i) for i in range(count))}
'''
    sub=SPOOL/f'{phase}_{stamp}.sub';sub.write_text(descriptor)
    result=subprocess.check_output(['condor_submit','-terse',str(sub)],text=True).strip()
    record=dict(result=result,phase=phase,indices=list(range(count)),cpus=cpus,
                descriptor=descriptor,package=dict(path=relative,bytes=package.stat().st_size,files=files))
    (OUT/f'{phase}_submission.json').write_text(json.dumps(record,indent=2)+'\n');print(result)

if __name__=='__main__':main()
