"""Terminal exact-byte archival, with distinct failed/successful attempt versions."""
import json,subprocess,tarfile
from pathlib import Path
from stage158_finalize import archive_exact,gnu
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage186_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage186';SOFT=ROOT/'software/stage186';SPOOL=Path.home()/'condor/nu_muAnalysis/stage186'
if __name__=='__main__':
 assert not (OUT/'storage_cleanup.json').exists()
 account=json.loads((OUT/'scheduler_accounting.json').read_text());assert account['live_N']==0 and all(r['JobStatus']==4 for r in account['jobs'])
 assert json.loads((OUT/'independent_validation.json').read_text())['passed'];assert json.loads((OUT/'resource_validation.json').read_text())['passed']
 submissions=sorted([json.loads(p.read_text()) for p in OUT.glob('*_submission.json')],key=lambda r:int(r['result'].split('.')[0]));sources={};logs={};times={};transports=[];last_result={};input_assets={}
 by_cluster={r['ClusterId']:r for r in account['jobs']};protocol=json.loads((OUT/'protocol.json').read_text());budget_rows=[]
 assert set(by_cluster)=={int(r['result'].split('.')[0]) for r in submissions}
 for r in submissions:
  job=by_cluster[int(r['result'].split('.')[0])];phase=r['phase'];cpu=job['RemoteUserCpu']+job['RemoteSysCpu']
  family='production_'+phase.split('_')[1] if phase.startswith(('production_','repair_')) else 'fit_audit' if phase in ['fit','fit_repair','audit'] else 'pilot'
  budget_rows.append(dict(phase=phase,family=family,CPU_s=cpu,exit=job['ExitCode']))
 limits=dict(pilot=4000,fit_audit=8000,**{f'production_{i}':v for i,v in enumerate(protocol['production_job_CPU_allowances_s'])})
 used={k:sum(r['CPU_s'] for r in budget_rows if r['family']==k) for k in limits}
 assert all(used[k]<=v for k,v in limits.items()),(used,limits)
 assert sum(used.values())==account['total_CPU_s']<=180000
 assert sum(v for k,v in used.items() if k.startswith('production_'))<=168000
 (OUT/'budget_validation.json').write_text(json.dumps(dict(passed=True,measured_CPU_s=used,limits_CPU_s=limits,attempts=budget_rows,total_CPU_s=account['total_CPU_s'],total_cap_CPU_s=180000,all_failed_attempts_counted=True),indent=2)+'\n')
 for r in submissions:
  phase=r['phase'];package=ROOT/r['package']['path']
  with tarfile.open(package) as t:
   for member in t:
    if not member.isfile():continue
    data=t.extractfile(member).read()
    if member.name.endswith(('.py','.hxx','.sh','.xml','protocol.json','source_producers.json')):sources[phase+'/'+member.name]=data
    elif member.name.endswith(('.npz','.ubj')):input_assets[member.name]=data
  sources[phase+'/submission/descriptor.sub']=r['descriptor'].encode();sources[phase+'/submission/worker.sh']=(SPOOL/f'worker_{package.parent.name}.sh').read_bytes()
  result=CACHE/f'{phase}_result.tar.gz'
  with tarfile.open(result) as t:
   for member in t:
    if not member.isfile():continue
    data=t.extractfile(member).read();last_result[member.name]=data
    if member.name.endswith('.log'):logs[phase+'/'+member.name]=data
    if member.name.endswith('_time.txt'):times[phase+'/'+member.name]=data
  transports += [package,result]
 # Older failed attempt logs may have been superseded by a repaired native run;
 # the phase-qualified bytes above retain each exact submitted result separately.
 for name,data in last_result.items():assert (ROOT/name).read_bytes()==data,name
 for name,data in input_assets.items():assert (ROOT/name).read_bytes()==data,name
 for p in (ROOT/'ml').glob('stage186*'):
  if p.is_file():sources['final/'+str(p.relative_to(ROOT))]=p.read_bytes()
 seen={};unique={};index={}
 for name,data in sources.items():
  if data not in seen:seen[data]=name;unique[name]=data
  index[name]=seen[data]
 unique['source_versions.json']=(json.dumps(index,indent=2)+'\n').encode();archive_exact(SOFT/'source_snapshots.tar.gz',unique)
 archive_exact(SOFT/'worker_logs.tar.gz',logs);archive_exact(SOFT/'execution_audits.tar.gz',times)
 native=sorted(OUT.glob('full_*_summary.json'))+[OUT/'pilot_0_summary.json',OUT/'repeat_0_summary.json']
 archive_exact(SOFT/'native_audits.tar.gz',{str(p.relative_to(ROOT)):p.read_bytes() for p in native})
 (OUT/'process_resources.json').write_text(json.dumps([dict(task=p.stem,**gnu(p)) for p in OUT.glob('*_time.txt')],indent=2)+'\n')
 queue=json.loads(subprocess.check_output(['condor_q','-json','-attributes','ClusterId,Iwd'],text=True).strip() or '[]');assert all(Path(r.get('Iwd','/'))!=SPOOL for r in queue)
 spool=[p for p in SPOOL.rglob('*') if p.is_file()];assert all(p.suffix in ['.sh','.sub','.out','.err','.log'] for p in spool)
 archive_exact(SOFT/'terminal_spool.tar.gz',{str(p.relative_to(SPOOL)):p.read_bytes() for p in spool})
 baseline=json.loads((ROOT/'workbook/stage158_energy_ml/preexisting_asset_snapshot.json').read_text());assert all((ROOT/k).stat().st_size==v['bytes'] and (ROOT/k).stat().st_mtime_ns==v['mtime_ns'] for k,v in baseline.items())
 arrays=list(CACHE.glob('*.npz'))+list((ROOT/'ml/artifacts/stage186').glob('*'));total=sum(p.stat().st_size for p in arrays);assert total<=67108864
 assert total==json.loads((OUT/'resource_validation.json').read_text())['current_scientific_array_model_B']
 # Keep certified full scalar shards and merged cohort for model reproduction;
 # remove only exact verified transports and archived verbose text/spool.
 paths=transports+spool+list(OUT.glob('*.log'))+list(OUT.glob('*_time.txt'))+native;deleted=[]
 for path in dict.fromkeys(paths):deleted.append(dict(path=str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),bytes=path.stat().st_size));path.unlink()
 for path in transports:
  if path.parent!=CACHE and path.parent.exists() and not any(path.parent.iterdir()):path.parent.rmdir()
 (SPOOL/'execution_index.json').write_text(json.dumps(dict(stage=186,terminal_jobs=[r['ClusterId'] for r in account['jobs']],archive=str(SOFT/'terminal_spool.tar.gz')),indent=2)+'\n')
 result=dict(passed=True,deleted_bytes=sum(r['bytes'] for r in deleted),deleted=deleted,retained_new_scalar_model_B=total,cap_B=67108864,starts=account['starts'],scheduler_CPU_s=account['total_CPU_s'],scheduler_aggregate_wall_s=account['total_execute_wall_s'],live_N=0,failed_job_N=sum(r.get('ExitCode')!=0 for r in account['jobs']),Stage54_preserved=True,queue_Iwd_checked=True,G4_N=0,energy_fits=9,new_baseline_fits=0,overall_complete=False)
 (OUT/'storage_cleanup.json').write_text(json.dumps(result,indent=2)+'\n');print({k:v for k,v in result.items() if k!='deleted'})
