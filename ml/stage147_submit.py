"""One fixed recorded-track association control on already certified muon roots."""
import json
import subprocess
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage147_energy_ml'
SPOOL = Path.home()/'condor/nu_muAnalysis/stage147'


def main():
    assert not (OUT/'control_submission.json').exists()
    previous = json.loads((ROOT/'workbook/stage146_energy_ml/scheduler_accounting.json').read_text())
    assert previous['live_N'] == 0 and all(r.get('ExitCode') == 0 for r in previous['jobs'])
    stamp = time.time_ns()
    relative = f'software/stage147/{stamp}/energy-ml-stage147.tar.gz'
    package = ROOT/relative
    package.parent.mkdir(parents=True)
    files = ['ml/stage147_track_control.py', 'ml/stage145_mu_joint.py',
             'workbook/stage147_energy_ml/protocol.json', 'workbook/stage146_energy_ml/heldout_by_root.tsv',
             'ntuples/energy_ml_stage146/event_records.json.gz']
    with tarfile.open(package, 'w:gz') as archive:
        for name in files:
            archive.add(ROOT/name, arcname=name)
    SPOOL.mkdir(parents=True, exist_ok=True)
    (SPOOL/'logs').mkdir(exist_ok=True)
    worker = SPOOL/f'worker_{stamp}.sh'
    worker.write_text('''#!/usr/bin/env bash
set -eo pipefail
stage147_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage147.XXXXXX")
tar -xzf energy-ml-stage147.tar.gz -C "$stage147_work"
cd "$stage147_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
stage147_status=0
/usr/bin/time -v -o workbook/stage147_energy_ml/control_time.txt python -u ml/stage147_track_control.py || stage147_status=$?
printf '%s\\n' "$stage147_status" > workbook/stage147_energy_ml/control_exitcode.txt
tar -czf result.tar.gz workbook/stage147_energy_ml
xrdcp --silent --force result.tar.gz root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage147/control_result.tar.gz
exit "$stage147_status"
''')
    descriptor = f'''universe = vanilla
initialdir = {SPOOL}
executable = /bin/bash
transfer_executable = False
arguments = {worker}
transfer_input_files = root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/{relative}
should_transfer_files = YES
transfer_output_files = ""
request_cpus = 1
request_memory = 4000MB
request_disk = 2000MB
max_retries = 0
+MaxRuntime = 86400
+PeriodicRemoveReason = "Stage147 CPU budget exceeded"
periodic_remove = (RemoteUserCpu + RemoteSysCpu) > 60
+NuMuStage = "energy-ml-stage147"
log = {SPOOL}/logs/$(ClusterId).$(ProcId).log
output = {SPOOL}/logs/$(ClusterId).$(ProcId).out
error = {SPOOL}/logs/$(ClusterId).$(ProcId).err
queue 1
'''
    submit = SPOOL/f'control_{stamp}.sub'
    submit.write_text(descriptor)
    result = subprocess.check_output(['condor_submit', '-terse', str(submit)], text=True).strip()
    (OUT/'control_submission.json').write_text(json.dumps(dict(result=result, phase='control', descriptor=descriptor,
        package=dict(path=relative, bytes=package.stat().st_size, files=files)), indent=2)+'\n')
    print(result)


if __name__ == '__main__':
    main()
