"""Scoped Stage162 scheduling and exact terminal transport; no local scientific reads."""
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
OUT=ROOT/'workbook/stage162_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage162'
SPOOL=Path.home()/'condor/nu_muAnalysis/stage162'
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
        raise RuntimeError('Frozen Stage162 cumulative CPU exhausted')
    return report


def collect(phase):
    account=monitor();cluster=int(json.loads((OUT/f'{phase}_submission.json').read_text())['result'].split('.')[0])
    row=next(r for r in account['jobs'] if r['ClusterId']==cluster)
    assert row['JobStatus'] in [3,4]
    with tempfile.NamedTemporaryFile(prefix='nu_mu_stage162_',suffix='.tar.gz') as target:
        subprocess.run(['xrdcp','--silent','--force',
            f'root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage162/{phase}_result.tar.gz',target.name],check=True)
        with tarfile.open(target.name,'r:gz') as archive:archive.extractall(ROOT)
    print('COLLECTED',phase,'exit',row.get('ExitCode'),flush=True)
    return row.get('ExitCode',1)


def submit(phase):
    assert phase in ['pilot','content_audit','producer_audit','full','repeat']
    assert not (OUT/f'{phase}_submission.json').exists()
    assert (OUT/'protocol.json').read_bytes()==(ROOT/'workbook/stage161_energy_ml/next_execution_contract.json').read_bytes()
    assert (ROOT/'workbook/stage161_energy_ml/storage_cleanup.json').exists()
    account=monitor();assert account['live_N']==0 and not account['unresolved_ids']
    used=account['total_CPU_s']
    if phase.startswith('pilot') or phase in ['content_audit','producer_audit']:allowance=int(650-used)
    elif phase=='full':
        gate=json.loads((OUT/'admission.json').read_text());assert gate['admitted']
        assert used+gate['projected_full_raw_3x_CPU_s']+gate['projected_full_native_3x_CPU_s']+200<=2000
        allowance=int(2000-used-200)
    else:
        assert (OUT/'full_exitcode.txt').read_text().strip()=='0';allowance=min(200,int(2000-used))
    assert 0<allowance<=2000-used
    files=['setup_env.sh','ml/stage158_finalize.py','ml/stage124_native.hxx','ml/stage149_native.hxx',
           'workbook/stage162_energy_ml/protocol.json','workbook/stage162_energy_ml/matched_manifest.json',
           'workbook/stage162_energy_ml/scheduler_accounting.json',
           'ml/stage161_native.hxx','workbook/stage161_energy_ml/IdDictScintillator_2024.xml',
           'ntuples/energy_ml_stage161/event_records.json.gz','workbook/stage162_energy_ml/numerical_definition.json']
    files += [str(p.relative_to(ROOT)) for p in sorted((ROOT/'ml').glob('stage162_*')) if p.suffix in ['.py','.hxx']]
    if phase=='pilot_conditions':
        files += ['ntuples/energy_ml_stage162/pilot_raw.json.gz','workbook/stage162_energy_ml/pilot_raw_summary.json',
                  'workbook/stage162_energy_ml/pilot_raw_time.txt','workbook/stage162_energy_ml/reuse_raw.json']
    if phase=='producer_audit':
        files += ['ntuples/energy_ml_stage162/event_records.json.gz','workbook/stage162_energy_ml/producer_integral_source.json']
    if phase=='content_audit':
        files += ['ntuples/energy_ml_stage162/pilot_raw.json.gz']
    if phase in ['full','repeat']:
        files += ['workbook/stage162_energy_ml/admission.json']
        files += [f'ntuples/energy_ml_stage162/pilot_{kind}.json.gz' for kind in ['raw','native']]
    stamp=str(time.time_ns());relative=Path('software/stage162')/stamp/'energy-ml-stage162.tar.gz'
    package=ROOT/relative;package.parent.mkdir(parents=True)
    with tarfile.open(package,'w:gz') as archive:
        for name in files:archive.add(ROOT/name,arcname=name)
    SPOOL.mkdir(parents=True,exist_ok=True);(SPOOL/'logs').mkdir(exist_ok=True)
    worker=SPOOL/f'worker_{stamp}.sh';worker.write_bytes((ROOT/'AnalysisZipFramework/submission/run_ml_stage162.sh').read_bytes())
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
+PeriodicRemoveReason = "Stage162 cumulative CPU allowance"
periodic_remove = (RemoteUserCpu + RemoteSysCpu) > {allowance}
+NuMuStage = "energy-ml-stage162"
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
    software=ROOT/'software/stage162';software.mkdir(exist_ok=True)
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
    native=[]
    for path in sorted(OUT.glob('*_summary.json')):
        if path.name.endswith(('_raw_summary.json','_native_summary.json')):
            data=json.loads(path.read_text())
            native.append(dict(phase=path.name.removesuffix('_summary.json'),**{k:data.get(k)
                for k in ['N','CPU_s','wall_s','ROOT_read_bytes','RSS_KiB','first_read_CPU_s','first_execute_CPU_s','steady_complete_interval_max_CPU_s']}))
    comparisons=sorted(OUT.glob('*_raw_comparison.tsv'))
    archive_exact(software/'comparison_tables.tar.gz',{str(p.relative_to(ROOT)):p.read_bytes() for p in comparisons})
    resource=dict(scheduler_CPU_s=account['total_CPU_s'],scheduler_aggregate_wall_s=account['total_execute_wall_s'],
        starts=account['starts'],failed_jobs=[f"{r['ClusterId']}.{r['ProcId']}" for r in account['jobs'] if r.get('ExitCode')!=0],
        submitted_request_CPUs=2,submitted_memory_MB=8000,scheduler_RequestCpus=sorted({r['RequestCpus'] for r in account['jobs']}),
        scheduler_RequestMemory_MB=sorted({r['RequestMemory'] for r in account['jobs']}),GNU_processes=resources,native_processes=native,
        GPU_jobs=0,interpretation='Nested process CPU is not added to scheduler. No controlled speedup claim.')
    (OUT/'resource_audit.json').write_text(json.dumps(resource,indent=2)+'\n')
    deleted=[]
    for path in transports+event_paths+timings+comparisons+[p for p in logs if p.is_relative_to(OUT)]:
        if path.exists():deleted.append(dict(path=str(path.relative_to(ROOT)),bytes=path.stat().st_size));path.unlink()
    for path in transports:
        if path.parent!=CACHE and path.parent.exists() and not any(path.parent.iterdir()):path.parent.rmdir()
    report=dict(all_jobs_terminal=True,event_text_equality=True,source_logs_GNU_byte_equality=True,
        event_capsule=dict(path=str(event_capsule.relative_to(ROOT)),bytes=event_capsule.stat().st_size),
        archives=[dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size) for p in software.glob('*.tar.gz')],
        deleted=deleted,deleted_bytes=sum(r['bytes'] for r in deleted),original_inputs_other_stages_Stage54_untouched=True,no_persistent_ROOT=True)
    (OUT/'storage_cleanup.json').write_text(json.dumps(report,indent=2)+'\n');print(resource);print(report)


def finalize_supplement():
    """Append one cached producer-definition diagnosis to already exact terminal archives."""
    account=monitor();assert account['live_N']==0 and not account['unresolved_ids']
    phase='producer_audit';assert (OUT/(phase+'_exitcode.txt')).read_text().strip()=='0'
    old=json.loads((OUT/'storage_cleanup.json').read_text());software=ROOT/'software/stage162'
    record=json.loads((OUT/(phase+'_submission.json')).read_text());package=ROOT/record['package']['path']
    def contents(path):
        with tarfile.open(path,'r:gz') as archive:return {m.name:archive.extractfile(m).read() for m in archive if m.isfile()}
    sources=contents(software/'source_snapshots.tar.gz')
    with tarfile.open(package,'r:gz') as archive:
        for member in archive:
            if member.isfile():sources[phase+'/'+member.name]=archive.extractfile(member).read()
    sources[phase+'/submission/worker.sh']=(SPOOL/f'worker_{package.parent.name}.sh').read_bytes()
    archive_exact(software/'source_snapshots.tar.gz',sources)
    logs=contents(software/'worker_logs.tar.gz')
    cluster=record['result'].split()[0]
    for suffix in ['out','err','log']:
        path=SPOOL/'logs'/(cluster+'.'+suffix);logs['scheduler/'+path.name]=path.read_bytes()
    archive_exact(software/'worker_logs.tar.gz',logs)
    timing=OUT/(phase+'_time.txt');timings=contents(software/'execution_audits.tar.gz')
    timings[str(timing.relative_to(ROOT))]=timing.read_bytes();archive_exact(software/'execution_audits.tar.gz',timings)
    resource=json.loads((OUT/'resource_audit.json').read_text())
    resource.update(scheduler_CPU_s=account['total_CPU_s'],scheduler_aggregate_wall_s=account['total_execute_wall_s'],starts=account['starts'])
    resource['GNU_processes'].append(dict(task=phase,**gnu(timing)))
    (OUT/'resource_audit.json').write_text(json.dumps(resource,indent=2)+'\n')
    deleted=[]
    for path in [package,CACHE/(phase+'_result.tar.gz'),timing]:
        if path.exists():deleted.append(dict(path=str(path.relative_to(ROOT)),bytes=path.stat().st_size));path.unlink()
    if not any(package.parent.iterdir()):package.parent.rmdir()
    old['deleted']+=deleted;old['deleted_bytes']=sum(r['bytes'] for r in old['deleted'])
    old['archives']=[dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size) for p in software.glob('*.tar.gz')]
    old['supplement_exact_archived']=phase
    (OUT/'storage_cleanup.json').write_text(json.dumps(old,indent=2)+'\n');print(resource);print(old['deleted_bytes'])


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['submit','monitor','collect','finalize','finalize_supplement']);parser.add_argument('--phase',default='pilot')
    args=parser.parse_args()
    if args.action=='submit':submit(args.phase)
    elif args.action=='monitor':monitor()
    elif args.action=='collect':raise SystemExit(collect(args.phase))
    elif args.action=='finalize_supplement':finalize_supplement()
    else:finalize()


if __name__=='__main__':main()
