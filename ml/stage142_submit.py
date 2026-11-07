"""Submit the bounded minimal new-instrumentation experiment, with immutable payload."""
import argparse
import json
import subprocess
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage142_energy_ml'
SPOOL = Path.home()/'condor/nu_muAnalysis/stage142'

def main():
    parser=argparse.ArgumentParser();parser.add_argument("phase",choices=["preflight","pilot","audit"]);phase=parser.parse_args().phase
    if phase=="pilot":
        admission=json.loads((OUT/"pilot_admission.json").read_text());assert admission["admitted"]
    assert not (OUT/f'{phase}_submission.json').exists(), 'Inspect existing job before resubmission'
    assert phase!='preflight' or not (OUT/'preflight_results.json').exists(), 'Inspect existing results before repeating'
    stamp = time.time_ns()
    relative = f'software/stage142/{stamp}/energy-ml-stage142.tar.gz'
    package = ROOT/relative
    package.parent.mkdir(parents=True)
    (ROOT/'ntuples/energy_ml_stage142').mkdir(exist_ok=True)
    files = [str(p.relative_to(ROOT)) for p in (ROOT/'ml').glob('*.py')]
    files += ['ml/configs', 'workbook/stage142_energy_ml/protocol.json',
              'ntuples/energy_ml_stage131/production_cases.json.gz',
              'ntuples/energy_ml_stage131/parent_evidence.json.gz',
              'ml/stage142_observer','ml/stage138_response.hxx','ml/stage129_rng.hxx','ml/stage129_official.hxx','ml/stage141_analog.hxx','ntuples/energy_ml_stage135/parent_50_qa_hits.json.gz','ntuples/energy_ml_stage131/pilot_private_rng_states.json.gz','ntuples/energy_ml_stage131/matched_input.npz','setup_env.sh']
    if phase=='pilot':files+=['software/stage142/observer-runtime.tar.gz','workbook/stage142_energy_ml/pilot_admission.json']
    if phase=='audit':
        assert (OUT/'pilot_results.json').exists()
        files += [str(p.relative_to(ROOT)) for p in OUT.glob('parent_*_report.json')]
        files += [str(p.relative_to(ROOT)) for p in OUT.glob('parent_*_lineage.json')]
        files += [str(p.relative_to(ROOT)) for p in OUT.glob('*source_control.json')]
        files += [str(p.relative_to(ROOT)) for p in OUT.glob('*source_analog_charge.tsv')]
        files += ['workbook/stage142_energy_ml/preflight_report.json']
        files += [str(p.relative_to(ROOT)) for p in (ROOT/'ntuples/energy_ml_stage142').glob('*.json.gz')]
    with tarfile.open(package, 'w:gz') as archive:
        for name in files:
            archive.add(ROOT/name, arcname=name)
    SPOOL.mkdir(parents=True, exist_ok=True)
    (SPOOL/'logs').mkdir(exist_ok=True)
    worker = SPOOL/f'worker_{stamp}.sh'
    worker.write_bytes((ROOT/'AnalysisZipFramework/submission/run_ml_stage142.sh').read_bytes())
    descriptor = f'''universe = vanilla
initialdir = {SPOOL}
executable = /bin/bash
transfer_executable = False
arguments = {worker} {phase}
transfer_input_files = root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/{relative}
should_transfer_files = YES
transfer_output_files = ""
request_cpus = 4
request_memory = 12000MB
request_disk = 8000MB
max_retries = 0
+MaxRuntime = 86400
+PeriodicRemoveReason = "Stage142 cumulative CPU budget 3000 seconds exceeded"
periodic_remove = (RemoteUserCpu + RemoteSysCpu) > 3000
+NuMuStage = "energy-ml-stage142"
log = {SPOOL}/logs/$(ClusterId).$(ProcId).log
output = {SPOOL}/logs/$(ClusterId).$(ProcId).out
error = {SPOOL}/logs/$(ClusterId).$(ProcId).err
queue 1
'''
    submit = SPOOL/f'{phase}_{stamp}.sub'
    submit.write_text(descriptor)
    result = subprocess.check_output(['condor_submit', '-terse', str(submit)], text=True).strip()
    record = dict(result=result, phase=phase, indices=[0], cpus=4,
                  descriptor=descriptor, package=dict(path=relative,
                  bytes=package.stat().st_size, files=files),
                  frozen_before_new_risks=True, total_fit_budget=0)
    (OUT/f'{phase}_submission.json').write_text(json.dumps(record, indent=2)+'\n')
    print(result)

if __name__ == '__main__':
    main()
