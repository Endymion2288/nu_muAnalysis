"""Single-CPU immutable packages and cumulative native/score accounting."""
import argparse
import json
import subprocess
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage146_energy_ml'
SPOOL = Path.home()/'condor/nu_muAnalysis/stage146'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['pilot', 'full', 'score'])
    phase = parser.parse_args().phase
    assert not (OUT/f'{phase}_submission.json').exists()
    used = 0
    if phase != 'pilot':
        accounting = json.loads((OUT/'scheduler_accounting.json').read_text())
        assert accounting['live_N'] == 0
        used = accounting['total_CPU_s']
    if phase == 'full':
        assert json.loads((OUT/'full_admission.json').read_text())['admitted']
    remaining = 300-used
    assert remaining > 0
    stamp = time.time_ns()
    relative = f'software/stage146/{stamp}/energy-ml-stage146.tar.gz'
    package = ROOT/relative
    package.parent.mkdir(parents=True)
    files = ['setup_env.sh', 'ml/stage146_native.py', 'workbook/stage146_energy_ml/protocol.json']
    if phase == 'full':
        files.append('workbook/stage146_energy_ml/full_admission.json')
    if phase == 'score':
        files += ['ml/stage146_score.py', 'ml/stage145_mu_joint.py', 'workbook/stage145_energy_ml/models.json',
                  'workbook/stage145_energy_ml/protocol.json', 'workbook/stage145_energy_ml/heldout.tsv',
                  'workbook/stage146_energy_ml/full_roots.json.gz']
    with tarfile.open(package, 'w:gz') as archive:
        for name in files:
            archive.add(ROOT/name, arcname=name)
    SPOOL.mkdir(parents=True, exist_ok=True)
    (SPOOL/'logs').mkdir(exist_ok=True)
    worker = SPOOL/f'worker_{stamp}.sh'
    worker.write_bytes((ROOT/'AnalysisZipFramework/submission/run_ml_stage146.sh').read_bytes())
    descriptor = f'''universe = vanilla
initialdir = {SPOOL}
executable = /bin/bash
transfer_executable = False
arguments = {worker} {phase}
transfer_input_files = root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/{relative}
should_transfer_files = YES
transfer_output_files = ""
request_cpus = 1
request_memory = 4000MB
request_disk = 4000MB
max_retries = 0
+MaxRuntime = 86400
+PeriodicRemoveReason = "Stage146 cumulative CPU budget exceeded"
periodic_remove = (RemoteUserCpu + RemoteSysCpu) > {remaining}
+NuMuStage = "energy-ml-stage146"
log = {SPOOL}/logs/$(ClusterId).$(ProcId).log
output = {SPOOL}/logs/$(ClusterId).$(ProcId).out
error = {SPOOL}/logs/$(ClusterId).$(ProcId).err
queue 1
'''
    submit = SPOOL/f'{phase}_{stamp}.sub'
    submit.write_text(descriptor)
    result = subprocess.check_output(['condor_submit', '-terse', str(submit)], text=True).strip()
    (OUT/f'{phase}_submission.json').write_text(json.dumps(dict(result=result, phase=phase, descriptor=descriptor,
        package=dict(path=relative, bytes=package.stat().st_size, files=files)), indent=2)+'\n')
    print(result)


if __name__ == '__main__':
    main()
