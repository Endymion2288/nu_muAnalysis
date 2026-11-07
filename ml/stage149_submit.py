"""Submit one frozen physical pilot, followed only by measured-cost admission."""
import argparse
import json
import subprocess
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage149_energy_ml'
SPOOL = Path.home()/'condor/nu_muAnalysis/stage149'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['pilot', 'pilot_retry', 'admission', 'full', 'full_retry', 'audit'])
    phase = parser.parse_args().phase
    assert not (OUT/f'{phase}_submission.json').exists()
    plan = json.loads((OUT/'protocol.json').read_text())
    used = 0
    if phase != 'pilot':
        accounting = json.loads((OUT/'scheduler_accounting.json').read_text())
        assert accounting['live_N'] == 0
        used = accounting['total_CPU_s']
    if phase in ['full', 'full_retry']:
        admission = json.loads((OUT/'full_admission.json').read_text())
        assert admission['admitted']
    allowance = (plan['resources']['pilot_CPU_allowance_s']-used if phase in ['pilot', 'pilot_retry']
                 else 3000-used-(100 if phase in ['full', 'full_retry'] else 0))
    assert allowance > 0
    files = ['setup_env.sh', 'workbook/stage149_energy_ml/protocol.json',
             'ntuples/energy_ml_stage146/event_records.json.gz']
    files += [f'ml/{name}' for name in ['stage149_pipeline.py', 'stage149_digitize.py', 'stage149_reco.py',
        'stage149_native.py', 'stage149_native.hxx', 'stage149_extract.py', 'stage129_rng.hxx', 'stage124_native.hxx',
        'stage149_audit.py']]
    if phase in ['full', 'full_retry', 'admission', 'audit']:
        files += ['workbook/stage149_energy_ml/pilot', 'ntuples/energy_ml_stage149/pilot']
    if (OUT/'full_admission.json').exists():
        files += ['workbook/stage149_energy_ml/full_admission.json']
    if phase == 'audit' and (OUT/'full').exists():
        files += ['workbook/stage149_energy_ml/full', 'ntuples/energy_ml_stage149/full']
    if phase in ['admission', 'audit']:
        files += ['workbook/stage149_energy_ml/scheduler_accounting.json']
    stamp = time.time_ns()
    relative = f'software/stage149/{stamp}/energy-ml-stage149.tar.gz'
    package = ROOT/relative
    package.parent.mkdir(parents=True)
    with tarfile.open(package, 'w:gz') as archive:
        for name in files:
            archive.add(ROOT/name, arcname=name)
    SPOOL.mkdir(parents=True, exist_ok=True)
    (SPOOL/'logs').mkdir(exist_ok=True)
    worker = SPOOL/f'worker_{stamp}.sh'
    worker.write_bytes((ROOT/'AnalysisZipFramework/submission/run_ml_stage149.sh').read_bytes())
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
+PeriodicRemoveReason = "Stage149 cumulative CPU allowance"
periodic_remove = (RemoteUserCpu + RemoteSysCpu) > {allowance}
+NuMuStage = "energy-ml-stage149"
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
