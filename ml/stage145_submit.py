"""One frozen two-source control; four CPUs, no new particle transport."""
import argparse
import json
import subprocess
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage145_energy_ml'
SPOOL = Path.home()/'condor/nu_muAnalysis/stage145'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['control','typedqa'],default='control');phase=parser.parse_args().phase
    assert not (OUT/f'{phase}_submission.json').exists()
    used = json.loads((OUT/'scheduler_accounting.json').read_text())['total_CPU_s'] if (OUT/'scheduler_accounting.json').exists() else 0
    remaining = 120-used
    assert remaining > 0
    stamp = time.time_ns()
    relative = f'software/stage145/{stamp}/energy-ml-stage145.tar.gz'
    package = ROOT/relative
    package.parent.mkdir(parents=True)
    (ROOT/'ntuples/energy_ml_stage145').mkdir(exist_ok=True)
    files = ['ml/stage145_mu_joint.py', 'workbook/stage145_energy_ml/protocol.json']
    with tarfile.open(package, 'w:gz') as archive:
        for name in files:
            archive.add(ROOT/name, arcname=name)
    SPOOL.mkdir(parents=True, exist_ok=True)
    (SPOOL/'logs').mkdir(exist_ok=True)
    worker = SPOOL/f'worker_{stamp}.sh'
    worker.write_text('''#!/usr/bin/env bash
set -eo pipefail
stage145_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage145.XXXXXX")
tar -xzf energy-ml-stage145.tar.gz -C "$stage145_work"
cd "$stage145_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
stage145_status=0
/usr/bin/time -v -o workbook/stage145_energy_ml/PHASE_time.txt python -u ml/stage145_mu_joint.py || stage145_status=$?
printf '%s\\n' "$stage145_status" > workbook/stage145_energy_ml/PHASE_exitcode.txt
tar -czf result.tar.gz workbook/stage145_energy_ml
xrdcp --silent --force result.tar.gz root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage145/PHASE_result.tar.gz
exit "$stage145_status"
'''.replace('PHASE',phase))
    descriptor = f'''universe = vanilla
initialdir = {SPOOL}
executable = /bin/bash
transfer_executable = False
arguments = {worker}
transfer_input_files = root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/{relative}
should_transfer_files = YES
transfer_output_files = ""
request_cpus = 4
request_memory = 6000MB
request_disk = 2000MB
max_retries = 0
+MaxRuntime = 86400
+PeriodicRemoveReason = "Stage145 cumulative CPU budget exceeded"
periodic_remove = (RemoteUserCpu + RemoteSysCpu) > {remaining}
+NuMuStage = "energy-ml-stage145"
log = {SPOOL}/logs/$(ClusterId).$(ProcId).log
output = {SPOOL}/logs/$(ClusterId).$(ProcId).out
error = {SPOOL}/logs/$(ClusterId).$(ProcId).err
queue 1
'''
    submit = SPOOL/f'{phase}_{stamp}.sub'
    submit.write_text(descriptor)
    result = subprocess.check_output(['condor_submit', '-terse', str(submit)], text=True).strip()
    (OUT/f'{phase}_submission.json').write_text(json.dumps(dict(result=result, phase=phase, cpus=4,
        descriptor=descriptor, package=dict(path=relative, bytes=package.stat().st_size, files=files)), indent=2)+'\n')
    print(result)


if __name__ == '__main__':
    main()
