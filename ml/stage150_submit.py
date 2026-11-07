"""Immutable stage150 cached-support preflight; physics extension needs admission."""
import json
import subprocess
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage150_energy_ml'
SPOOL = Path.home()/'condor/nu_muAnalysis/stage150'


def main():
    assert not (OUT/'support_submission.json').exists()
    files = ['workbook/stage150_energy_ml/protocol.json', 'ml/stage150_support.py',
        'ntuples/energy_ml_stage131/production_cases.json.gz', 'ntuples/energy_ml_stage131/matched_input.npz',
        'ntuples/energy_ml_stage137/boundary_evidence.json.gz']
    stamp = time.time_ns()
    relative = f'software/stage150/{stamp}/energy-ml-stage150.tar.gz'
    package = ROOT/relative
    package.parent.mkdir(parents=True)
    with tarfile.open(package, 'w:gz') as archive:
        for name in files:
            archive.add(ROOT/name, arcname=name)
    SPOOL.mkdir(parents=True, exist_ok=True)
    (SPOOL/'logs').mkdir(exist_ok=True)
    worker = SPOOL/f'worker_{stamp}.sh'
    worker.write_bytes((ROOT/'AnalysisZipFramework/submission/run_ml_stage150.sh').read_bytes())
    descriptor = f'''universe = vanilla
initialdir = {SPOOL}
executable = /bin/bash
transfer_executable = False
arguments = {worker.name}
transfer_input_files = {worker}, root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/{relative}
should_transfer_files = YES
transfer_output_files = ""
request_cpus = 4
request_memory = 12000MB
request_disk = 8000MB
max_retries = 0
+MaxRuntime = 86400
+PeriodicRemoveReason = "Stage150 support CPU budget and response reserve"
periodic_remove = (RemoteUserCpu + RemoteSysCpu) > 82
+NuMuStage = "energy-ml-stage150"
log = {SPOOL}/logs/$(ClusterId).$(ProcId).log
output = {SPOOL}/logs/$(ClusterId).$(ProcId).out
error = {SPOOL}/logs/$(ClusterId).$(ProcId).err
queue 1
'''
    path = SPOOL/f'support_{stamp}.sub'
    path.write_text(descriptor)
    result = subprocess.check_output(['condor_submit', '-terse', str(path)], text=True).strip()
    (OUT/'support_submission.json').write_text(json.dumps(dict(result=result, phase='support',
        descriptor=descriptor, CPU_allowance_s=82,
        package=dict(path=relative, bytes=package.stat().st_size, files=files)), indent=2)+'\n')
    print(result)


if __name__ == '__main__':
    main()
