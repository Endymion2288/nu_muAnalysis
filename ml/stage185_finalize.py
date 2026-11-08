"""Exact terminal archival and deletion of verified transports only."""
import json
import subprocess
import tarfile
from pathlib import Path
from stage158_finalize import archive_exact,gnu
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage185_energy_ml'
CACHE=ROOT/'ntuples/energy_ml_stage185';SOFT=ROOT/'software/stage185';SPOOL=Path.home()/'condor/nu_muAnalysis/stage185'

if __name__=='__main__':
    assert not (OUT/'storage_cleanup.json').exists()
    account=json.loads((OUT/'scheduler_accounting.json').read_text())
    assert account['live_N']==0 and all(r['JobStatus']==4 for r in account['jobs'])
    assert json.loads((OUT/'independent_validation.json').read_text())['passed']
    sources={};transports=[]
    for path in sorted(OUT.glob('*_submission.json')):
        r=json.loads(path.read_text());phase=r['phase'];package=ROOT/r['package']['path']
        with tarfile.open(package) as archive:
            for member in archive:
                if not member.isfile():continue
                data=archive.extractfile(member).read()
                if member.name.startswith('ntuples/'):
                    assert (ROOT/member.name).read_bytes()==data
                else:sources[phase+'/'+member.name]=data
        sources[phase+'/submission/descriptor.sub']=r['descriptor'].encode()
        sources[phase+'/submission/worker.sh']=(SPOOL/f'worker_{package.parent.name}.sh').read_bytes()
        result=CACHE/f'{phase}_result.tar.gz'
        with tarfile.open(result) as archive:
            for member in archive:
                if member.isfile():assert (ROOT/member.name).read_bytes()==archive.extractfile(member).read(),member.name
        transports.extend([package,result])
    for path in (ROOT/'ml').glob('stage185*'):
        if path.is_file():sources['final/'+str(path.relative_to(ROOT))]=path.read_bytes()
    seen={};unique={};index={}
    for name,data in sources.items():
        if data not in seen:seen[data]=name;unique[name]=data
        index[name]=seen[data]
    unique['source_versions.json']=(json.dumps(index,indent=2)+'\n').encode()
    archive_exact(SOFT/'source_snapshots.tar.gz',unique)
    times=sorted(OUT.glob('*_time.txt'));logs=sorted(OUT.glob('*.log'))
    (OUT/'process_resources.json').write_text(json.dumps([dict(phase=p.stem,**gnu(p)) for p in times],indent=2)+'\n')
    archive_exact(SOFT/'execution_audits.tar.gz',{str(p.relative_to(ROOT)):p.read_bytes() for p in times})
    archive_exact(SOFT/'worker_logs.tar.gz',{str(p.relative_to(ROOT)):p.read_bytes() for p in logs})
    queue=json.loads(subprocess.check_output(['condor_q','-json','-attributes','ClusterId,Iwd'],text=True).strip() or '[]')
    assert all(Path(r.get('Iwd','/'))!=SPOOL for r in queue)
    spool=[p for p in SPOOL.rglob('*') if p.is_file()]
    assert all(p.suffix in ['.sh','.sub','.out','.err','.log'] for p in spool)
    archive_exact(SOFT/'terminal_spool.tar.gz',{str(p.relative_to(SPOOL)):p.read_bytes() for p in spool})
    baseline=json.loads((ROOT/'workbook/stage158_energy_ml/preexisting_asset_snapshot.json').read_text())
    assert all((ROOT/p).stat().st_size==v['bytes'] and (ROOT/p).stat().st_mtime_ns==v['mtime_ns'] for p,v in baseline.items())
    deleted=[]
    for path in transports+times+logs+spool:
        deleted.append(dict(path=str(path),bytes=path.stat().st_size));path.unlink()
    for path in transports:
        if path.parent!=CACHE and path.parent.exists() and not any(path.parent.iterdir()):path.parent.rmdir()
    (SPOOL/'execution_index.json').write_text(json.dumps(dict(stage=185,terminal_jobs=[r['ClusterId'] for r in account['jobs']],archive=str(SOFT/'terminal_spool.tar.gz')),indent=2)+'\n')
    result=dict(passed=True,deleted_bytes=sum(r['bytes'] for r in deleted),deleted=deleted,
        retained_new_event_cache_B=sum(p.stat().st_size for p in CACHE.glob('*') if p.is_file()),
        retained_scope='Verified historical ID/physical PMT and12train scalar integrals; no ROOT/ADC/xAOD payload or new energy models.',
        starts=account['starts'],scheduler_CPU_s=account['total_CPU_s'],scheduler_aggregate_wall_s=account['total_execute_wall_s'],
        live_N=0,failed_job_N=sum(r.get('ExitCode')!=0 for r in account['jobs']),Stage54_preserved=True,queue_Iwd_checked=True,G4_N=0,energy_fits=0,new_forward=0,overall_complete=False)
    (OUT/'storage_cleanup.json').write_text(json.dumps(result,indent=2)+'\n');print({k:v for k,v in result.items() if k!='deleted'})
