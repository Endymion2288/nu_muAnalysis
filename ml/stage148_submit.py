"""One immutable bounded support/transport/Ecal/audit sequence, never replace the parent."""
import argparse
import json
import subprocess
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage148_energy_ml'
SPOOL = Path.home()/'condor/nu_muAnalysis/stage148'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['support', 'transport', 'ecal', 'audit'])
    phase = parser.parse_args().phase
    assert not (OUT/f'{phase}_submission.json').exists()
    used = 0
    if phase != 'support':
        accounting = json.loads((OUT/'scheduler_accounting.json').read_text())
        assert accounting['live_N'] == 0
        used = accounting['total_CPU_s']
    if phase in ['transport', 'ecal']:
        assert json.loads((OUT/f'{phase}_admission.json').read_text())['admitted']
    remaining = 1000-used-(300 if phase == 'transport' else 0)
    assert remaining > 0
    files = ['workbook/stage148_energy_ml/protocol.json']
    if phase == 'support':
        files += ['ml/stage148_support.py', 'ntuples/energy_ml_stage131/production_cases.json.gz',
                  'ntuples/energy_ml_stage137/boundary_evidence.json.gz']
    elif phase == 'transport':
        files += [f'ml/{name}' for name in ['stage148_transport.py', 'stage142_pilot.py', 'stage131_pilot.py',
                  'stage142_simulate.py', 'stage131_hitscheck.py', 'stage142_control_general.py', 'stage142_native_general.py',
                  'stage138_response.hxx', 'stage129_rng.hxx', 'stage129_official.hxx', 'stage141_analog.hxx']]
        files += ['setup_env.sh', 'software/stage142/observer-runtime.tar.gz',
                  'ntuples/energy_ml_stage131/production_cases.json.gz', 'ntuples/energy_ml_stage131/parent_evidence.json.gz',
                  'ntuples/energy_ml_stage131/matched_input.npz', 'workbook/stage148_energy_ml/support.json',
                  'workbook/stage148_energy_ml/transport_admission.json']
    elif phase == 'ecal':
        index = json.loads((OUT/'support.json').read_text())['selected_indices'][0]
        files += [f'ml/{name}' for name in ['stage144_native.py', 'stage144_ecal.hxx', 'stage138_response.hxx',
                  'stage129_rng.hxx', 'stage129_official.hxx', 'stage141_analog.hxx']]
        files += ['setup_env.sh', 'ntuples/energy_ml_stage131/production_cases.json.gz',
                  'ntuples/energy_ml_stage131/matched_input.npz', f'ntuples/energy_ml_stage148/parent_{index}_qa_hits.json.gz',
                  f'workbook/stage148_energy_ml/parent_{index}_lineage.json', 'workbook/stage148_energy_ml/support.json',
                  'workbook/stage148_energy_ml/ecal_admission.json']
    else:
        files += ['ml/stage148_summarize.py', 'ml/stage148_window.py', 'ml/stage141_analog.hxx',
                  'setup_env.sh', 'workbook/stage148_energy_ml/support.json']
        indices = json.loads((OUT/'support.json').read_text())['selected_indices']
        for index in indices:
            files += [f'workbook/stage148_energy_ml/parent_{index}_{suffix}' for suffix in [
                      'report.json', 'hitscheck.json', 'source_control.json', 'source_analog_charge.tsv', 'summary.json', 'charge.tsv', 'lineage.json']]
            files += [f'ntuples/energy_ml_stage148/parent_{index}_{suffix}' for suffix in [
                      'qa_hits.json.gz', 'control.json.gz', 'ecal_control.json.gz']]
    stamp = time.time_ns()
    relative = f'software/stage148/{stamp}/energy-ml-stage148.tar.gz'
    package = ROOT/relative
    package.parent.mkdir(parents=True)
    with tarfile.open(package, 'w:gz') as archive:
        for name in files:
            archive.add(ROOT/name, arcname=name)
    SPOOL.mkdir(parents=True, exist_ok=True)
    (SPOOL/'logs').mkdir(exist_ok=True)
    worker = SPOOL/f'worker_{stamp}.sh'
    worker.write_bytes((ROOT/'AnalysisZipFramework/submission/run_ml_stage148.sh').read_bytes())
    descriptor = f'''universe = vanilla
initialdir = {SPOOL}
executable = /bin/bash
transfer_executable = False
arguments = {worker} {phase}
transfer_input_files = root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/{relative}
should_transfer_files = YES
transfer_output_files = ""
request_cpus = {4 if phase in ['transport', 'ecal'] else 1}
request_memory = {12000 if phase in ['transport', 'ecal'] else 4000}MB
request_disk = 8000MB
max_retries = 0
+MaxRuntime = 86400
+PeriodicRemoveReason = "Stage148 CPU budget or reserved Ecal allowance reached"
periodic_remove = (RemoteUserCpu + RemoteSysCpu) > {remaining}
+NuMuStage = "energy-ml-stage148"
log = {SPOOL}/logs/$(ClusterId).$(ProcId).log
output = {SPOOL}/logs/$(ClusterId).$(ProcId).out
error = {SPOOL}/logs/$(ClusterId).$(ProcId).err
queue 1
'''
    submit = SPOOL/f'{phase}_{stamp}.sub'
    submit.write_text(descriptor)
    result = subprocess.check_output(['condor_submit', '-terse', str(submit)], text=True).strip()
    (OUT/f'{phase}_submission.json').write_text(json.dumps(dict(result=result, phase=phase, descriptor=descriptor,
        remaining_CPU_s=remaining, package=dict(path=relative, bytes=package.stat().st_size, files=files)), indent=2)+'\n')
    print(result)


if __name__ == '__main__':
    main()
