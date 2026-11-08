"""Three sequential bounded Condor jobs, no automatic scientific retry."""
import argparse,json,subprocess,tarfile,tempfile,time
from pathlib import Path
from stage143_monitor import ATTR
CPU_BUDGET_S=1200
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage194_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage194';SPOOL=Path.home()/'condor/nu_muAnalysis/stage194'
def monitor():
 old=json.loads((OUT/'scheduler_accounting.json').read_text()) if (OUT/'scheduler_accounting.json').exists() else {};terminal={r['ClusterId']:r for r in old.get('jobs',[]) if r['JobStatus'] in [3,4]};rows=[]
 for f in OUT.glob('*_submission.json'):
  cluster=int(json.loads(f.read_text())['result'].split('.')[0])
  if cluster in terminal:rows.append(terminal[cluster]);continue
  data=json.loads(subprocess.check_output(['condor_q',str(cluster),'-json','-attributes',','.join(ATTR)],text=True).strip() or '[]')
  if not data:data=json.loads(subprocess.check_output(['condor_history',str(cluster),'-limit','1','-json','-attributes',','.join(ATTR)],text=True).strip() or '[]')
  assert len(data)==1,'Unresolved original job; no duplicate submission';rows.extend(data)
 result=dict(jobs=rows,live_N=sum(r['JobStatus'] not in [3,4] for r in rows),starts=sum(r.get('NumJobStarts',0) for r in rows),total_CPU_s=sum(r.get('RemoteUserCpu',0)+r.get('RemoteSysCpu',0) for r in rows),total_execute_wall_s=sum(r.get('RemoteWallClockTime',0) for r in rows),CPU_budget_s=CPU_BUDGET_S)
 (OUT/'scheduler_accounting.json').write_text(json.dumps(result,indent=2)+'\n');print({k:v for k,v in result.items() if k!='jobs'},flush=True);return result
def submit(phase):
 assert phase in ['pilot','pilot_repair','pilot_repair2','review','full','audit'] and not (OUT/f'{phase}_submission.json').exists();account=monitor();assert account['live_N']==0
 p=json.loads((OUT/'protocol.json').read_text());allowance=(400-account['total_CPU_s'] if phase.startswith('pilot_repair') or phase=='review' else p['resources']['phase_CPU_s'][phase]);assert allowance>0 and account['total_CPU_s']+allowance<=1200
 files=['ml/stage192_links.cxx','ml/stage192_review.py','workbook/stage192_energy_ml/protocol.json','workbook/stage192_energy_ml/full_prediction_summary.json','ntuples/energy_ml_stage192/full_native.json.gz','setup_env.sh','ml/stage143_monitor.py','ml/stage158_finalize.py','workbook/stage194_energy_ml/protocol.json','workbook/stage194_energy_ml/pinned_source_evidence.json','workbook/stage194_energy_ml/build_spec.json']+[str(f.relative_to(ROOT)) for f in (ROOT/'ml').glob('stage194*.py')]+['ml/stage194_links.cxx','ntuples/energy_ml_stage188/full_native.json.gz']
 if phase=='full':
  assert json.loads((OUT/'admission.json').read_text())['admitted'];files+=['workbook/stage194_energy_ml/admission.json']
 if phase in ['review','audit']:
  files += [str(f.relative_to(ROOT)) for f in CACHE.glob('*_native.json.gz')]
  files += [str(f.relative_to(ROOT)) for f in OUT.glob('*_summary.json')]
  files += [str(f.relative_to(ROOT)) for f in OUT.glob('*_time.txt')]
 if phase=='review':files+=['workbook/stage194_energy_ml/scheduler_accounting.json']
 stamp=str(time.time_ns());relative=Path('software/stage194')/stamp/'energy-ml-stage194.tar.gz';package=ROOT/relative;package.parent.mkdir(parents=True);CACHE.mkdir(exist_ok=True)
 with tarfile.open(package,'w:gz') as t:
  for name in dict.fromkeys(files):t.add(ROOT/name,arcname=name)
 SPOOL.mkdir(parents=True,exist_ok=True);(SPOOL/'logs').mkdir(exist_ok=True);worker=SPOOL/f'worker_{stamp}.sh';worker.write_bytes((ROOT/'AnalysisZipFramework/submission/run_ml_stage194.sh').read_bytes())
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
request_disk = 6000MB
max_retries = 0
+MaxRuntime = 86400
+NuMuStage = "energy-ml-stage194"
+PeriodicRemoveReason = "Stage192 frozen disjoint CPU allowance"
periodic_remove = (RemoteUserCpu + RemoteSysCpu) > {allowance}
log = {SPOOL}/logs/$(ClusterId).$(ProcId).log
output = {SPOOL}/logs/$(ClusterId).$(ProcId).out
error = {SPOOL}/logs/$(ClusterId).$(ProcId).err
queue 1
'''
 path=SPOOL/f'{phase}_{stamp}.sub';path.write_text(descriptor);result=subprocess.check_output(['condor_submit','-terse',str(path)],text=True).strip();(OUT/f'{phase}_submission.json').write_text(json.dumps(dict(phase=phase,result=result,CPU_allowance_s=allowance,descriptor=descriptor,package=dict(path=str(relative),bytes=package.stat().st_size,files=files)),indent=2)+'\n');print(result,flush=True)
def collect(phase):
 a=monitor();s=json.loads((OUT/f'{phase}_submission.json').read_text());j=next(r for r in a['jobs'] if r['ClusterId']==int(s['result'].split('.')[0]));assert j['JobStatus'] in [3,4]
 with tempfile.NamedTemporaryFile(suffix='.tar.gz') as tmp:
  subprocess.run(['xrdcp','--silent','--force',f'root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/{CACHE.relative_to(ROOT)}/{phase}_result.tar.gz',tmp.name],check=True)
  with tarfile.open(tmp.name) as t:t.extractall(ROOT)
 print('COLLECTED',phase,j.get('ExitCode'));return j.get('ExitCode',1)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['submit','monitor','collect']);parser.add_argument('--phase',default='pilot');a=parser.parse_args()
 if a.action=='submit':submit(a.phase)
 elif a.action=='monitor':monitor()
 else:raise SystemExit(collect(a.phase))
