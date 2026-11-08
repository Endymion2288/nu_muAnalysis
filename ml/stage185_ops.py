"""Frozen inventory/header Condor scheduling, disjoint 2400 CPU seconds."""
import argparse
import json
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path
from stage143_monitor import ATTR

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage185_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage185'
SPOOL=Path.home()/'condor/nu_muAnalysis/stage185'


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
        total_execute_wall_s=sum(r.get('RemoteWallClockTime',0) for r in rows),CPU_budget_s=2400)
    (OUT/'scheduler_accounting.json').write_text(json.dumps(report,indent=2)+'\n');print({k:v for k,v in report.items() if k!='jobs'},flush=True)
    if report['total_CPU_s']>=2400 and live:
        subprocess.run(['condor_rm',*[str(r['ClusterId']) for r in live]],check=True);raise RuntimeError('Frozen budget exhausted')
    return report

def submit(phase):
    assert phase in ['identity','identity_repair','identity_fix','batch','audit'] and not (OUT/f'{phase}_submission.json').exists()
    p=json.loads((OUT/'protocol.json').read_text());account=monitor();assert account['live_N']==0
    allowance=500-account['total_CPU_s'] if phase in ['identity_repair','identity_fix'] else p['phase_CPU_allowance_s'][phase]
    assert account['total_CPU_s']+allowance<=p['CPU_budget_s']
    if phase not in ['identity','identity_repair','identity_fix']:assert json.loads((OUT/'identity_summary.json').read_text())['passed']
    files=['setup_env.sh','ml/stage143_monitor.py','ml/stage185_identity.py','ml/stage185_identity.hxx',
        'workbook/stage185_energy_ml/protocol.json','workbook/stage185_energy_ml/IdDict_6d6ab70b.xml',
        'workbook/stage184_energy_ml/audit_source_0_summary.json']
    if phase=='batch':assert json.loads((OUT/'batch_resource_admission.json').read_text())['admitted']
    if phase in ['batch','audit']:
        files+=['ml/stage185_native.py','ml/stage185_mapping.hxx','ml/stage138_response.hxx','ml/stage144_ecal.hxx',
            'ml/stage129_official.hxx','ml/stage141_analog.hxx','ml/stage184_window.hxx','ml/stage122_saved.py',
            'workbook/stage185_energy_ml/identity_summary.json','workbook/stage185_energy_ml/batch_resource_admission.json','workbook/stage184_energy_ml/preflight_source_0_charges.tsv']
    if phase=='audit':
        files+=['ml/stage185_audit.py','workbook/stage185_energy_ml/identity_summary.json',
            'workbook/stage185_energy_ml/batch_summary.json','workbook/stage185_energy_ml/charges.tsv',
            'workbook/stage184_energy_ml/preflight_source_0_charges.tsv','workbook/stage184_energy_ml/audit_source_0_summary.json']
    stamp=str(time.time_ns());relative=Path('software/stage185')/stamp/'energy-ml-stage185.tar.gz'
    package=ROOT/relative;package.parent.mkdir(parents=True)
    with tarfile.open(package,'w:gz') as archive:
        for name in dict.fromkeys(files):archive.add(ROOT/name,arcname=name)
    SPOOL.mkdir(parents=True,exist_ok=True);(SPOOL/'logs').mkdir(exist_ok=True)
    worker=SPOOL/f'worker_{stamp}.sh';worker.write_bytes((ROOT/'AnalysisZipFramework/submission/run_ml_stage185.sh').read_bytes())
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
request_disk = 4000MB
max_retries = 0
+MaxRuntime = 86400
+PeriodicRemoveReason = "Stage185 fixed phase CPU allowance"
periodic_remove = (RemoteUserCpu + RemoteSysCpu) > {allowance}
+NuMuStage = "energy-ml-stage185"
log = {SPOOL}/logs/$(ClusterId).$(ProcId).log
output = {SPOOL}/logs/$(ClusterId).$(ProcId).out
error = {SPOOL}/logs/$(ClusterId).$(ProcId).err
queue 1
'''
    path=SPOOL/f'{phase}_{stamp}.sub';path.write_text(descriptor)
    result=subprocess.check_output(['condor_submit','-terse',str(path)],text=True).strip()
    (OUT/f'{phase}_submission.json').write_text(json.dumps(dict(phase=phase,result=result,CPU_allowance_s=allowance,
        descriptor=descriptor,package=dict(path=str(relative),bytes=package.stat().st_size,files=files)),indent=2)+'\n');print(result,flush=True)

def collect(phase):
    account=monitor();cluster=int(json.loads((OUT/f'{phase}_submission.json').read_text())['result'].split('.')[0])
    row=next(r for r in account['jobs'] if r['ClusterId']==cluster);assert row['JobStatus'] in [3,4]
    with tempfile.NamedTemporaryFile(prefix='nu_mu_stage185_',suffix='.tar.gz') as tmp:
        subprocess.run(['xrdcp','--silent','--force',f'root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage185/{phase}_result.tar.gz',tmp.name],check=True)
        with tarfile.open(tmp.name) as archive:archive.extractall(ROOT)
    print('COLLECTED',phase,'exit',row.get('ExitCode'));return row.get('ExitCode',1)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['submit','monitor','collect']);parser.add_argument('--phase',default='identity');args=parser.parse_args()
    if args.action=='submit':submit(args.phase)
    elif args.action=='monitor':monitor()
    else:raise SystemExit(collect(args.phase))
