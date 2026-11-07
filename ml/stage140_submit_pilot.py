"""Submit the finite response-MC experiment, with immutable payload."""
import json
import subprocess
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage140_energy_ml'
SPOOL = Path.home()/'condor/nu_muAnalysis/stage140'

def main():
    assert not (OUT/'pilot_submission.json').exists(), 'Inspect existing job before resubmission'
    assert not (OUT/'pilot_results.json').exists(), 'Existing finite-MC result must not be repeated'
    stamp = time.time_ns()
    relative = f'software/stage140/{stamp}/energy-ml-stage140.tar.gz'
    package = ROOT/relative
    package.parent.mkdir(parents=True)
    (ROOT/'ntuples/energy_ml_stage140').mkdir(exist_ok=True)
    files = ['ml/stage140_pilot.py','ml/stage140_solve.py',
             'ml/stage139_likelihood.py','ml/stage139_optimizer.py',
             'workbook/stage140_energy_ml/pilot_protocol.json',
             'ntuples/energy_ml_stage139/template_counts.npz']
    with tarfile.open(package, 'w:gz') as archive:
        for name in files:
            archive.add(ROOT/name, arcname=name)
    SPOOL.mkdir(parents=True, exist_ok=True)
    (SPOOL/'logs').mkdir(exist_ok=True)
    worker = SPOOL/f'worker_{stamp}.sh'
    worker.write_bytes((ROOT/'AnalysisZipFramework/submission/run_ml_stage140.sh').read_bytes())
    descriptor = f'''universe = vanilla
initialdir = {SPOOL}
executable = /bin/bash
transfer_executable = False
arguments = {worker}
transfer_input_files = root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/{relative}
should_transfer_files = YES
transfer_output_files = ""
request_cpus = 4
request_memory = 12000MB
request_disk = 2000MB
max_retries = 0
+MaxRuntime = 7200
+PeriodicRemoveReason = "Stage140 cumulative CPU budget 600 seconds exceeded"
periodic_remove = (RemoteUserCpu + RemoteSysCpu) > 600
+NuMuStage = "energy-ml-stage140"
log = {SPOOL}/logs/$(ClusterId).$(ProcId).log
output = {SPOOL}/logs/$(ClusterId).$(ProcId).out
error = {SPOOL}/logs/$(ClusterId).$(ProcId).err
queue 1
'''
    submit = SPOOL/f'pilot_{stamp}.sub'
    submit.write_text(descriptor)
    result = subprocess.check_output(['condor_submit', '-terse', str(submit)], text=True).strip()
    record = dict(result=result, phase='pilot', indices=[0], cpus=4,
                  descriptor=descriptor, package=dict(path=relative,
                  bytes=package.stat().st_size, files=files),
                  frozen_before_new_risks=True, total_fit_budget=0)
    (OUT/'pilot_submission.json').write_text(json.dumps(record, indent=2)+'\n')
    print(result)

if __name__ == '__main__':
    main()
