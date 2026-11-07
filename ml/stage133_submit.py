"""Submit the single bounded cached-input experiment, with immutable payload."""
import json
import subprocess
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage133_energy_ml'
SPOOL = Path.home()/'condor/nu_muAnalysis/stage133'

def main():
    assert not (OUT/'submission.json').exists(), 'Inspect existing job before resubmission'
    assert not (OUT/'fit_lock.json').exists(), 'Seven-fit experiment already started'
    stamp = time.time_ns()
    relative = f'software/stage133/{stamp}/energy-ml-stage133.tar.gz'
    package = ROOT/relative
    package.parent.mkdir(parents=True)
    (ROOT/'ntuples/energy_ml_stage133').mkdir(exist_ok=True)
    files = [str(p.relative_to(ROOT)) for p in (ROOT/'ml').glob('*.py')]
    files += ['ml/configs', 'workbook/stage133_energy_ml/protocol.json',
              'ntuples/energy_ml_stage131/matched_input.npz',
              'ntuples/energy_ml_stage131/bootstrap_draws.npz',
              'ml/artifacts/stage131/energy_predictions.npz']
    with tarfile.open(package, 'w:gz') as archive:
        for name in files:
            archive.add(ROOT/name, arcname=name)
    SPOOL.mkdir(parents=True, exist_ok=True)
    (SPOOL/'logs').mkdir(exist_ok=True)
    worker = SPOOL/f'worker_{stamp}.sh'
    worker.write_bytes((ROOT/'AnalysisZipFramework/submission/run_ml_stage133.sh').read_bytes())
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
+PeriodicRemoveReason = "Stage133 cumulative CPU budget 900 seconds exceeded"
periodic_remove = (RemoteUserCpu + RemoteSysCpu) > 900
+NuMuStage = "energy-ml-stage133"
log = {SPOOL}/logs/$(ClusterId).$(ProcId).log
output = {SPOOL}/logs/$(ClusterId).$(ProcId).out
error = {SPOOL}/logs/$(ClusterId).$(ProcId).err
queue 1
'''
    submit = SPOOL/f'analysis_{stamp}.sub'
    submit.write_text(descriptor)
    result = subprocess.check_output(['condor_submit', '-terse', str(submit)], text=True).strip()
    record = dict(result=result, phase='analysis', indices=[0], cpus=4,
                  descriptor=descriptor, package=dict(path=relative,
                  bytes=package.stat().st_size, files=files),
                  frozen_before_new_risks=True, total_fit_budget=7)
    (OUT/'submission.json').write_text(json.dumps(record, indent=2)+'\n')
    print(result)

if __name__ == '__main__':
    main()
