"""Submit the single bounded cached-input experiment, with immutable payload."""
import json
import subprocess
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage142_energy_ml'
SPOOL = Path.home()/'condor/nu_muAnalysis/stage142'

def main():
    assert not (OUT/'control_submission.json').exists(), 'Inspect existing job before resubmission'
    assert not (OUT/'source_control.json').exists(), 'Control already started'
    stamp = time.time_ns()
    relative = f'software/stage142/{stamp}/energy-ml-stage142.tar.gz'
    package = ROOT/relative
    package.parent.mkdir(parents=True)
    (ROOT/'ntuples/energy_ml_stage142').mkdir(exist_ok=True)
    assert json.loads((OUT/'preflight_report.json').read_text())['successful']
    files = ['ml/stage142_native.py','ml/stage142_control.py',
             'ml/stage138_response.hxx','ml/stage129_rng.hxx','ml/stage129_official.hxx',
             'ml/stage141_analog.hxx','setup_env.sh',
             'workbook/stage142_energy_ml/protocol.json',
             'workbook/stage142_energy_ml/source_control_protocol.json',
             'workbook/stage142_energy_ml/preflight_report.json',
             'workbook/stage142_energy_ml/parent_50_lineage.json',
             'ntuples/energy_ml_stage142/parent_50_qa_hits.json.gz',
             'ntuples/energy_ml_stage131/pilot_private_rng_states.json.gz',
             'ntuples/energy_ml_stage131/matched_input.npz']
    with tarfile.open(package, 'w:gz') as archive:
        for name in files:
            archive.add(ROOT/name, arcname=name)
    SPOOL.mkdir(parents=True, exist_ok=True)
    (SPOOL/'logs').mkdir(exist_ok=True)
    worker = SPOOL/f'worker_{stamp}.sh'
    worker.write_bytes((ROOT/'AnalysisZipFramework/submission/run_ml_stage142_control.sh').read_bytes())
    descriptor = f'''universe = vanilla
initialdir = {SPOOL}
executable = /bin/bash
transfer_executable = False
arguments = {worker}
transfer_input_files = root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/{relative}
should_transfer_files = YES
transfer_output_files = ""
request_cpus = 4
request_memory = 12000MB
request_disk = 2000MB
max_retries = 0
+MaxRuntime = 600
+PeriodicRemoveReason = "Stage142 cumulative CPU budget 600 seconds exceeded"
periodic_remove = (RemoteUserCpu + RemoteSysCpu) > 600
+NuMuStage = "energy-ml-stage142"
log = {SPOOL}/logs/$(ClusterId).$(ProcId).log
output = {SPOOL}/logs/$(ClusterId).$(ProcId).out
error = {SPOOL}/logs/$(ClusterId).$(ProcId).err
queue 1
'''
    submit = SPOOL/f'analysis_{stamp}.sub'
    submit.write_text(descriptor)
    result = subprocess.check_output(['condor_submit', '-terse', str(submit)], text=True).strip()
    record = dict(result=result, phase='source_control', indices=[0], cpus=4,
                  descriptor=descriptor, package=dict(path=relative,
                  bytes=package.stat().st_size, files=files),
                  frozen_before_new_risks=True, total_fit_budget=0)
    (OUT/'control_submission.json').write_text(json.dumps(record, indent=2)+'\n')
    print(result)

if __name__ == '__main__':
    main()
