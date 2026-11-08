"""Fixed-prefix Ecal response/time-window control with measured pilot admission."""
import argparse
import json
import subprocess
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage152_energy_ml'
SPOOL = Path.home()/'condor/nu_muAnalysis/stage152'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['pilot', 'admission', 'full', 'audit'])
    phase = parser.parse_args().phase
    assert not (OUT/f'{phase}_submission.json').exists()
    plan = json.loads((OUT/'protocol.json').read_text())
    used = 0
    if phase != 'pilot':
        accounting = json.loads((OUT/'scheduler_accounting.json').read_text())
        assert accounting['live_N'] == 0
        used = accounting['total_CPU_s']
    if phase == 'full':
        assert json.loads((OUT/'full_admission.json').read_text())['admitted']
    allowance = (plan['resources']['pilot_CPU_allowance_s'] if phase == 'pilot'
                 else plan['resources']['CPU_budget_s']-used-(100 if phase == 'full' else 0))
    assert allowance > 0
    files = ['setup_env.sh', 'workbook/stage152_energy_ml/protocol.json',
             'ntuples/energy_ml_stage151/event_records.json.gz']
    files += [f'ml/{name}' for name in ['stage152_native.py', 'stage152_support.hxx', 'stage152_audit.py',
        'stage138_response.hxx', 'stage129_rng.hxx', 'stage129_official.hxx',
        'stage144_ecal.hxx', 'stage141_analog.hxx']]
    if phase != 'pilot':
        files += ['workbook/stage152_energy_ml/pilot_summary.json',
                  'workbook/stage152_energy_ml/pilot_time.txt',
                  'workbook/stage152_energy_ml/pilot_channels.tsv',
                  'ntuples/energy_ml_stage152/pilot.json.gz']
    if phase in ['admission', 'audit']:
        files += ['workbook/stage152_energy_ml/scheduler_accounting.json']
    if (OUT/'full_admission.json').exists():
        files += ['workbook/stage152_energy_ml/full_admission.json']
    if phase == 'audit' and (OUT/'full_summary.json').exists():
        files += ['workbook/stage152_energy_ml/full_summary.json',
                  'workbook/stage152_energy_ml/full_time.txt',
                  'workbook/stage152_energy_ml/full_channels.tsv',
                  'ntuples/energy_ml_stage152/full.json.gz']
    stamp = time.time_ns()
    relative = f'software/stage152/{stamp}/energy-ml-stage152.tar.gz'
    package = ROOT/relative
    package.parent.mkdir(parents=True)
    with tarfile.open(package, 'w:gz') as archive:
        for name in files:
            archive.add(ROOT/name, arcname=name)
    SPOOL.mkdir(parents=True, exist_ok=True)
    (SPOOL/'logs').mkdir(exist_ok=True)
    worker = SPOOL/f'worker_{stamp}.sh'
    worker.write_bytes((ROOT/'AnalysisZipFramework/submission/run_ml_stage152.sh').read_bytes())
    descriptor = f'''universe = vanilla
initialdir = {SPOOL}
executable = /bin/bash
transfer_executable = False
arguments = {worker.name} {phase}
transfer_input_files = {worker}, root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/{relative}
should_transfer_files = YES
transfer_output_files = ""
request_cpus = 4
request_memory = 12000MB
request_disk = 8000MB
max_retries = 0
+MaxRuntime = 86400
+PeriodicRemoveReason = "Stage152 cumulative CPU allowance"
periodic_remove = (RemoteUserCpu + RemoteSysCpu) > {allowance}
+NuMuStage = "energy-ml-stage152"
log = {SPOOL}/logs/$(ClusterId).$(ProcId).log
output = {SPOOL}/logs/$(ClusterId).$(ProcId).out
error = {SPOOL}/logs/$(ClusterId).$(ProcId).err
queue 1
'''
    path = SPOOL/f'{phase}_{stamp}.sub'
    path.write_text(descriptor)
    result = subprocess.check_output(['condor_submit', '-terse', str(path)], text=True).strip()
    (OUT/f'{phase}_submission.json').write_text(json.dumps(dict(result=result, phase=phase,
        descriptor=descriptor, CPU_allowance_s=allowance,
        package=dict(path=relative, bytes=package.stat().st_size, files=files)), indent=2)+'\n')
    print(result)


if __name__ == '__main__':
    main()
