"""Frozen inventory/header Condor scheduling, disjoint 1200 CPU seconds."""
import argparse
import json
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path
from stage143_monitor import ATTR

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage170_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage170'
SPOOL=Path.home()/'condor/nu_muAnalysis/stage170'


def monitor():
    submissions=[json.loads(p.read_text()) for p in OUT.glob('*_submission.json')]
    old=json.loads((OUT/'scheduler_accounting.json').read_text()) if (OUT/'scheduler_accounting.json').exists() else {}
    terminal={r['ClusterId']:r for r in old.get('jobs',[]) if r['JobStatus'] in [3,4]}
    query={int(r['result'].split('.')[0]) for r in submissions}-set(terminal);live=[]
    if query:
        payload=subprocess.check_output(['condor_q',*map(str,sorted(query)),'-json','-attributes',','.join(ATTR+['RequestMemory','MemoryUsage'])],text=True).strip()
        live=json.loads(payload) if payload else []
        absent=query-{r['ClusterId'] for r in live}
        if absent:
            payload=subprocess.check_output(['condor_history','-constraint',' || '.join(f'ClusterId == {i}' for i in sorted(absent)),'-limit',str(len(absent)),'-since','CompletionDate < 1794084000','-json','-attributes',','.join(ATTR+['RequestMemory','MemoryUsage'])],text=True).strip()
            for r in json.loads(payload) if payload else []:terminal[r['ClusterId']]=r
        assert not absent-set(terminal),'Unresolved submitted job; do not launch a duplicate'
    rows=list(terminal.values())+live
    report=dict(jobs=rows,live_N=len(live),starts=sum(r.get('NumJobStarts',0) for r in rows),
        total_CPU_s=sum(r.get('RemoteUserCpu',0)+r.get('RemoteSysCpu',0) for r in rows),
        total_execute_wall_s=sum(r.get('RemoteWallClockTime',0) for r in rows),CPU_budget_s=1200)
    (OUT/'scheduler_accounting.json').write_text(json.dumps(report,indent=2)+'\n');print({k:v for k,v in report.items() if k!='jobs'},flush=True)
    if report['total_CPU_s']>=1200 and live:
        subprocess.run(['condor_rm',*[str(r['ClusterId']) for r in live]],check=True);raise RuntimeError('Frozen budget exhausted')
    return report


def submit(phase):
    assert phase in ['smoke','pilot','audit'] and not (OUT/f'{phase}_submission.json').exists()
    if (OUT/'smoke_submission.json').exists():
        original=json.loads((OUT/'smoke_submission.json').read_text())['package']['path']
        with tarfile.open(ROOT/original) as archive:
            for name in ['protocol.json','header_sources.json']:
                assert archive.extractfile('workbook/stage170_energy_ml/'+name).read()==(OUT/name).read_bytes()
    account=monitor();assert account['live_N']==0
    allowance=dict(smoke=300,pilot=600,audit=300)[phase]
    assert account['total_CPU_s']+allowance<=1200
    if phase in ['pilot','audit']:
        previous='smoke' if phase=='pilot' else 'pilot'
        assert (OUT/f'{previous}_exitcode.txt').read_text().strip()=='0'
    if phase=='pilot':assert json.loads((OUT/'admission.json').read_text())['admitted']
    files=['ml/stage170_run.py','ml/stage170_raw.cxx','ml/stage143_monitor.py',
        'workbook/stage170_energy_ml/protocol.json','workbook/stage170_energy_ml/header_sources.json',
        'software/stage170/official_headers.tar.gz','ntuples/energy_ml_stage43/data_noise.npz',
        'workbook/stage166_energy_ml/exposure_input_manifest.json']
    if phase in ['pilot','audit']:
        files+=['workbook/stage170_energy_ml/admission.json','ntuples/energy_ml_stage170/smoke_rows.jsonl.gz']
    if phase=='audit':files+=['ntuples/energy_ml_stage170/pilot_rows.jsonl.gz']
    stamp=str(time.time_ns());relative=Path('software/stage170')/stamp/'energy-ml-stage170.tar.gz';package=ROOT/relative;package.parent.mkdir(parents=True)
    with tarfile.open(package,'w:gz') as archive:
        for name in files:archive.add(ROOT/name,arcname=name)
    SPOOL.mkdir(parents=True,exist_ok=True);(SPOOL/'logs').mkdir(exist_ok=True)
    worker=SPOOL/f'worker_{stamp}.sh';worker.write_bytes((ROOT/'AnalysisZipFramework/submission/run_ml_stage170.sh').read_bytes())
    descriptor=f'''universe = vanilla
initialdir = {SPOOL}
executable = /bin/bash
transfer_executable = False
arguments = {worker.name} {phase}
transfer_input_files = {worker}, root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/{relative}
should_transfer_files = YES
transfer_output_files = ""
request_cpus = 2
request_memory = 4000MB
request_disk = 2000MB
max_retries = 0
+MaxRuntime = 86400
+PeriodicRemoveReason = "Stage170 frozen disjoint CPU allowance"
periodic_remove = (RemoteUserCpu + RemoteSysCpu) > {allowance}
+NuMuStage = "energy-ml-stage170"
log = {SPOOL}/logs/$(ClusterId).$(ProcId).log
output = {SPOOL}/logs/$(ClusterId).$(ProcId).out
error = {SPOOL}/logs/$(ClusterId).$(ProcId).err
queue 1
'''
    path=SPOOL/f'{phase}_{stamp}.sub';path.write_text(descriptor)
    result=subprocess.check_output(['condor_submit','-terse',str(path)],text=True).strip()
    (OUT/f'{phase}_submission.json').write_text(json.dumps(dict(phase=phase,result=result,CPU_allowance_s=allowance,descriptor=descriptor,
        package=dict(path=str(relative),bytes=package.stat().st_size,files=files)),indent=2)+'\n');print(result,flush=True)


def collect(phase):
    account=monitor();cluster=int(json.loads((OUT/f'{phase}_submission.json').read_text())['result'].split('.')[0]);row=next(r for r in account['jobs'] if r['ClusterId']==cluster)
    assert row['JobStatus'] in [3,4]
    with tempfile.NamedTemporaryFile(prefix='nu_mu_stage170_',suffix='.tar.gz') as tmp:
        subprocess.run(['xrdcp','--silent','--force',f'root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage170/{phase}_result.tar.gz',tmp.name],check=True)
        with tarfile.open(tmp.name) as archive:archive.extractall(ROOT)
    print('COLLECTED',phase,'exit',row.get('ExitCode'));return row.get('ExitCode',1)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['submit','monitor','collect']);parser.add_argument('--phase',default='smoke');args=parser.parse_args()
    if args.action=='submit':submit(args.phase)
    elif args.action=='monitor':monitor()
    else:raise SystemExit(collect(args.phase))
