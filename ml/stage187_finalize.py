"""Local exact-byte archival and terminal budget/storage closure only."""
import json,subprocess,tarfile
from pathlib import Path
from stage158_finalize import archive_exact,gnu
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage187_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage187';SOFT=ROOT/'software/stage187';SPOOL=Path.home()/'condor/nu_muAnalysis/stage187'
if __name__=='__main__':
 assert not (OUT/'storage_cleanup.json').exists();a=json.loads((OUT/'scheduler_accounting.json').read_text());p=json.loads((OUT/'protocol.json').read_text());assert a['live_N']==0 and all(j['JobStatus']==4 and j['ExitCode']==0 for j in a['jobs']);assert json.loads((OUT/'independent_validation.json').read_text())['passed']
 sources={};outputs={};logs={};times={};transports=[];inputs={};budgets=[]
 for phase in ['pilot','analysis','audit']:
  s=json.loads((OUT/f'{phase}_submission.json').read_text());job=next(j for j in a['jobs'] if j['ClusterId']==int(s['result'].split('.')[0]));cpu=job['RemoteUserCpu']+job['RemoteSysCpu'];assert cpu<=p['phase_CPU_caps_s'][phase];budgets.append(dict(phase=phase,CPU_s=cpu,cap_CPU_s=p['phase_CPU_caps_s'][phase]))
  package=ROOT/s['package']['path']
  with tarfile.open(package) as t:
   for m in t:
    if not m.isfile():continue
    data=t.extractfile(m).read()
    if m.name.endswith(('.py','.sh','.cxx','protocol.json')):sources[phase+'/'+m.name]=data
    else:inputs[m.name]=data
  sources[phase+'/submission/descriptor.sub']=s['descriptor'].encode();sources[phase+'/submission/worker.sh']=(SPOOL/f'worker_{package.parent.name}.sh').read_bytes()
  result=CACHE/f'{phase}_result.tar.gz'
  with tarfile.open(result) as t:
   for m in t:
    if not m.isfile():continue
    data=t.extractfile(m).read();outputs[m.name]=data
    if m.name.endswith('.log'):logs[phase+'/'+m.name]=data
    if m.name.endswith('_time.txt'):times[phase+'/'+m.name]=data
  transports += [package,result]
 assert sum(r['CPU_s'] for r in budgets)==a['total_CPU_s']<=240
 for name,data in inputs.items():assert (ROOT/name).read_bytes()==data,name
 for name,data in outputs.items():assert (ROOT/name).read_bytes()==data,name
 for f in (ROOT/'ml').glob('stage187*.py'):sources['final/'+str(f.relative_to(ROOT))]=f.read_bytes()
 SOFT.mkdir(exist_ok=True);archive_exact(SOFT/'source_snapshots.tar.gz',sources);archive_exact(SOFT/'worker_logs.tar.gz',logs);archive_exact(SOFT/'execution_audits.tar.gz',times)
 (OUT/'process_resources.json').write_text(json.dumps([dict(phase=f.stem,**gnu(f)) for f in OUT.glob('*_time.txt')],indent=2)+'\n')
 queue=json.loads(subprocess.check_output(['condor_q','-json','-attributes','ClusterId,Iwd'],text=True).strip() or '[]');assert all(Path(j.get('Iwd','/'))!=SPOOL for j in queue)
 spool=[f for f in SPOOL.rglob('*') if f.is_file()];assert all(f.suffix in ['.sh','.sub','.out','.err','.log'] for f in spool);archive_exact(SOFT/'terminal_spool.tar.gz',{str(f.relative_to(SPOOL)):f.read_bytes() for f in spool})
 before=json.loads((ROOT/'workbook/stage158_energy_ml/preexisting_asset_snapshot.json').read_text());assert all((ROOT/k).stat().st_size==v['bytes'] and (ROOT/k).stat().st_mtime_ns==v['mtime_ns'] for k,v in before.items())
 scalarfiles=[OUT/n for n in ['pilot_result.json','ledger.json','parent_ledger.tsv','source_ledger.tsv','energy_source_ledger.png','energy_source_ledger.pdf']];total=sum(f.stat().st_size for f in scalarfiles);assert total<=2097152
 deleted=[]
 for f in dict.fromkeys(transports+spool+list(OUT.glob('*.log'))+list(OUT.glob('*_time.txt'))):deleted.append(dict(path=str(f),bytes=f.stat().st_size));f.unlink()
 for f in transports:
  if f.parent!=CACHE and f.parent.exists() and not any(f.parent.iterdir()):f.parent.rmdir()
 (SPOOL/'execution_index.json').write_text(json.dumps(dict(stage=187,jobs=[j['ClusterId'] for j in a['jobs']],archive=str(SOFT/'terminal_spool.tar.gz')),indent=2)+'\n')
 result=dict(passed=True,starts=a['starts'],scheduler_CPU_s=a['total_CPU_s'],scheduler_aggregate_wall_s=a['total_execute_wall_s'],phase_budgets=budgets,CPU_cap_s=240,live_N=0,deleted_B=sum(r['bytes'] for r in deleted),deleted=deleted,retained_scientific_scalar_plot_B=total,cap_B=2097152,original_input_assets_bytes_verified_N=len(inputs),Stage54_preserved_N=len(before),new_G4=0,new_fits=0,new_forward=0,overall_complete=False,promotion=False)
 (OUT/'storage_cleanup.json').write_text(json.dumps(result,indent=2)+'\n');print({k:v for k,v in result.items() if k not in ['deleted']})
