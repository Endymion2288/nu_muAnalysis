"""Frozen inventory/header Condor scheduling, disjoint 8000 CPU seconds."""
import argparse
import json
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path
from stage143_monitor import ATTR

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage179_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage179'
SPOOL=Path.home()/'condor/nu_muAnalysis/stage179'


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
        total_execute_wall_s=sum(r.get('RemoteWallClockTime',0) for r in rows),CPU_budget_s=8000)
    (OUT/'scheduler_accounting.json').write_text(json.dumps(report,indent=2)+'\n');print({k:v for k,v in report.items() if k!='jobs'},flush=True)
    if report['total_CPU_s']>=8000 and live:
        subprocess.run(['condor_rm',*[str(r['ClusterId']) for r in live]],check=True);raise RuntimeError('Frozen budget exhausted')
    return report

def submit(phase):
    assert phase in ['preflight','preflight_repair','full','audit'] and not (OUT/f'{phase}_submission.json').exists()
    p=json.loads((OUT/'protocol.json').read_text());account=monitor();assert account['live_N']==0
    allowance=1000-account['total_CPU_s'] if phase=='preflight_repair' else p['phase_CPU_allowance_s'][phase]
    assert account['total_CPU_s']+allowance<=p['CPU_budget_s']
    if phase in ['full','audit']:
        assert json.loads((OUT/'admission.json').read_text())['admitted']
        previous=('preflight_repair' if (OUT/'preflight_repair_submission.json').exists() else 'preflight') if phase=='full' else 'full'
        assert (OUT/f'{previous}_exitcode.txt').read_text().strip()=='0'
    files=['setup_env.sh','ml/stage143_monitor.py','ml/stage179_native.py','ml/stage179_driver.py',
        'workbook/stage179_energy_ml/protocol.json','ml/stage138_response.hxx','ml/stage129_rng.hxx',
        'ml/stage129_official.hxx','ml/stage144_ecal.hxx','ml/stage141_analog.hxx']+p['sources']
    if phase in ['full','audit']:
        files+=['workbook/stage179_energy_ml/admission.json']
    indices=p['indices'] if phase=='audit' else [50] if phase.startswith('preflight') else p['remaining_indices']
    mapping={}
    for index in indices:
        origin=176 if index==50 else 178
        for kind in ['lineage','qa_hits']:
            name=f'ntuples/energy_ml_stage179/parent_{index}_{kind}.json.gz'
            mapping[name]=f'ntuples/energy_ml_stage{origin}/parent_{index}_{kind}.json.gz'
        mapping[f'workbook/stage179_energy_ml/parent_{index}_intervals.json']=f'workbook/stage178_energy_ml/parent_{index}_intervals.json'
        if phase=='audit':
            files+=[f'ntuples/energy_ml_stage179/parent_{index}_response.json.gz',f'workbook/stage179_energy_ml/parent_{index}_charges.tsv',
                f'workbook/stage179_energy_ml/parent_{index}_summary.json']
    if phase=='audit':files+=['ml/stage179_audit.py']
    if (OUT/'preflight_submission.json').exists():
        with tarfile.open(ROOT/json.loads((OUT/'preflight_submission.json').read_text())['package']['path']) as archive:
            assert archive.extractfile('workbook/stage179_energy_ml/protocol.json').read()==(OUT/'protocol.json').read_bytes()
    stamp=str(time.time_ns());relative=Path('software/stage179')/stamp/'energy-ml-stage179.tar.gz'
    package=ROOT/relative;package.parent.mkdir(parents=True)
    with tarfile.open(package,'w:gz') as archive:
        for name in files:archive.add(ROOT/name,arcname=name)
        for name,source in mapping.items():archive.add(ROOT/source,arcname=name)
    SPOOL.mkdir(parents=True,exist_ok=True);(SPOOL/'logs').mkdir(exist_ok=True)
    worker=SPOOL/f'worker_{stamp}.sh';worker.write_bytes((ROOT/'AnalysisZipFramework/submission/run_ml_stage179.sh').read_bytes())
    descriptor=f'''universe = vanilla
initialdir = {SPOOL}
executable = /bin/bash
transfer_executable = False
arguments = {worker.name} {phase}
transfer_input_files = {worker}, root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/{relative}
should_transfer_files = YES
transfer_output_files = ""
request_cpus = 4
request_memory = 12000MB
request_disk = 8000MB
max_retries = 0
+MaxRuntime = 86400
+PeriodicRemoveReason = "Stage179 frozen disjoint CPU allowance"
periodic_remove = (RemoteUserCpu + RemoteSysCpu) > {allowance}
+NuMuStage = "energy-ml-stage179"
log = {SPOOL}/logs/$(ClusterId).$(ProcId).log
output = {SPOOL}/logs/$(ClusterId).$(ProcId).out
error = {SPOOL}/logs/$(ClusterId).$(ProcId).err
queue 1
'''
    path=SPOOL/f'{phase}_{stamp}.sub';path.write_text(descriptor)
    result=subprocess.check_output(['condor_submit','-terse',str(path)],text=True).strip()
    (OUT/f'{phase}_submission.json').write_text(json.dumps(dict(phase=phase,result=result,CPU_allowance_s=allowance,
        descriptor=descriptor,package=dict(path=str(relative),bytes=package.stat().st_size,files=files,mapping=mapping)),indent=2)+'\n')
    print(result,flush=True)

def collect(phase):
    account=monitor();cluster=int(json.loads((OUT/f'{phase}_submission.json').read_text())['result'].split('.')[0])
    row=next(r for r in account['jobs'] if r['ClusterId']==cluster);assert row['JobStatus'] in [3,4]
    with tempfile.NamedTemporaryFile(prefix='nu_mu_stage179_',suffix='.tar.gz') as tmp:
        subprocess.run(['xrdcp','--silent','--force',f'root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage179/{phase}_result.tar.gz',tmp.name],check=True)
        with tarfile.open(tmp.name) as archive:archive.extractall(ROOT)
    print('COLLECTED',phase,'exit',row.get('ExitCode'));return row.get('ExitCode',1)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['submit','monitor','collect']);parser.add_argument('--phase',default='preflight');args=parser.parse_args()
    if args.action=='submit':submit(args.phase)
    elif args.action=='monitor':monitor()
    else:raise SystemExit(collect(args.phase))
