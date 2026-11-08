"""Preserve exact source/results, retire terminal transports, retain science inputs."""
import json
import subprocess
import tarfile
from pathlib import Path
from stage158_finalize import archive_exact,gnu
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage178_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage178';SOFT=ROOT/'software/stage178';SPOOL=Path.home()/'condor/nu_muAnalysis/stage178'
if __name__=='__main__':
    assert not (OUT/'storage_cleanup.json').exists()
    account=json.loads((OUT/'scheduler_accounting.json').read_text())
    assert account['live_N']==0 and all(r['JobStatus']==4 and r['ExitCode']==0 for r in account['jobs'])
    assert json.loads((OUT/'independent_validation.json').read_text())['passed']
    source={};transport=[]
    for path in OUT.glob('*_submission.json'):
        r=json.loads(path.read_text());phase=r['phase'];package=ROOT/r['package']['path']
        with tarfile.open(package) as archive:
            for member in archive:
                if not member.isfile():continue
                data=archive.extractfile(member).read()
                if member.name.startswith('ntuples/') or member.name.endswith('observer-runtime.tar.gz'):
                    assert (ROOT/member.name).read_bytes()==data
                else:source[phase+'/'+member.name]=data
        source[phase+'/submission/descriptor.sub']=r['descriptor'].encode()
        source[phase+'/submission/worker.sh']=(SPOOL/f'worker_{package.parent.name}.sh').read_bytes()
        result=CACHE/f'{phase}_result.tar.gz'
        with tarfile.open(result) as archive:
            for member in archive:
                if member.isfile():assert (ROOT/member.name).read_bytes()==archive.extractfile(member).read(),member.name
        transport.extend([package,result])
    for path in (ROOT/'ml').glob('stage178*.py'):source['final/'+str(path.relative_to(ROOT))]=path.read_bytes()
    seen={};unique={};index={}
    for name,data in source.items():
        if data not in seen:seen[data]=name;unique[name]=data
        index[name]=seen[data]
    unique['source_versions.json']=(json.dumps(index,indent=2)+'\n').encode()
    archive_exact(SOFT/'source_snapshots.tar.gz',unique)
    times=list(OUT.glob('*_time.txt'));logs=list(OUT.glob('*.log'))
    (OUT/'process_resources.json').write_text(json.dumps([dict(phase=p.stem,**gnu(p)) for p in times],indent=2)+'\n')
    archive_exact(SOFT/'execution_audits.tar.gz',{str(p.relative_to(ROOT)):p.read_bytes() for p in times})
    archive_exact(SOFT/'worker_logs.tar.gz',{str(p.relative_to(ROOT)):p.read_bytes() for p in logs})
    active=json.loads(subprocess.check_output(['condor_q','-json','-attributes','ClusterId,Iwd'],text=True).strip() or '[]')
    assert all(Path(r.get('Iwd','/'))!=SPOOL for r in active)
    spool=[p for p in SPOOL.rglob('*') if p.is_file()]
    assert all(p.suffix in ['.sh','.sub','.out','.err','.log'] for p in spool)
    archive_exact(SOFT/'terminal_spool.tar.gz',{str(p.relative_to(SPOOL)):p.read_bytes() for p in spool})
    baseline=json.loads((ROOT/'workbook/stage158_energy_ml/preexisting_asset_snapshot.json').read_text())
    assert all((ROOT/p).stat().st_size==v['bytes'] and (ROOT/p).stat().st_mtime_ns==v['mtime_ns'] for p,v in baseline.items())
    deleted=[]
    for path in transport+times+logs+spool:
        deleted.append(dict(path=str(path),bytes=path.stat().st_size));path.unlink()
    for path in transport:
        if path.parent!=CACHE and path.parent.exists() and not any(path.parent.iterdir()):path.parent.rmdir()
    (SPOOL/'execution_index.json').write_text(json.dumps(dict(stage=178,terminal_jobs=[r['ClusterId'] for r in account['jobs']],archive=str(SOFT/'terminal_spool.tar.gz')),indent=2)+'\n')
    result=dict(passed=True,deleted_bytes=sum(r['bytes'] for r in deleted),deleted=deleted,
        retained_event_B=sum(p.stat().st_size for p in CACHE.glob('*') if p.is_file())+sum(p.stat().st_size for p in OUT.glob('parent_*_intervals.json')),
        retained_scope='Necessary compact per-parent lineage/HITS and interval labels, reused directly by the next matched-window study; no ROOT retained.',
        source_logical_N=len(source),source_unique_N=len(seen),starts=account['starts'],scheduler_CPU_s=account['total_CPU_s'],
        scheduler_aggregate_wall_s=account['total_execute_wall_s'],live_N=0,Stage54_preserved=True,queue_Iwd_checked=True,
        scheduler_RequestCpus=sorted({r['RequestCpus'] for r in account['jobs']}),scheduler_RequestMemory_MB=sorted({r['RequestMemory'] for r in account['jobs']}),
        G4_replays=11,reconstruction_N=0,energy_fits=0,new_independent_nu=0,overall_complete=False)
    (OUT/'storage_cleanup.json').write_text(json.dumps(result,indent=2)+'\n')
    print({k:v for k,v in result.items() if k!='deleted'})
