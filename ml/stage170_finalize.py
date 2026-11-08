"""Exact-byte terminal-only storage closure for bounded RAW control stages."""
import argparse
import json
import subprocess
import tarfile
from pathlib import Path
from stage158_finalize import archive_exact,gnu
ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--stage',type=int,default=170);args=parser.parse_args();stage=args.stage
    out=ROOT/f'workbook/stage{stage}_energy_ml';cache=ROOT/f'ntuples/energy_ml_stage{stage}';software=ROOT/f'software/stage{stage}'
    spool=Path.home()/f'condor/nu_muAnalysis/stage{stage}'
    assert not (out/'storage_cleanup.json').exists()
    account=json.loads((out/'scheduler_accounting.json').read_text());assert account['live_N']==0
    assert all(r['JobStatus'] in [3,4] for r in account['jobs'])
    sources={};transport=[]
    for path in sorted(out.glob('*_submission.json')):
        rec=json.loads(path.read_text());phase=rec['phase'];package=ROOT/rec['package']['path']
        with tarfile.open(package) as t:
            for m in t:
                if not m.isfile():continue
                data=t.extractfile(m).read()
                if m.name.startswith('ntuples/'):
                    assert (ROOT/m.name).read_bytes()==data,m.name
                else:sources[phase+'/'+m.name]=data
        sources[phase+'/submission/descriptor.sub']=rec['descriptor'].encode()
        sources[phase+'/submission/worker.sh']=(spool/('worker_'+package.parent.name+'.sh')).read_bytes()
        result=cache/(phase+'_result.tar.gz')
        with tarfile.open(result) as t:
            for m in t:
                if m.isfile():assert (ROOT/m.name).read_bytes()==t.extractfile(m).read(),m.name
        transport.extend([package,result])
    for p in (ROOT/'ml').glob(f'stage{stage}*.py'):sources['final/'+str(p.relative_to(ROOT))]=p.read_bytes()
    canonical={};seen={};index={}
    for name,data in sources.items():
        if data not in seen:seen[data]=name;canonical[name]=data
        index[name]=seen[data]
    canonical['source_versions.json']=(json.dumps(index,indent=2)+'\n').encode()
    archive_exact(software/'source_snapshots.tar.gz',canonical)
    with tarfile.open(software/'source_snapshots.tar.gz') as t:
        assert all(t.extractfile(index[name]).read()==data for name,data in sources.items())
    times=list(out.glob('*_time.txt'));logs=list(out.glob('*.log'))
    process=[dict(task=p.stem,**gnu(p)) for p in times]
    (out/'process_resources.json').write_text(json.dumps(process,indent=2)+'\n')
    archive_exact(software/'execution_audits.tar.gz',{str(p.relative_to(ROOT)):p.read_bytes() for p in times})
    active=json.loads(subprocess.check_output(['condor_q','-json','-attributes','ClusterId,Iwd'],text=True).strip() or '[]')
    assert all(Path(r.get('Iwd','/'))!=spool for r in active)
    spoolfiles=[p for p in spool.rglob('*') if p.is_file()]
    assert all(p.suffix in ['.sh','.sub','.out','.err','.log'] for p in spoolfiles)
    archive_exact(software/'terminal_spool.tar.gz',{str(p.relative_to(spool)):p.read_bytes() for p in spoolfiles})
    archive_exact(software/'worker_logs.tar.gz',{str(p.relative_to(ROOT)):p.read_bytes() for p in logs})
    baseline=json.loads((ROOT/'workbook/stage158_energy_ml/preexisting_asset_snapshot.json').read_text())
    assert all((ROOT/p).stat().st_size==v['bytes'] and (ROOT/p).stat().st_mtime_ns==v['mtime_ns'] for p,v in baseline.items())
    final=list(cache.glob('*_rows.jsonl.gz'));data_bytes=sum(p.stat().st_size for p in final);assert data_bytes<=4194304
    deleted=[]
    for p in transport+times+logs+spoolfiles:
        if p.exists():deleted.append(dict(path=str(p),bytes=p.stat().st_size));p.unlink()
    for p in transport:
        if p.parent!=cache and p.parent.exists() and not any(p.parent.iterdir()):p.parent.rmdir()
    (spool/'execution_index.json').write_text(json.dumps(dict(stage=stage,terminal_jobs=[r['ClusterId'] for r in account['jobs']],archive=str(software/'terminal_spool.tar.gz')),indent=2)+'\n')
    report=dict(all_jobs_terminal=True,source_logical_versions=len(sources),source_unique_versions=len(seen),
        exact_bytes_verified=True,live_queue_Iwd_checked=True,Stage54_size_mtime_preserved=True,
        final_event_bytes=data_bytes,final_event_files=[dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size) for p in final],
        deleted_bytes=sum(r['bytes'] for r in deleted),deleted=deleted,
        scheduler_CPU_s=account['total_CPU_s'],scheduler_aggregate_wall_s=account['total_execute_wall_s'],
        starts=account['starts'],live_N=0,energy_fits=0,new_G4=0,model_forward=0,GPU_jobs=0,
        scheduler_RequestMemory_MB=sorted({r['RequestMemory'] for r in account['jobs'] if 'RequestMemory' in r}),
        archives=[dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size) for p in software.glob('*.tar.gz')])
    (out/'storage_cleanup.json').write_text(json.dumps(report,indent=2)+'\n');print({k:v for k,v in report.items() if k not in ['deleted','archives']})


if __name__=='__main__':main()
