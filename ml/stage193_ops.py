"""Bounded scheduler; reuse terminal-accounting implementation, not scientific work."""
import argparse,json,subprocess,tarfile,time
from pathlib import Path
import stage192_ops as scheduler
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage193_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage193';SPOOL=Path.home()/'condor/nu_muAnalysis/stage193'
scheduler.ROOT,scheduler.OUT,scheduler.CACHE,scheduler.SPOOL=ROOT,OUT,CACHE,SPOOL
scheduler.CPU_BUDGET_S=300
monitor=scheduler.monitor
def submit(phase):
 assert phase in ['pilot','full','audit'] and not (OUT/f'{phase}_submission.json').exists()
 a=monitor();assert not a['live_N'] and a['total_CPU_s']+100<=300
 if phase!='pilot':assert json.loads((OUT/'admission.json').read_text())['admitted']
 if phase=='audit':assert json.loads((OUT/'full_summary.json').read_text())['passed']
 files=['ml/stage192_ops.py','ml/stage143_monitor.py','ml/stage192_review.py','ml/stage158_finalize.py',
  'workbook/stage192_energy_ml/protocol.json','workbook/stage192_energy_ml/full_prediction_summary.json',
  'workbook/stage193_energy_ml/protocol.json']
 files += [str(f.relative_to(ROOT)) for f in (ROOT/'ml').glob('stage193*.py')]
 files += json.loads((OUT/'protocol.json').read_text())['inputs']
 if phase=='audit':files += [str(f.relative_to(ROOT)) for f in CACHE.glob('*.json.gz')]+['workbook/stage193_energy_ml/full_accounting.json']
 stamp=str(time.time_ns());relative=Path('software/stage193')/stamp/'energy-ml-stage193.tar.gz';package=ROOT/relative;package.parent.mkdir(parents=True);CACHE.mkdir(exist_ok=True)
 with tarfile.open(package,'w:gz') as t:
  for name in dict.fromkeys(files):t.add(ROOT/name,arcname=name)
 SPOOL.mkdir(parents=True,exist_ok=True);(SPOOL/'logs').mkdir(exist_ok=True)
 worker=SPOOL/f'worker_{stamp}.sh';worker.write_bytes((ROOT/'AnalysisZipFramework/submission/run_ml_stage193.sh').read_bytes())
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
request_disk = 1000MB
max_retries = 0
+MaxRuntime = 3600
+NuMuStage = "energy-ml-stage193"
+PeriodicRemoveReason = "Stage193 frozen100CPU seconds per phase"
periodic_remove = (RemoteUserCpu + RemoteSysCpu) > 100
log = {SPOOL}/logs/$(ClusterId).$(ProcId).log
output = {SPOOL}/logs/$(ClusterId).$(ProcId).out
error = {SPOOL}/logs/$(ClusterId).$(ProcId).err
queue 1
'''
 path=SPOOL/f'{phase}_{stamp}.sub';path.write_text(descriptor);result=subprocess.check_output(['condor_submit','-terse',str(path)],text=True).strip()
 (OUT/f'{phase}_submission.json').write_text(json.dumps(dict(phase=phase,result=result,CPU_allowance_s=100,descriptor=descriptor,package=dict(path=str(relative),bytes=package.stat().st_size,files=files)),indent=2)+'\n');print(result,flush=True)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['submit','monitor','collect']);parser.add_argument('--phase',default='pilot');a=parser.parse_args()
 if a.action=='submit':submit(a.phase)
 elif a.action=='monitor':monitor()
 else:
  rc=scheduler.collect(a.phase);monitor();raise SystemExit(rc)
