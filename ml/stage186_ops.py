"""Frozen inventory/header Condor scheduling, disjoint 180000 CPU seconds."""
import argparse
import json
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path
from stage143_monitor import ATTR

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage186_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage186'
SPOOL=Path.home()/'condor/nu_muAnalysis/stage186'


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
        total_execute_wall_s=sum(r.get('RemoteWallClockTime',0) for r in rows),CPU_budget_s=180000)
    (OUT/'scheduler_accounting.json').write_text(json.dumps(report,indent=2)+'\n');print({k:v for k,v in report.items() if k!='jobs'},flush=True)
    if report['total_CPU_s']>=180000 and live:
        subprocess.run(['condor_rm',*[str(r['ClusterId']) for r in live]],check=True);raise RuntimeError('Frozen budget exhausted')
    return report

def submit(phase):
    assert not (OUT/f'{phase}_submission.json').exists()
    p=json.loads((OUT/'protocol.json').read_text());account=monitor()
    production=phase.startswith('production_');repair=phase.startswith('repair_');pilot_phase=phase in ['pilot','pilot_repair']
    if repair:
        assert account['live_N']<4 and json.loads((OUT/'admission.json').read_text())['admitted']
        family=int(phase.split('_')[1]);parent=json.loads((OUT/f'production_{family}_submission.json').read_text());cluster=int(parent['result'].split('.')[0]);job=next(r for r in account['jobs'] if r['ClusterId']==cluster);assert job['JobStatus']==4
        failed=[int(r['label'].split('_')[1]) for r in json.loads((OUT/f'production_{family}_driver.json').read_text()) if r['exit']!=0];assert failed
        allowance=p['production_job_CPU_allowances_s'][family]-job['RemoteUserCpu']-job['RemoteSysCpu']
        (OUT/f'{phase}_plan.json').write_text(json.dumps(dict(family=family,groups=failed,CPU_allowance_s=allowance,already_used_family_CPU_s=job['RemoteUserCpu']+job['RemoteSysCpu'],original_family_cap_s=p['production_job_CPU_allowances_s'][family]),indent=2)+'\n')
    elif production:
        assert account['live_N']<4 and json.loads((OUT/'admission.json').read_text())['admitted']
        job=int(phase.split('_')[1]);allowance=p['production_job_CPU_allowances_s'][job]
    else:
        assert account['live_N']==0
        if phase=='fit_repair':
            prior=json.loads((OUT/'fit_submission.json').read_text());job=next(r for r in account['jobs'] if r['ClusterId']==int(prior['result'].split('.')[0]))
            assert job['JobStatus']==4 and job['ExitCode']==1
            assert "ModuleNotFoundError: No module named 'xgboost'" in (OUT/'fit.log').read_text()
            assert not any((ROOT/'ml/artifacts/stage186').glob('*')) and not (OUT/'fit_summary.json').exists()
            allowance=3000-job['RemoteUserCpu']-job['RemoteSysCpu']
        else:allowance={'pilot_repair':4000-account['total_CPU_s']-1000,'pilot':3000,'pilot_audit':1000,'probe':500,'fit':3000,'audit':5000}[phase]
    assert account['total_CPU_s']+allowance<=180000
    if phase=='pilot_audit':assert (OUT/'pilot_repair_exitcode.txt').read_text().strip()=='0'
    if phase in ['fit','fit_repair','audit']:
        assert all((OUT/f'full_{g}_summary.json').exists() and (CACHE/f'full_{g}.npz').exists() for g in range(35))
    files=['setup_env.sh','ml/stage143_monitor.py','ml/stage184_freeze.py','ml/stage158_finalize.py',
        'ml/stage185_identity.hxx','ml/stage185_mapping.hxx','ml/stage138_response.hxx','ml/stage144_ecal.hxx',
        'ml/stage129_official.hxx','ml/stage141_analog.hxx','ml/stage184_window.hxx','ml/stage122_saved.py',
        'workbook/stage185_energy_ml/IdDict_6d6ab70b.xml','workbook/stage186_energy_ml/IdDict_4a0e366b.xml',
        'workbook/stage186_energy_ml/protocol.json','workbook/stage186_energy_ml/source_producers.json',
        'workbook/stage129_energy_ml/extraction_contract.json']
    files += [str(p.relative_to(ROOT)) for p in (ROOT/'ml').glob('stage186_*.py') if p.name not in ['stage186_finalize.py','stage186_validate_docs.py']]
    if phase in ['pilot','pilot_repair','probe','fit','fit_repair','audit']:
        files+=['ml/audited_features.py','ml/configs/audited_features.json','ml/stage119_curve_common.py',
            'ml/stage129_energy.py','ml/stage119_reportcurve.py','workbook/stage87_energy_ml/protocol.json',
            'ntuples/energy_ml_stage119/old_input.npz','ml/artifacts/stage87/predictions.npz']
    if phase in ['pilot','pilot_repair','probe']:
        files+=['ml/alternative_calibration.py','workbook/stage70_energy_ml/calo_conditions_qa.json','workbook/stage70_energy_ml/calibration_closure.json','workbook/stage186_energy_ml/input_control_repair.json','ntuples/energy_ml_stage55/dataset.npz','ntuples/energy_ml_stage56/readout.npz',
            'ntuples/energy_ml_stage87/split.npz']+[f'ntuples/energy_ml_stage{i}/support.npz' for i in [70,81,82,83]]
    if phase=='pilot_audit':files+=['ntuples/energy_ml_stage186/pilot_0.npz','workbook/stage186_energy_ml/pilot_0_summary.json','workbook/stage186_energy_ml/input_controls.json','workbook/stage186_energy_ml/scheduler_accounting.json','workbook/stage186_energy_ml/pilot_0_time.txt']
    if repair:files += [f'workbook/stage186_energy_ml/{phase}_plan.json','workbook/stage186_energy_ml/baseline_rounding_contract.json']
    if production or repair:files+=['workbook/stage186_energy_ml/admission.json','ntuples/energy_ml_stage119/old_input.npz','ml/configs/audited_features.json']
    if phase in ['fit','fit_repair','audit']:
        files+=['workbook/stage186_energy_ml/admission.json','workbook/stage186_energy_ml/pilot_validation.json']
        files += [str(p.relative_to(ROOT)) for p in (ROOT/'ntuples/energy_ml_stage186').glob('full_*.npz')]
        files += [str(p.relative_to(ROOT)) for p in (ROOT/'workbook/stage186_energy_ml').glob('full_*_summary.json')]
        files += [str(p.relative_to(ROOT)) for p in (ROOT/'workbook/stage186_energy_ml').glob('full_*_time.txt')]
    if phase=='audit':
        files += [str(p.relative_to(ROOT)) for p in OUT.glob('*_driver.json')]
        files += [str(p.relative_to(ROOT)) for p in (ROOT/'ml/artifacts/stage186').glob('*') if p.is_file()]
        files += [str(p.relative_to(ROOT)) for p in (ROOT/'workbook/stage186_energy_ml').glob('energy_*.tsv')]
        files += ['workbook/stage186_energy_ml/fit_summary.json','workbook/stage186_energy_ml/energy_summary.json',
            'workbook/stage186_energy_ml/input_controls.json','workbook/stage186_energy_ml/input_control_repair.json',
            'workbook/stage186_energy_ml/baseline_rounding_contract.json',
            'ntuples/energy_ml_stage186/pilot_0.npz','ntuples/energy_ml_stage186/repeat_0.npz','ntuples/energy_ml_stage186/cohort.npz']
    stamp=str(time.time_ns());relative=Path('software/stage186')/stamp/'energy-ml-stage186.tar.gz'
    package=ROOT/relative;package.parent.mkdir(parents=True)
    with tarfile.open(package,'w:gz') as archive:
        for name in dict.fromkeys(files):archive.add(ROOT/name,arcname=name)
    SPOOL.mkdir(parents=True,exist_ok=True);(SPOOL/'logs').mkdir(exist_ok=True)
    worker=SPOOL/f'worker_{stamp}.sh';worker.write_bytes((ROOT/'AnalysisZipFramework/submission/run_ml_stage186.sh').read_bytes())
    descriptor=f'''universe = vanilla
initialdir = {SPOOL}
executable = /bin/bash
transfer_executable = False
arguments = {worker.name} {phase}
transfer_input_files = {worker}, root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/{relative}
should_transfer_files = YES
transfer_output_files = ""
request_cpus = 8
request_memory = 24000MB
request_disk = 6000MB
max_retries = 0
+MaxRuntime = 86400
+PeriodicRemoveReason = "Stage186 frozen disjoint CPU allowance"
periodic_remove = (RemoteUserCpu + RemoteSysCpu) > {allowance}
+NuMuStage = "energy-ml-stage186"
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
    with tempfile.NamedTemporaryFile(prefix='nu_mu_stage186_',suffix='.tar.gz') as tmp:
        subprocess.run(['xrdcp','--silent','--force',f'root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage186/{phase}_result.tar.gz',tmp.name],check=True)
        with tarfile.open(tmp.name) as archive:archive.extractall(ROOT)
    print('COLLECTED',phase,'exit',row.get('ExitCode'));return row.get('ExitCode',1)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['submit','monitor','collect']);parser.add_argument('--phase',default='pilot');args=parser.parse_args()
    if args.action=='submit':submit(args.phase)
    elif args.action=='monitor':monitor()
    else:raise SystemExit(collect(args.phase))
