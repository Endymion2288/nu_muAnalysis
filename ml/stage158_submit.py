"""Immutable bounded packages, disjoint native CPU budgets and scoped submission."""
import argparse
import json
import subprocess
import tarfile
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage158_energy_ml'
SPOOL=Path.home()/'condor/nu_muAnalysis/stage158'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['pilot','admission','fit','validate','plot']+[f'batch_{i:02d}' for i in range(10)])
    phase=parser.parse_args().phase
    assert not (OUT/f'{phase}_submission.json').exists()
    plan=json.loads((OUT/'protocol.json').read_text());account=dict(total_CPU_s=0,live_N=0,unresolved_ids=[])
    if phase!='pilot':account=json.loads((OUT/'scheduler_accounting.json').read_text())
    assert not account['unresolved_ids']
    if not phase.startswith('batch_'):assert account['live_N']==0
    used=account['total_CPU_s']
    if phase=='pilot':allowance=1600
    elif phase.startswith('batch_'):
        admission=json.loads((OUT/'full_admission.json').read_text());assert admission['admitted']
        assert account['live_N']<4
        allowance=int((30000-admission['already_used_scheduler_CPU_s']-1000-100)/10)
    elif phase=='admission':allowance=100
    else:
        assert len(list(OUT.glob('batch_*_exitcode.txt')))==10
        allowance=min(1000,30000-used)
        if phase=='validate':
            fit_id=int(json.loads((OUT/'fit_submission.json').read_text())['result'].split('.')[0])
            spent=sum(r.get('RemoteUserCpu',0)+r.get('RemoteSysCpu',0) for r in account['jobs'] if r['ClusterId']==fit_id)
            allowance=min(allowance,1000-spent)
        if phase=='plot':
            assert json.loads((OUT/'validation_summary.json').read_text())['passed']
            scientific_ids={int(json.loads((OUT/f'{p}_submission.json').read_text())['result'].split('.')[0]) for p in ['fit','validate']}
            spent=sum(r.get('RemoteUserCpu',0)+r.get('RemoteSysCpu',0) for r in account['jobs'] if r['ClusterId'] in scientific_ids)
            allowance=min(allowance,1000-spent)
    assert 0<allowance<=30000-used
    files=['setup_env.sh','workbook/stage158_energy_ml/protocol.json',
        'workbook/stage124_energy_ml/native_contract.json','ntuples/energy_ml_stage119/old_input.npz',
        'ml/configs/audited_features.json','ml/audited_features.py','ml/stage155_native.hxx','ml/stage153_native.hxx',
        'ml/stage124_native.hxx','ml/stage155_schema.py','ml/stage156_geometry.py',
        'ml/stage119_curve_common.py','ml/stage119_reportcurve.py']
    files += [str(p.relative_to(ROOT)) for p in sorted((ROOT/'ml').glob('stage158_*.py'))]
    if phase=='admission':
        files+=['ntuples/energy_ml_stage158/pilot.json.gz','ntuples/energy_ml_stage158/repeat.json.gz',
            'ntuples/energy_ml_stage155/event_records.json.gz','workbook/stage158_energy_ml/pilot_summary.json',
            'workbook/stage158_energy_ml/pilot_time.txt','workbook/stage158_energy_ml/scheduler_accounting.json']
    if phase.startswith('batch_') or phase in ['fit','validate']:files+=['workbook/stage158_energy_ml/full_admission.json']
    if phase=='fit':
        files+=['ntuples/energy_ml_stage158','ntuples/energy_ml_stage158/pilot.json.gz',
                'ml/artifacts/stage87/predictions.npz','workbook/stage87_energy_ml/protocol.json']
        files += [str(p.relative_to(ROOT)) for p in sorted(OUT.glob('native_*_summary.json'))]
    if phase=='validate':
        files+=['ntuples/energy_ml_stage158/features.npz','ml/artifacts/stage158','ml/artifacts/stage87/predictions.npz',
                'workbook/stage158_energy_ml/metrics.tsv','workbook/stage158_energy_ml/paired.tsv',
                'workbook/stage158_energy_ml/comparison_summary.json']
    if phase=='plot':files+=['workbook/stage158_energy_ml/metrics.tsv','workbook/stage158_energy_ml/paired.tsv']
    for name in files:assert (ROOT/name).exists(),name
    stamp=time.time_ns();relative=f'software/stage158/{stamp}/energy-ml-stage158.tar.gz';package=ROOT/relative
    package.parent.mkdir(parents=True)
    with tarfile.open(package,'w:gz') as archive:
        for name in files:
            # Package only scientific compact members, never old return transports.
            if name=='ntuples/energy_ml_stage158':
                for path in sorted((ROOT/name).glob('native_*.json.gz')):archive.add(path,arcname=str(path.relative_to(ROOT)))
            else:archive.add(ROOT/name,arcname=name)
    SPOOL.mkdir(parents=True,exist_ok=True);(SPOOL/'logs').mkdir(exist_ok=True)
    worker=SPOOL/f'worker_{stamp}.sh';worker.write_bytes((ROOT/'AnalysisZipFramework/submission/run_ml_stage158.sh').read_bytes())
    descriptor=f'''universe = vanilla
initialdir = {SPOOL}
executable = /bin/bash
transfer_executable = False
arguments = {worker.name} {phase}
transfer_input_files = {worker}, root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/{relative}
should_transfer_files = YES
transfer_output_files = ""
request_cpus = 4
request_memory = 16000MB
request_disk = 8000MB
max_retries = 0
+MaxRuntime = 86400
+PeriodicRemoveReason = "Stage158 cumulative CPU allowance"
periodic_remove = (RemoteUserCpu + RemoteSysCpu) > {allowance}
+NuMuStage = "energy-ml-stage158"
log = {SPOOL}/logs/$(ClusterId).$(ProcId).log
output = {SPOOL}/logs/$(ClusterId).$(ProcId).out
error = {SPOOL}/logs/$(ClusterId).$(ProcId).err
queue 1
'''
    path=SPOOL/f'{phase}_{stamp}.sub';path.write_text(descriptor)
    result=subprocess.check_output(['condor_submit','-terse',str(path)],text=True).strip()
    (OUT/f'{phase}_submission.json').write_text(json.dumps(dict(phase=phase,result=result,CPU_allowance_s=allowance,
        descriptor=descriptor,package=dict(path=relative,bytes=package.stat().st_size,files=files)),indent=2)+'\n')
    print(result,flush=True)


if __name__=='__main__':main()
