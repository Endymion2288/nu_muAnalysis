"""Submit one admitted parent, with a stage-wide remaining CPU budget."""
import argparse
import json
import subprocess
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage143_energy_ml'
SPOOL = Path.home()/'condor/nu_muAnalysis/stage143'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('index', type=int)
    index = parser.parse_args().index
    admission = json.loads((OUT/f'parent_{index}_admission.json').read_text())
    assert admission['admitted']
    assert not (OUT/f'parent_{index}_submission.json').exists()
    accounting = json.loads((OUT/'scheduler_accounting.json').read_text())
    assert accounting['live_N'] == 0
    remaining = 1000 - accounting['total_CPU_s']
    assert remaining > 0
    stamp = time.time_ns()
    relative = f'software/stage143/{stamp}/energy-ml-stage143.tar.gz'
    package = ROOT/relative
    package.parent.mkdir(parents=True)
    files = [f'ml/{name}' for name in [
        'stage143_response.py', 'stage142_pilot.py', 'stage131_pilot.py',
        'stage142_simulate.py', 'stage131_hitscheck.py',
        'stage142_native_general.py', 'stage142_control_general.py',
        'stage138_response.hxx', 'stage129_rng.hxx', 'stage129_official.hxx',
        'stage141_analog.hxx']]
    files += ['setup_env.sh', 'software/stage142/observer-runtime.tar.gz',
              'ntuples/energy_ml_stage131/production_cases.json.gz',
              'ntuples/energy_ml_stage131/parent_evidence.json.gz',
              'ntuples/energy_ml_stage131/matched_input.npz',
              'workbook/stage143_energy_ml/protocol.json',
              'workbook/stage143_energy_ml/support.json',
              f'workbook/stage143_energy_ml/parent_{index}_admission.json']
    with tarfile.open(package, 'w:gz') as archive:
        for name in files:
            archive.add(ROOT/name, arcname=name)
    worker = SPOOL/f'worker_response_{stamp}.sh'
    worker.write_bytes((ROOT/'AnalysisZipFramework/submission/run_ml_stage143_response.sh').read_bytes())
    descriptor = f'''universe = vanilla
initialdir = {SPOOL}
executable = /bin/bash
transfer_executable = False
arguments = {worker} {index}
transfer_input_files = root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/{relative}
should_transfer_files = YES
transfer_output_files = ""
request_cpus = 4
request_memory = 12000MB
request_disk = 8000MB
max_retries = 0
+MaxRuntime = 86400
+PeriodicRemoveReason = "Stage143 remaining cumulative CPU budget exceeded"
periodic_remove = (RemoteUserCpu + RemoteSysCpu) > {remaining}
+NuMuStage = "energy-ml-stage143"
log = {SPOOL}/logs/$(ClusterId).$(ProcId).log
output = {SPOOL}/logs/$(ClusterId).$(ProcId).out
error = {SPOOL}/logs/$(ClusterId).$(ProcId).err
queue 1
'''
    submit = SPOOL/f'parent_{index}_{stamp}.sub'
    submit.write_text(descriptor)
    result = subprocess.check_output(['condor_submit', '-terse', str(submit)], text=True).strip()
    record = dict(result=result, phase='response', index=index, cpus=4,
                  remaining_CPU_budget_s=remaining, descriptor=descriptor,
                  package=dict(path=relative, bytes=package.stat().st_size, files=files))
    (OUT/f'parent_{index}_submission.json').write_text(json.dumps(record, indent=2)+'\n')
    print(result)


if __name__ == '__main__':
    main()
