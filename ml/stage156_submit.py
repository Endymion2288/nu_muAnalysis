"""Frozen native spatial muon control with measured physical-pilot admission."""
import argparse
import json
import subprocess
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage156_energy_ml'
SPOOL = Path.home()/'condor/nu_muAnalysis/stage156'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['pilot', 'admission', 'admission_retry', 'full', 'audit'])
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
                 else plan['resources']['CPU_budget_s']-used-(plan['resources']['audit_reserve_CPU_s'] if phase == 'full' else 0))
    assert allowance > 0
    files = ['setup_env.sh', 'workbook/stage156_energy_ml/protocol.json',
             'ntuples/energy_ml_stage146/event_records.json.gz']
    files += [f'ml/{name}' for name in ['stage156_pipeline.py', 'stage149_digitize.py', 'stage149_reco.py',
        'stage156_native.py', 'stage149_native.hxx', 'stage149_extract.py', 'stage129_rng.hxx', 'stage124_native.hxx',
        'stage155_native.hxx', 'stage153_native.hxx', 'stage155_schema.py', 'stage156_geometry.py', 'stage156_audit.py']]
    files += ['ntuples/energy_ml_stage149/event_records.json.gz']
    if phase != 'pilot':
        files += ['workbook/stage156_energy_ml/pilot', 'ntuples/energy_ml_stage156/pilot']
    if phase in ['admission', 'admission_retry', 'audit']:
        files += ['workbook/stage156_energy_ml/scheduler_accounting.json']
    if (OUT/'full_admission.json').exists():
        files += ['workbook/stage156_energy_ml/full_admission.json']
    if phase in ['audit'] and (OUT/'full').exists():
        files += ['workbook/stage156_energy_ml/full', 'ntuples/energy_ml_stage156/full']
    stamp = time.time_ns()
    relative = f'software/stage156/{stamp}/energy-ml-stage156.tar.gz'
    package = ROOT/relative
    package.parent.mkdir(parents=True)
    with tarfile.open(package, 'w:gz') as archive:
        for name in files:
            archive.add(ROOT/name, arcname=name)
    SPOOL.mkdir(parents=True, exist_ok=True)
    (SPOOL/'logs').mkdir(exist_ok=True)
    worker = SPOOL/f'worker_{stamp}.sh'
    worker.write_bytes((ROOT/'AnalysisZipFramework/submission/run_ml_stage156.sh').read_bytes())
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
+PeriodicRemoveReason = "Stage156 cumulative CPU allowance"
periodic_remove = (RemoteUserCpu + RemoteSysCpu) > {allowance}
+NuMuStage = "energy-ml-stage156"
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
