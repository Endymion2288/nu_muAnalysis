"""Finite Condor scheduling with disjoint phase caps and immutable protocol."""
import argparse
import json
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path
from stage143_monitor import ATTR

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage191_energy_ml'
CACHE=ROOT/'ntuples/energy_ml_stage191';SPOOL=Path.home()/'condor/nu_muAnalysis/stage191'


def monitor():
    old=json.loads((OUT/'scheduler_accounting.json').read_text()) if (OUT/'scheduler_accounting.json').exists() else {}
    terminal={r['ClusterId']:r for r in old.get('jobs',[]) if r['JobStatus'] in [3,4]}
    ids={int(json.loads(f.read_text())['result'].split('.')[0]) for f in OUT.glob('*_submission.json')}
    query=ids-set(terminal);live=[]
    if query:
        live=json.loads(subprocess.check_output(['condor_q',*map(str,sorted(query)),'-json','-attributes',','.join(ATTR)],text=True).strip() or '[]')
        absent=query-{r['ClusterId'] for r in live}
        if absent:
            rows=json.loads(subprocess.check_output(['condor_history','-constraint',' || '.join(f'ClusterId == {i}' for i in sorted(absent)),'-limit',str(len(absent)),'-json','-attributes',','.join(ATTR)],text=True).strip() or '[]')
            terminal.update({r['ClusterId']:r for r in rows})
        assert not absent-set(terminal),'Unresolved original job; never duplicate'
    rows=list(terminal.values())+live
    a=dict(jobs=rows,live_N=len(live),starts=sum(r.get('NumJobStarts',0) for r in rows),
        total_CPU_s=sum(r.get('RemoteUserCpu',0)+r.get('RemoteSysCpu',0) for r in rows),
        total_execute_wall_s=sum(r.get('RemoteWallClockTime',0) for r in rows),CPU_budget_s=60000)
    (OUT/'scheduler_accounting.json').write_text(json.dumps(a,indent=2)+'\n')
    print({k:v for k,v in a.items() if k!='jobs'},flush=True);return a


def submit(phase):
    assert not (OUT/f'{phase}_submission.json').exists()
    p=json.loads((OUT/'protocol.json').read_text());a=monitor()
    if (OUT/'pilot_submission.json').exists():
        with tarfile.open(ROOT/json.loads((OUT/'pilot_submission.json').read_text())['package']['path']) as t:
            assert t.extractfile('workbook/stage191_energy_ml/protocol.json').read()==(OUT/'protocol.json').read_bytes()
    repair=phase.startswith('repair')
    production=phase.startswith('production_') or repair
    if production:
        assert 0<=int(phase.split('_')[1])<5 and a['live_N']<4
        assert json.loads((OUT/'admission.json').read_text())['admitted'];allowance=9600
        if repair:
            family=int(phase.split('_')[1]);original=json.loads((OUT/f'production_{family}_submission.json').read_text())
            job=next(j for j in a['jobs'] if j['ClusterId']==int(original['result'].split('.')[0]))
            assert job['JobStatus']==4 and job['ExitCode']==1
            failed=[r['group'] for r in json.loads((OUT/f'production_{family}_driver.json').read_text()) if r['exit']!=0]
            assert failed==[32]
            allowance-=job.get('RemoteUserCpu',0)+job.get('RemoteSysCpu',0)
            for previous in OUT.glob(f'repair*_{family}_submission.json'):
                previous_job=next(j for j in a['jobs'] if j['ClusterId']==int(json.loads(previous.read_text())['result'].split('.')[0]))
                assert previous_job['JobStatus']==4 and previous_job['ExitCode']==1
                allowance-=previous_job.get('RemoteUserCpu',0)+previous_job.get('RemoteSysCpu',0)
            assert allowance>0
            (OUT/f'{phase}_plan.json').write_text(json.dumps(dict(groups=failed,remaining_original_family_CPU_s=allowance),indent=2)+'\n')
    else:
        assert a['live_N']==0
        allowance={'pilot':3000,'review':1000,'review_repair':1000,'fit':3000,'audit':5000}[phase]
        if phase=='review_repair':
            previous=int(json.loads((OUT/'review_submission.json').read_text())['result'].split('.')[0])
            job=next(j for j in a['jobs'] if j['ClusterId']==previous)
            assert job['JobStatus']==4 and job['ExitCode']==1
            allowance-=job.get('RemoteUserCpu',0)+job.get('RemoteSysCpu',0)
            assert allowance>0
    # Charge all outstanding allowances before permitting additional jobs.
    outstanding=sum(json.loads(f.read_text())['CPU_allowance_s'] for f in OUT.glob('*_submission.json')
        if any(j['ClusterId']==int(json.loads(f.read_text())['result'].split('.')[0]) and j['JobStatus'] not in [3,4] for j in a['jobs']))
    assert a['total_CPU_s']+outstanding+allowance<=60000
    files=['setup_env.sh','ml/stage143_monitor.py','ml/stage158_finalize.py','ml/stage188_native.hxx','ml/stage188_bridge.cxx',
        'workbook/stage129_energy_ml/extraction_contract.json','workbook/stage191_energy_ml/protocol.json',
        'workbook/stage191_energy_ml/build_spec.json','workbook/stage191_energy_ml/pinned_source_evidence.json']
    files += [str(f.relative_to(ROOT)) for f in (ROOT/'ml').glob('stage191_*.py')]
    if phase in ['review','review_repair','fit','audit']:
        files+=['ml/audited_features.py','ml/configs/audited_features.json','ml/stage129_energy.py','ml/stage119_curve_common.py','ml/stage119_reportcurve.py',
            'workbook/stage87_energy_ml/protocol.json','ntuples/energy_ml_stage119/old_input.npz','ml/artifacts/stage87/predictions.npz']
        files += [str(f.relative_to(ROOT)) for f in CACHE.glob('*.json.gz')]
        files += [str(f.relative_to(ROOT)) for f in OUT.glob('*_summary.json')]
        files += [str(f.relative_to(ROOT)) for f in OUT.glob('*_time.txt')]
    if phase in ['review','review_repair']:files+=['workbook/stage191_energy_ml/scheduler_accounting.json']
    if production or phase in ['fit','audit']:files+=['workbook/stage191_energy_ml/admission.json','workbook/stage191_energy_ml/pilot_validation.json']
    if phase in ['fit','audit']:
        assert all((CACHE/f'full_{i}.json.gz').exists() for i in range(35))
    if repair:files+=[f'workbook/stage191_energy_ml/{phase}_plan.json']
    if phase=='audit':
        files += [str(f.relative_to(ROOT)) for f in (ROOT/'ml/artifacts/stage191').glob('*') if f.is_file()]
        files += [str(f.relative_to(ROOT)) for f in CACHE.glob('*.npz')]
        files += [str(f.relative_to(ROOT)) for f in OUT.glob('ift_*.tsv')]
        files += ['workbook/stage191_energy_ml/fit_summary.json','workbook/stage191_energy_ml/ift_summary.json','workbook/stage191_energy_ml/fits.json']
    stamp=str(time.time_ns());relative=Path('software/stage191')/stamp/'energy-ml-stage191.tar.gz'
    package=ROOT/relative;package.parent.mkdir(parents=True);CACHE.mkdir(exist_ok=True)
    with tarfile.open(package,'w:gz') as t:
        for name in dict.fromkeys(files):t.add(ROOT/name,arcname=name)
    SPOOL.mkdir(parents=True,exist_ok=True);(SPOOL/'logs').mkdir(exist_ok=True)
    worker=SPOOL/f'worker_{stamp}.sh';worker.write_bytes((ROOT/'AnalysisZipFramework/submission/run_ml_stage191.sh').read_bytes())
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
+NuMuStage = "energy-ml-stage191"
+PeriodicRemoveReason = "Stage191 frozen disjoint CPU allowance"
periodic_remove = (RemoteUserCpu + RemoteSysCpu) > {allowance}
log = {SPOOL}/logs/$(ClusterId).$(ProcId).log
output = {SPOOL}/logs/$(ClusterId).$(ProcId).out
error = {SPOOL}/logs/$(ClusterId).$(ProcId).err
queue 1
'''
    descriptor_path=SPOOL/f'{phase}_{stamp}.sub';descriptor_path.write_text(descriptor)
    result=subprocess.check_output(['condor_submit','-terse',str(descriptor_path)],text=True).strip()
    (OUT/f'{phase}_submission.json').write_text(json.dumps(dict(phase=phase,result=result,CPU_allowance_s=allowance,descriptor=descriptor,
        package=dict(path=str(relative),bytes=package.stat().st_size,files=files)),indent=2)+'\n');print(result,flush=True)


def collect(phase):
    a=monitor();cluster=int(json.loads((OUT/f'{phase}_submission.json').read_text())['result'].split('.')[0])
    job=next(j for j in a['jobs'] if j['ClusterId']==cluster);assert job['JobStatus'] in [3,4]
    with tempfile.NamedTemporaryFile(suffix='.tar.gz') as tmp:
        subprocess.run(['xrdcp','--silent','--force',f'root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage191/{phase}_result.tar.gz',tmp.name],check=True)
        with tarfile.open(tmp.name) as t:t.extractall(ROOT)
    print('COLLECTED',phase,job.get('ExitCode'));return job.get('ExitCode',1)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['monitor','submit','collect']);parser.add_argument('--phase',default='pilot');a=parser.parse_args()
    if a.action=='submit':submit(a.phase)
    elif a.action=='monitor':monitor()
    else:raise SystemExit(collect(a.phase))
