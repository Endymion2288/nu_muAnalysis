"""Frozen native spatial muon control with measured physical-pilot admission."""
import argparse
import json
import subprocess
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage157_energy_ml'
SPOOL = Path.home()/'condor/nu_muAnalysis/stage157'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['pilot', 'pilot_retry', 'admission', 'audit', 'audit_retry']+[f'batch_{i:02d}' for i in range(16)])
    phase = parser.parse_args().phase
    assert not (OUT/f'{phase}_submission.json').exists()
    plan = json.loads((OUT/'protocol.json').read_text())
    used = 0
    if phase != 'pilot':
        accounting = json.loads((OUT/'scheduler_accounting.json').read_text())
        if not phase.startswith('batch_'): assert accounting['live_N'] == 0
        used = accounting['total_CPU_s']
    if phase.startswith('batch_'):
        assert json.loads((OUT/'full_admission.json').read_text())['admitted']
    allowance = (plan['resources']['pilot_CPU_allowance_s']-used if phase in ['pilot','pilot_retry']
                 else plan['resources']['CPU_budget_s']-used-(plan['resources']['audit_reserve_CPU_s'] if phase.startswith('batch_') else 0))
    assert allowance > 0
    files = ['setup_env.sh', 'workbook/stage157_energy_ml/protocol.json',
             'ntuples/energy_ml_stage146/event_records.json.gz']
    files += [f'ml/{name}' for name in ['stage157_driver.py','stage157_pipeline.py','stage157_digitize.py',
        'stage149_reco.py','stage157_native.py','stage157_extract.py','stage157_audit.py','stage149_native.hxx',
        'stage157_compact.py','stage157_response.py','stage157_plot.py','stage157_full.py','stage157_verify.py','stage129_rng.hxx','stage124_native.hxx','stage155_native.hxx','stage153_native.hxx','stage155_schema.py','stage156_geometry.py']]
    files += ['ntuples/energy_ml_stage156/event_records.json.gz']
    if phase == 'admission' or phase.startswith('audit'):
        files += ['workbook/stage157_energy_ml/chains','ntuples/energy_ml_stage157/chains',
                  'workbook/stage157_energy_ml/scheduler_accounting.json']
    if phase.startswith('audit'):
        drivers = sorted(OUT.glob('batch_*_driver.json'))
        assert len(drivers) == 16, 'Collect all batch timing reports before the final audit'
        files += [str(p.relative_to(ROOT)) for p in drivers]
    if phase.startswith('batch_') or phase.startswith('audit'):
        files += ['workbook/stage157_energy_ml/full_admission.json']
    if phase == 'batch_00': files += ['ntuples/energy_ml_stage157/pilot_reference.json.gz']
    if phase.startswith('batch_'):
        assert accounting['live_N'] < 4
        assert not accounting.get('unresolved_ids', [])
        # Sixteen disjoint budgets leave the frozen audit reserve, even if all
        # allocations were consumed. Pilot/admission are already charged.
        admission = json.loads((OUT/'full_admission.json').read_text())
        allowance = int((60000-admission['already_used_scheduler_CPU_s']-500-100)/16)
        assert allowance > 0
    if phase.startswith('audit'):
        prior_ids={int(json.loads(p.read_text())['result'].split('.')[0]) for p in OUT.glob('audit*_submission.json')}
        prior_cpu=sum(r.get('RemoteUserCpu',0)+r.get('RemoteSysCpu',0) for r in accounting['jobs'] if r['ClusterId'] in prior_ids)
        allowance = min(allowance, plan['resources']['audit_reserve_CPU_s']-prior_cpu)
        assert allowance > 0
    stamp = time.time_ns()
    relative = f'software/stage157/{stamp}/energy-ml-stage157.tar.gz'
    package = ROOT/relative
    package.parent.mkdir(parents=True)
    with tarfile.open(package, 'w:gz') as archive:
        for name in files:
            archive.add(ROOT/name, arcname=name)
    SPOOL.mkdir(parents=True, exist_ok=True)
    (SPOOL/'logs').mkdir(exist_ok=True)
    worker = SPOOL/f'worker_{stamp}.sh'
    worker.write_bytes((ROOT/'AnalysisZipFramework/submission/run_ml_stage157.sh').read_bytes())
    descriptor = f'''universe = vanilla
initialdir = {SPOOL}
executable = /bin/bash
transfer_executable = False
arguments = {worker.name} {phase}
transfer_input_files = {worker}, root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/{relative}
should_transfer_files = YES
transfer_output_files = ""
request_cpus = 4
request_memory = 16000MB
request_disk = 12000MB
max_retries = 0
+MaxRuntime = 86400
+PeriodicRemoveReason = "Stage157 cumulative CPU allowance"
periodic_remove = (RemoteUserCpu + RemoteSysCpu) > {allowance}
+NuMuStage = "energy-ml-stage157"
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
