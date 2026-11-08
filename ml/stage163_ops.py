"""Scoped scheduling/transport and disjoint frozen CPU allowances for Stage163."""
import argparse,json,subprocess,tarfile,tempfile,time
from pathlib import Path
from stage143_monitor import ATTR
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage163_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage163';SPOOL=Path.home()/'condor/nu_muAnalysis/stage163'
def monitor():
 submissions=[json.loads(p.read_text()) for p in OUT.glob('*_submission.json')]
 old=json.loads((OUT/'scheduler_accounting.json').read_text()) if (OUT/'scheduler_accounting.json').exists() else {}
 terminal={r['ClusterId']:r for r in old.get('jobs',[]) if r['JobStatus'] in [3,4]};ids={int(r['result'].split('.')[0]) for r in submissions}
 query=sorted(ids-set(terminal));live=[];missing=[]
 if query:
  text=subprocess.check_output(['condor_q']+[str(i) for i in query]+['-json','-attributes',','.join(ATTR+['RequestMemory','MemoryUsage','CpusUsage'])],text=True).strip();live=json.loads(text) if text else []
  absent=set(query)-{r['ClusterId'] for r in live}
  if absent:
   text=subprocess.check_output(['condor_history','-constraint',' || '.join(f'ClusterId == {i}' for i in sorted(absent)),'-limit',str(len(absent)),'-since','CompletionDate < 1794084000','-json','-attributes',','.join(ATTR+['RequestMemory','MemoryUsage','CpusUsage'])],text=True).strip()
   for r in json.loads(text) if text else []:terminal[r['ClusterId']]=r
   missing=sorted(absent-set(terminal))
 rows=list(terminal.values())+live
 report=dict(jobs=rows,live_N=len(live),unresolved_ids=missing,total_CPU_s=sum(r.get('RemoteUserCpu',0)+r.get('RemoteSysCpu',0) for r in rows),total_execute_wall_s=sum(r.get('RemoteWallClockTime',0) for r in rows),starts=sum(r.get('NumJobStarts',0) for r in rows),CPU_budget_s=12000)
 (OUT/'scheduler_accounting.json').write_text(json.dumps(report,indent=2)+'\n');print({k:v for k,v in report.items() if k!='jobs'},flush=True)
 if report['total_CPU_s']>=12000 and live:
  subprocess.run(['condor_rm']+[f"{r['ClusterId']}.{r['ProcId']}" for r in live],check=True);raise RuntimeError('Frozen cumulative CPU exhausted')
 return report

def submit(phase):
 assert phase in ['pilot','repeat','admission','admission_repair','source_repair','source_repair_retry','fit','validate']+[f'batch_{i:02d}' for i in range(8)]+[f'batch_{i:02d}_repair' for i in range(2,8)]
 assert not (OUT/f'{phase}_submission.json').exists()
 assert (OUT/'protocol.json').read_bytes()==(ROOT/'workbook/stage162_energy_ml/next_execution_contract.json').read_bytes()
 assert (ROOT/'workbook/stage162_energy_ml/storage_cleanup.json').exists()
 account=monitor();assert not account['unresolved_ids'];used=account['total_CPU_s']
 assert account['live_N']<(4 if phase.startswith('batch') else 1)
 if phase=='pilot':allowance=700
 elif phase=='repeat':allowance=int(700-used);assert (OUT/'pilot_exitcode.txt').read_text().strip()=='0'
 elif phase.startswith('admission'):allowance=min(100,12000-used);assert (OUT/'repeat_exitcode.txt').read_text().strip()=='0'
 elif phase.startswith('source_repair'):
  audit_ids={int(json.loads(p.read_text())['result'].split('.')[0]) for p in OUT.glob('source_repair*_submission.json')}
  allowance=int(100-sum(r.get('RemoteUserCpu',0)+r.get('RemoteSysCpu',0) for r in account['jobs'] if r['ClusterId'] in audit_ids));assert account['live_N']==0
 elif phase.startswith('batch'):
  gate=json.loads((OUT/'admission.json').read_text());assert gate['admitted']
  budget_path=OUT/'batch_budget.json'
  if not budget_path.exists():
   assert account['live_N']==0
   assert used+gate['projected_full_3x_CPU_s']+1500<=12000
   per_batch=int((12000-used-1500)//8)
   budget=dict(already_used_scheduler_CPU_s=used,batch_N=8,per_batch_CPU_allowance_s=per_batch,
    audit_fit_reserve_CPU_s=1500,CPU_budget_s=12000,
    committed_CPU_s=used+8*per_batch+1500,
    reason='Resource-only gate refresh after completed admission; fixed disjoint allowances for all batches')
   budget_path.write_text(json.dumps(budget,indent=2)+'\n')
  budget=json.loads(budget_path.read_text());allowance=budget['per_batch_CPU_allowance_s']
  if phase.endswith('_repair'):
   assert json.loads((OUT/'source_repair_audit.json').read_text())['passed']
   original=phase.removesuffix('_repair')
   cluster=int(json.loads((OUT/f'{original}_submission.json').read_text())['result'].split('.')[0])
   prior=next(r for r in account['jobs'] if r['ClusterId']==cluster)
   assert prior['JobStatus'] in [3,4]
   allowance-=int(prior.get('RemoteUserCpu',0)+prior.get('RemoteSysCpu',0))
 else:
  assert all((OUT/(f'batch_{i:02d}_repair_exitcode.txt' if (OUT/f'batch_{i:02d}_repair_submission.json').exists() else f'batch_{i:02d}_exitcode.txt')).read_text().strip()=='0' for i in range(8))
  audit_ids={int(json.loads(p.read_text())['result'].split('.')[0]) for p in OUT.glob('source_repair*_submission.json')}
  previous=sum(r.get('RemoteUserCpu',0)+r.get('RemoteSysCpu',0) for r in account['jobs'] if r['ClusterId'] in audit_ids)
  if phase=='validate':
   cluster=int(json.loads((OUT/'fit_submission.json').read_text())['result'].split('.')[0]);previous+=sum(r.get('RemoteUserCpu',0)+r.get('RemoteSysCpu',0) for r in account['jobs'] if r['ClusterId']==cluster)
  allowance=int(min(1500-previous,12000-used));assert allowance>0
 assert 0<allowance<=12000-used
 files=['ml/audited_features.py','ml/configs/audited_features.json','ml/stage158_finalize.py','ml/stage119_curve_common.py','ml/stage119_reportcurve.py',
  'ntuples/energy_ml_stage119/old_input.npz','workbook/stage124_energy_ml/native_contract.json','workbook/stage87_energy_ml/protocol.json',
  'workbook/stage163_energy_ml/protocol.json','workbook/stage163_energy_ml/field_mapping.json','workbook/stage163_energy_ml/amplitude_definition.json','workbook/stage163_energy_ml/scheduler_accounting.json',
  'ml/configs/low_energy_files.tsv','ml/configs/alternative_support_pilot.json','workbook/stage81_energy_ml/source_plan.json','workbook/stage82_energy_ml/production_protocol.json','workbook/stage83_energy_ml/protocol.json']
 files += [str(p.relative_to(ROOT)) for p in sorted((ROOT/'ml').glob('stage163_*.py'))]
 if phase!='pilot':files+=['workbook/stage163_energy_ml/source_manifest.json']
 if phase.startswith('admission'):files += [f'{base}/{name}' for base,names in [('workbook/stage163_energy_ml',['pilot_summary.json','repeat_summary.json','pilot_time.txt','repeat_time.txt']),('ntuples/energy_ml_stage163',['pilot.npz','repeat.npz'])] for name in names]
 if phase.startswith('batch') or phase in ['fit','validate']:files+=['workbook/stage163_energy_ml/admission.json']
 if phase.startswith('batch') or phase in ['fit','validate']:files+=['workbook/stage163_energy_ml/batch_budget.json']
 if phase.startswith('source_repair'):files+=['workbook/stage163_energy_ml/source_manifest_original.json']
 if phase=='fit':
  files += [f'ntuples/energy_ml_stage163/{p}.npz' for p in ['pilot','repeat']+[f'batch_{i:02d}' for i in range(8)]]
  files += [f'workbook/stage163_energy_ml/batch_{i:02d}_summary.json' for i in range(8)]
  files += ['ml/artifacts/stage87/predictions.npz']
 if phase=='validate':files += ['ntuples/energy_ml_stage163/features.npz','ml/artifacts/stage163','ml/artifacts/stage87/predictions.npz','workbook/stage163_energy_ml/metrics.tsv','workbook/stage163_energy_ml/paired.tsv','workbook/stage163_energy_ml/comparison_summary.json']
 stamp=str(time.time_ns());relative=Path('software/stage163')/stamp/'energy-ml-stage163.tar.gz';package=ROOT/relative;package.parent.mkdir(parents=True)
 with tarfile.open(package,'w:gz') as archive:
  for name in files:archive.add(ROOT/name,arcname=name)
 SPOOL.mkdir(parents=True,exist_ok=True);(SPOOL/'logs').mkdir(exist_ok=True);worker=SPOOL/f'worker_{stamp}.sh';worker.write_bytes((ROOT/'AnalysisZipFramework/submission/run_ml_stage163.sh').read_bytes())
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
request_disk = 5000MB
max_retries = 0
+MaxRuntime = 86400
+PeriodicRemoveReason = "Stage163 frozen CPU allowance"
periodic_remove = (RemoteUserCpu + RemoteSysCpu) > {allowance}
+NuMuStage = "energy-ml-stage163"
log = {SPOOL}/logs/$(ClusterId).$(ProcId).log
output = {SPOOL}/logs/$(ClusterId).$(ProcId).out
error = {SPOOL}/logs/$(ClusterId).$(ProcId).err
queue 1
'''
 path=SPOOL/f'{phase}_{stamp}.sub';path.write_text(descriptor);result=subprocess.check_output(['condor_submit','-terse',str(path)],text=True).strip()
 (OUT/f'{phase}_submission.json').write_text(json.dumps(dict(phase=phase,result=result,CPU_allowance_s=allowance,descriptor=descriptor,package=dict(path=str(relative),bytes=package.stat().st_size,files=files)),indent=2)+'\n');print(result,flush=True)

def collect(phase):
 account=monitor();cluster=int(json.loads((OUT/f'{phase}_submission.json').read_text())['result'].split('.')[0]);row=next(r for r in account['jobs'] if r['ClusterId']==cluster);assert row['JobStatus'] in [3,4]
 with tempfile.NamedTemporaryFile(prefix='nu_mu_stage163_',suffix='.tar.gz') as target:
  subprocess.run(['xrdcp','--silent','--force',f'root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage163/{phase}_result.tar.gz',target.name],check=True)
  with tarfile.open(target.name,'r:gz') as archive:archive.extractall(ROOT)
 print('COLLECTED',phase,'exit',row.get('ExitCode'),flush=True);return row.get('ExitCode',1)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['submit','monitor','collect']);parser.add_argument('--phase',default='pilot');a=parser.parse_args()
 if a.action=='submit':submit(a.phase)
 elif a.action=='monitor':monitor()
 else:raise SystemExit(collect(a.phase))
