"""Bounded Ecal-only closure; no G4 or C++ build, immutable cache payload."""
import argparse
import json
import subprocess
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage144_energy_ml'
SPOOL = Path.home()/'condor/nu_muAnalysis/stage144'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['preflight', 'preflight_repair', 'preflight_rngmap', 'preflight_idheader', 'pilot', 'audit'])
    phase = parser.parse_args().phase
    assert not (OUT/f'{phase}_submission.json').exists()
    if phase == 'pilot':
        assert json.loads((OUT/'pilot_admission.json').read_text())['admitted']
    accounting = json.loads((OUT/'scheduler_accounting.json').read_text())
    assert accounting['live_N'] == 0
    remaining = 600-accounting['total_CPU_s']
    assert remaining > 0
    stamp = time.time_ns()
    relative = f'software/stage144/{stamp}/energy-ml-stage144.tar.gz'
    package = ROOT/relative
    package.parent.mkdir(parents=True)
    (ROOT/'ntuples/energy_ml_stage144').mkdir(exist_ok=True)
    files = [f'ml/{name}' for name in ['stage144_native.py', 'stage144_ecal.hxx', 'stage144_driver.py',
                                      'stage138_response.hxx', 'stage129_rng.hxx', 'stage129_official.hxx', 'stage141_analog.hxx']]
    files += ['setup_env.sh', 'workbook/stage144_energy_ml/protocol.json',
              'ntuples/energy_ml_stage142/event_records.json.gz',
              'ntuples/energy_ml_stage131/production_cases.json.gz',
              'ntuples/energy_ml_stage131/pilot_private_rng_states.json.gz',
              'ntuples/energy_ml_stage131/matched_input.npz']
    if phase == 'pilot':
        files += ['workbook/stage144_energy_ml/pilot_admission.json']
    if phase == 'audit':
        files = ['ml/stage144_summarize.py', 'workbook/stage144_energy_ml/protocol.json']
        for index in [50, 6, 2, 0]:
            files += [f'workbook/stage144_energy_ml/parent_{index}_{suffix}' for suffix in ['summary.json', 'charge.tsv']]
    with tarfile.open(package, 'w:gz') as archive:
        for name in files:
            archive.add(ROOT/name, arcname=name)
    SPOOL.mkdir(parents=True, exist_ok=True)
    (SPOOL/'logs').mkdir(exist_ok=True)
    worker = SPOOL/f'worker_{stamp}.sh'
    worker.write_bytes((ROOT/'AnalysisZipFramework/submission/run_ml_stage144.sh').read_bytes())
    descriptor = f'''universe = vanilla
initialdir = {SPOOL}
executable = /bin/bash
transfer_executable = False
arguments = {worker} {phase}
transfer_input_files = root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/{relative}
should_transfer_files = YES
transfer_output_files = ""
request_cpus = {1 if phase == 'audit' else 4}
request_memory = {3000 if phase == 'audit' else 12000}MB
request_disk = 4000MB
max_retries = 0
+MaxRuntime = 86400
+PeriodicRemoveReason = "Stage144 remaining cumulative CPU budget exceeded"
periodic_remove = (RemoteUserCpu + RemoteSysCpu) > {remaining}
+NuMuStage = "energy-ml-stage144"
log = {SPOOL}/logs/$(ClusterId).$(ProcId).log
output = {SPOOL}/logs/$(ClusterId).$(ProcId).out
error = {SPOOL}/logs/$(ClusterId).$(ProcId).err
queue 1
'''
    submit = SPOOL/f'{phase}_{stamp}.sub'
    submit.write_text(descriptor)
    result = subprocess.check_output(['condor_submit', '-terse', str(submit)], text=True).strip()
    (OUT/f'{phase}_submission.json').write_text(json.dumps(dict(result=result, phase=phase, cpus=1 if phase == 'audit' else 4,
        descriptor=descriptor, package=dict(path=relative, bytes=package.stat().st_size, files=files)), indent=2)+'\n')
    print(result)


if __name__ == '__main__':
    main()
