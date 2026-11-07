"""Submit the finite response-MC experiment, with immutable payload."""
import json
import subprocess
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage138_energy_ml'
SPOOL = Path.home()/'condor/nu_muAnalysis/stage138'

def main():
    assert not (OUT/'summary_submission.json').exists(), 'Inspect existing job before resubmission'
    assert not (OUT/'independent_integral_validation.json').exists(), 'Existing finite-MC result must not be repeated'
    stamp = time.time_ns()
    relative = f'software/stage138/{stamp}/energy-ml-stage138.tar.gz'
    package = ROOT/relative
    package.parent.mkdir(parents=True)
    (ROOT/'ntuples/energy_ml_stage138').mkdir(exist_ok=True)
    files = [str(p.relative_to(ROOT)) for p in (ROOT/'ml').glob('*.py')]
    files += ['workbook/stage138_energy_ml/protocol.json',
              'ntuples/energy_ml_stage138/control_0.json.gz',
              'workbook/stage138_energy_ml/control_summary.json']
    with tarfile.open(package, 'w:gz') as archive:
        for name in files:
            archive.add(ROOT/name, arcname=name)
    SPOOL.mkdir(parents=True, exist_ok=True)
    (SPOOL/'logs').mkdir(exist_ok=True)
    worker = SPOOL/f'worker_{stamp}.sh'
    worker.write_bytes((ROOT/'AnalysisZipFramework/submission/run_ml_stage138_summary.sh').read_bytes())
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
+MaxRuntime = 1800
+PeriodicRemoveReason = "Stage138 cumulative CPU budget 300 seconds exceeded"
periodic_remove = (RemoteUserCpu + RemoteSysCpu) > 300
+NuMuStage = "energy-ml-stage138"
log = {SPOOL}/logs/$(ClusterId).$(ProcId).log
output = {SPOOL}/logs/$(ClusterId).$(ProcId).out
error = {SPOOL}/logs/$(ClusterId).$(ProcId).err
queue 1
'''
    submit = SPOOL/f'summary_{stamp}.sub'
    submit.write_text(descriptor)
    result = subprocess.check_output(['condor_submit', '-terse', str(submit)], text=True).strip()
    record = dict(result=result, phase='summary', indices=[0], cpus=4,
                  descriptor=descriptor, package=dict(path=relative,
                  bytes=package.stat().st_size, files=files),
                  frozen_before_new_risks=True, total_fit_budget=0)
    (OUT/'summary_submission.json').write_text(json.dumps(record, indent=2)+'\n')
    print(result)

if __name__ == '__main__':
    main()
