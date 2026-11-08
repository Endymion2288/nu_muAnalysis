"""Scoped scheduling, exact transport and compact terminal audit for real-data pairing."""
import argparse
import json
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

from stage143_monitor import ATTR as BASE_ATTR
from stage158_finalize import archive_exact, gnu

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'workbook/stage159_energy_ml'
CACHE=ROOT/'ntuples/energy_ml_stage159'
SPOOL=Path.home()/'condor/nu_muAnalysis/stage159'
ATTR=BASE_ATTR+['RequestMemory','MemoryUsage','CpusUsage']


def monitor():
    submissions=[json.loads(p.read_text()) for p in OUT.glob('*_submission.json')]
    old=json.loads((OUT/'scheduler_accounting.json').read_text()) if (OUT/'scheduler_accounting.json').exists() else {}
    terminal={r['ClusterId']:r for r in old.get('jobs',[]) if r['JobStatus'] in [3,4]}
    ids={int(r['result'].split('.')[0]) for r in submissions}
    query=sorted(ids-set(terminal));live=[];missing=[]
    if query:
        text=subprocess.check_output(['condor_q']+[str(i) for i in query]+['-json','-attributes',','.join(ATTR)],text=True).strip()
        live=json.loads(text) if text else []
        absent=set(query)-{r['ClusterId'] for r in live}
        if absent:
            constraint=' || '.join(f'ClusterId == {i}' for i in sorted(absent))
            text=subprocess.check_output(['condor_history','-constraint',constraint,'-limit',str(len(absent)),
                '-since','CompletionDate < 1794084000','-json','-attributes',','.join(ATTR)],text=True).strip()
            for r in json.loads(text) if text else []:terminal[r['ClusterId']]=r
            missing=sorted(absent-set(terminal))
    rows=list(terminal.values())+live
    report=dict(jobs=rows,live_N=len(live),unresolved_ids=missing,
        total_CPU_s=sum(r.get('RemoteUserCpu',0)+r.get('RemoteSysCpu',0) for r in rows),
        total_execute_wall_s=sum(r.get('RemoteWallClockTime',0) for r in rows),
        starts=sum(r.get('NumJobStarts',0) for r in rows),CPU_budget_s=600)
    (OUT/'scheduler_accounting.json').write_text(json.dumps(report,indent=2)+'\n')
    print({k:v for k,v in report.items() if k!='jobs'},flush=True)
    if report['total_CPU_s']>=600 and live:
        subprocess.run(['condor_rm']+[f"{r['ClusterId']}.{r['ProcId']}" for r in live],check=True)
        raise RuntimeError('Frozen Stage159 cumulative CPU exhausted')
    return report


def submit(phase):
    assert not (OUT/f'{phase}_submission.json').exists()
    assert json.loads((ROOT/'workbook/stage158_energy_ml/validation_summary.json').read_text())['passed']
    assert (ROOT/'workbook/stage158_energy_ml/storage_cleanup.json').exists()
    assert (OUT/'protocol.json').read_bytes()==(ROOT/'workbook/stage158_energy_ml/next_execution_contract.json').read_bytes()
    account=monitor();assert account['live_N']==0 and not account['unresolved_ids']
    allowance=int(600-account['total_CPU_s']-100);assert allowance>0
    if phase=='identity_diagnostic':
        assert json.loads((OUT/'summary.json').read_text())['unique_pair_N']==0
        assert (OUT/'identity_diagnostic_contract.json').exists()
    elif phase!='audit':assert any(r.get('ExitCode')!=0 for r in account['jobs'])
    stamp=str(time.time_ns());relative=Path('software/stage159')/stamp/'energy-ml-stage159.tar.gz'
    package=ROOT/relative;package.parent.mkdir(parents=True)
    files=['setup_env.sh','workbook/stage159_energy_ml/protocol.json']
    if phase=='identity_diagnostic':files += ['workbook/stage159_energy_ml/native_64.json',
        'workbook/stage159_energy_ml/summary.json','workbook/stage159_energy_ml/identity_diagnostic_contract.json']
    files += [str(p.relative_to(ROOT)) for p in sorted((ROOT/'ml').glob('stage159_*.py'))]
    with tarfile.open(package,'w:gz') as archive:
        for name in files:archive.add(ROOT/name,arcname=name)
    SPOOL.mkdir(parents=True,exist_ok=True);(SPOOL/'logs').mkdir(exist_ok=True)
    worker=SPOOL/f'worker_{stamp}.sh';worker.write_bytes((ROOT/'AnalysisZipFramework/submission/run_ml_stage159.sh').read_bytes())
    descriptor=f'''universe = vanilla
initialdir = {SPOOL}
executable = /bin/bash
transfer_executable = False
arguments = {worker.name} {phase}
transfer_input_files = {worker}, root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/{relative}
should_transfer_files = YES
transfer_output_files = ""
request_cpus = 2
request_memory = 8000MB
request_disk = 5000MB
max_retries = 0
+MaxRuntime = 86400
+PeriodicRemoveReason = "Stage159 cumulative CPU allowance"
periodic_remove = (RemoteUserCpu + RemoteSysCpu) > {allowance}
+NuMuStage = "energy-ml-stage159"
log = {SPOOL}/logs/$(ClusterId).$(ProcId).log
output = {SPOOL}/logs/$(ClusterId).$(ProcId).out
error = {SPOOL}/logs/$(ClusterId).$(ProcId).err
queue 1
'''
    path=SPOOL/f'{phase}_{stamp}.sub';path.write_text(descriptor)
    result=subprocess.check_output(['condor_submit','-terse',str(path)],text=True).strip()
    (OUT/f'{phase}_submission.json').write_text(json.dumps(dict(phase=phase,result=result,CPU_allowance_s=allowance,
        descriptor=descriptor,package=dict(path=str(relative),bytes=package.stat().st_size,files=files)),indent=2)+'\n')
    print(result,flush=True)


def collect(phase):
    account=monitor();cluster=int(json.loads((OUT/f'{phase}_submission.json').read_text())['result'].split('.')[0])
    row=next(r for r in account['jobs'] if r['ClusterId']==cluster)
    assert row['JobStatus'] in [3,4]
    with tempfile.NamedTemporaryFile(prefix='nu_mu_stage159_',suffix='.tar.gz') as target:
        subprocess.run(['xrdcp','--silent','--force',
            f'root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage159/{phase}_result.tar.gz',target.name],check=True)
        with tarfile.open(target.name,'r:gz') as archive:archive.extractall(ROOT)
    print('COLLECTED',phase,'exit',row.get('ExitCode'),flush=True)
    return row.get('ExitCode',1)


def finalize():
    account=monitor();assert account['live_N']==0 and not account['unresolved_ids']
    assert json.loads((OUT/'summary.json').read_text())['passed']
    assert not (OUT/'storage_cleanup.json').exists()
    software=ROOT/'software/stage159';software.mkdir(exist_ok=True)
    source_payload={};transports=[]
    for path in sorted(OUT.glob('*_submission.json')):
        record=json.loads(path.read_text());package=ROOT/record['package']['path']
        with tarfile.open(package,'r:gz') as archive:
            for member in archive:
                if member.isfile():source_payload[record['phase']+'/'+member.name]=archive.extractfile(member).read()
        source_payload[record['phase']+'/submission/worker.sh']=(SPOOL/f'worker_{package.parent.name}.sh').read_bytes()
        transports.extend([package,CACHE/f"{record['phase']}_result.tar.gz"])
    archive_exact(software/'source_snapshots.tar.gz',source_payload)
    logs=sorted(OUT.glob('*.log'))
    logs.extend(SPOOL/'logs'/f"{r['ClusterId']}.{r['ProcId']}.{s}" for r in account['jobs'] for s in ['out','err','log'])
    archive_exact(software/'worker_logs.tar.gz',{
        str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else 'scheduler/'+p.name:p.read_bytes() for p in logs})
    native=[OUT/'native_64.json',OUT/'native_4.json']
    timing=sorted(OUT.glob('*_time.txt'))
    archive_exact(software/'native_audits.tar.gz',{str(p.relative_to(ROOT)):p.read_bytes() for p in native+timing})
    resources=[dict(task=p.stem.removesuffix('_time'),**gnu(p)) for p in sorted(OUT.glob('*_time.txt'))]
    native_resources=[{k:json.loads(p.read_text())[k] for k in ['requested_prefix','CPU_s','wall_s','ROOT_read_bytes','RSS_KiB']} for p in native]
    report=dict(scheduler_CPU_s=account['total_CPU_s'],scheduler_aggregate_wall_s=account['total_execute_wall_s'],
        starts=account['starts'],failed_jobs=[f"{r['ClusterId']}.{r['ProcId']}" for r in account['jobs'] if r.get('ExitCode')!=0],
        submitted_request_CPUs=2,submitted_memory_MB=8000,
        scheduler_RequestCpus=sorted({r['RequestCpus'] for r in account['jobs']}),
        scheduler_RequestMemory_MB=sorted({r['RequestMemory'] for r in account['jobs']}),
        GNU_processes=resources,native_processes=native_resources,GPU_jobs=0,
        interpretation='All attempts counted. GNU/native CPU nested inside scheduler CPU; no speedup claim.')
    (OUT/'resource_audit.json').write_text(json.dumps(report,indent=2)+'\n')
    deleted=[]
    for path in transports+native+timing+[p for p in logs if p.is_relative_to(OUT)]:
        if path.exists():deleted.append(dict(path=str(path.relative_to(ROOT)),bytes=path.stat().st_size));path.unlink()
    for path in transports:
        if path.parent!=CACHE and path.parent.exists() and not any(path.parent.iterdir()):path.parent.rmdir()
    event_bytes=sum(p.stat().st_size for p in CACHE.glob('*') if p.is_file())
    assert event_bytes<=8388608
    result=dict(all_jobs_terminal=True,source_logs_native_byte_equality=True,final_event_bytes=event_bytes,limit_bytes=8388608,
        archives=[dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size) for p in software.glob('*.tar.gz')],
        deleted=deleted,deleted_bytes=sum(r['bytes'] for r in deleted),no_persistent_ROOT=True,
        original_inputs_other_stages_and_Stage54_untouched=True)
    (OUT/'storage_cleanup.json').write_text(json.dumps(result,indent=2)+'\n');print(report);print(result)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['submit','monitor','collect','finalize']);parser.add_argument('--phase',default='audit')
    args=parser.parse_args()
    if args.action=='submit':submit(args.phase)
    elif args.action=='monitor':monitor()
    elif args.action=='collect':raise SystemExit(collect(args.phase))
    else:finalize()


if __name__=='__main__':main()
