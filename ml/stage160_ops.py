"""Scoped Stage160 scheduling and exact terminal transport; no local scientific reads."""
import argparse
import gzip
import json
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path
from stage143_monitor import ATTR as BASE_ATTR
from stage158_finalize import archive_exact, gnu
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'workbook/stage160_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage160'
SPOOL=Path.home()/'condor/nu_muAnalysis/stage160'
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
        starts=sum(r.get('NumJobStarts',0) for r in rows),CPU_budget_s=2000)
    (OUT/'scheduler_accounting.json').write_text(json.dumps(report,indent=2)+'\n')
    print({k:v for k,v in report.items() if k!='jobs'},flush=True)
    if report['total_CPU_s']>=2000 and live:
        subprocess.run(['condor_rm']+[f"{r['ClusterId']}.{r['ProcId']}" for r in live],check=True)
        raise RuntimeError('Frozen Stage160 cumulative CPU exhausted')
    return report


def collect(phase):
    account=monitor();cluster=int(json.loads((OUT/f'{phase}_submission.json').read_text())['result'].split('.')[0])
    row=next(r for r in account['jobs'] if r['ClusterId']==cluster)
    assert row['JobStatus'] in [3,4]
    with tempfile.NamedTemporaryFile(prefix='nu_mu_stage160_',suffix='.tar.gz') as target:
        subprocess.run(['xrdcp','--silent','--force',
            f'root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage160/{phase}_result.tar.gz',target.name],check=True)
        with tarfile.open(target.name,'r:gz') as archive:archive.extractall(ROOT)
    print('COLLECTED',phase,'exit',row.get('ExitCode'),flush=True)
    return row.get('ExitCode',1)


def submit(phase):
    assert phase in ['headers','headers_decision','pilot','admission','full','audit']
    assert not (OUT/f'{phase}_submission.json').exists()
    assert (OUT/'protocol.json').read_bytes()==(ROOT/'workbook/stage159_energy_ml/next_execution_contract.json').read_bytes()
    assert (ROOT/'workbook/stage159_energy_ml/storage_cleanup.json').exists()
    account=monitor();assert account['live_N']==0 and not account['unresolved_ids']
    used=account['total_CPU_s']
    if phase=='headers':allowance=600
    elif phase=='headers_decision':
        assert json.loads((OUT/'headers_summary.json').read_text())['passed']
        assert (OUT/'headers_exitcode.txt').read_text().strip()!='0';allowance=100
    elif phase=='pilot':
        assert json.loads((OUT/'locator.json').read_text())['continue_to_pilot'];allowance=400
    elif phase=='admission':
        assert (OUT/'pilot_exitcode.txt').read_text().strip()=='0';allowance=100
    elif phase=='full':
        assert json.loads((OUT/'admission.json').read_text())['admitted'];allowance=int(2000-used-200)
    else:
        assert (OUT/'full_exitcode.txt').read_text().strip()=='0';allowance=min(200,int(2000-used))
    assert 0<allowance<=2000-used
    files=['setup_env.sh','ml/stage158_finalize.py','workbook/stage160_energy_ml/protocol.json',
        'workbook/stage160_energy_ml/execution_cost_amendment.json','ntuples/energy_ml_stage159/paired_records.json.gz']
    files += [str(p.relative_to(ROOT)) for p in sorted((ROOT/'ml').glob('stage160_*.py'))]
    if phase!='headers':files += ['workbook/stage160_energy_ml/targets.json']
    if phase not in ['headers','headers_decision']:files += ['workbook/stage160_energy_ml/locator.json']
    if phase=='headers_decision':files += ['workbook/stage160_energy_ml/headers_summary.json','ntuples/energy_ml_stage160/headers.json.gz']
    if phase in ['admission','full','audit']:
        files += ['ntuples/energy_ml_stage160/pilot.json.gz','workbook/stage160_energy_ml/pilot_summary.json']
    if phase=='admission':files += ['workbook/stage160_energy_ml/pilot_time.txt','workbook/stage160_energy_ml/scheduler_accounting.json']
    if phase=='full':files += ['workbook/stage160_energy_ml/admission.json']
    if phase=='audit':files += ['workbook/stage160_energy_ml/matched_manifest.json','workbook/stage160_energy_ml/summary.json']
    stamp=str(time.time_ns());relative=Path('software/stage160')/stamp/'energy-ml-stage160.tar.gz'
    package=ROOT/relative;package.parent.mkdir(parents=True)
    with tarfile.open(package,'w:gz') as archive:
        for name in files:archive.add(ROOT/name,arcname=name)
    SPOOL.mkdir(parents=True,exist_ok=True);(SPOOL/'logs').mkdir(exist_ok=True)
    worker=SPOOL/f'worker_{stamp}.sh';worker.write_bytes((ROOT/'AnalysisZipFramework/submission/run_ml_stage160.sh').read_bytes())
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
+PeriodicRemoveReason = "Stage160 cumulative CPU allowance"
periodic_remove = (RemoteUserCpu + RemoteSysCpu) > {allowance}
+NuMuStage = "energy-ml-stage160"
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


def finalize():
    account=monitor();assert account['live_N']==0 and not account['unresolved_ids']
    summary=json.loads((OUT/'summary.json').read_text());assert summary['passed'] and summary['terminal_experiment']
    assert not (OUT/'storage_cleanup.json').exists()
    software=ROOT/'software/stage160';software.mkdir(exist_ok=True)
    source_payload={};transports=[]
    for path in sorted(OUT.glob('*_submission.json')):
        record=json.loads(path.read_text());package=ROOT/record['package']['path']
        with tarfile.open(package,'r:gz') as archive:
            for member in archive:
                if member.isfile():source_payload[record['phase']+'/'+member.name]=archive.extractfile(member).read()
        source_payload[record['phase']+'/submission/worker.sh']=(SPOOL/f'worker_{package.parent.name}.sh').read_bytes()
        transports.extend([package,CACHE/f"{record['phase']}_result.tar.gz"])
    archive_exact(software/'source_snapshots.tar.gz',source_payload)
    event_paths=sorted(CACHE.glob('*.json.gz'));texts={}
    for path in event_paths:
        with gzip.open(path,'rt') as stream:texts[str(path.relative_to(ROOT))]=stream.read()
    event_capsule=CACHE/'event_records.json.gz'
    with gzip.open(event_capsule,'wt') as stream:json.dump(texts,stream,separators=(',',':'))
    with gzip.open(event_capsule,'rt') as stream:assert json.load(stream)==texts
    assert event_capsule.stat().st_size<=8388608
    logs=sorted(OUT.glob('*.log'))
    logs.extend(SPOOL/'logs'/f"{r['ClusterId']}.{r['ProcId']}.{s}" for r in account['jobs'] for s in ['out','err','log'])
    archive_exact(software/'worker_logs.tar.gz',{
        str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else 'scheduler/'+p.name:p.read_bytes() for p in logs})
    timings=sorted(OUT.glob('*_time.txt'))
    archive_exact(software/'execution_audits.tar.gz',{str(p.relative_to(ROOT)):p.read_bytes() for p in timings})
    resources=[dict(task=p.stem.removesuffix('_time'),**gnu(p)) for p in timings]
    native=[dict(phase=p.name.removesuffix('_summary.json'),**{k:json.loads(p.read_text())[k]
        for k in ['N','CPU_s','wall_s','ROOT_read_bytes','RSS_KiB','steady_complete_interval_mean_CPU_s']})
        for p in sorted(OUT.glob('*_summary.json')) if p.name in ['headers_summary.json','pilot_summary.json','full_summary.json','audit_summary.json']]
    resource=dict(scheduler_CPU_s=account['total_CPU_s'],scheduler_aggregate_wall_s=account['total_execute_wall_s'],
        starts=account['starts'],failed_jobs=[f"{r['ClusterId']}.{r['ProcId']}" for r in account['jobs'] if r.get('ExitCode')!=0],
        submitted_request_CPUs=2,submitted_memory_MB=8000,scheduler_RequestCpus=sorted({r['RequestCpus'] for r in account['jobs']}),
        scheduler_RequestMemory_MB=sorted({r['RequestMemory'] for r in account['jobs']}),GNU_processes=resources,native_processes=native,
        GPU_jobs=0,interpretation='Nested process CPU is not added to scheduler. No controlled speedup claim.')
    (OUT/'resource_audit.json').write_text(json.dumps(resource,indent=2)+'\n')
    deleted=[]
    for path in transports+event_paths+timings+[p for p in logs if p.is_relative_to(OUT)]:
        if path.exists():deleted.append(dict(path=str(path.relative_to(ROOT)),bytes=path.stat().st_size));path.unlink()
    for path in transports:
        if path.parent!=CACHE and path.parent.exists() and not any(path.parent.iterdir()):path.parent.rmdir()
    report=dict(all_jobs_terminal=True,event_text_equality=True,source_logs_GNU_byte_equality=True,
        event_capsule=dict(path=str(event_capsule.relative_to(ROOT)),bytes=event_capsule.stat().st_size),
        archives=[dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size) for p in software.glob('*.tar.gz')],
        deleted=deleted,deleted_bytes=sum(r['bytes'] for r in deleted),original_inputs_other_stages_Stage54_untouched=True,no_persistent_ROOT=True)
    (OUT/'storage_cleanup.json').write_text(json.dumps(report,indent=2)+'\n');print(resource);print(report)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['submit','monitor','collect','finalize']);parser.add_argument('--phase',default='headers')
    args=parser.parse_args()
    if args.action=='submit':submit(args.phase)
    elif args.action=='monitor':monitor()
    elif args.action=='collect':raise SystemExit(collect(args.phase))
    else:finalize()


if __name__=='__main__':main()
