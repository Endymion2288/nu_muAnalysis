"""Terminal-only exact-byte compaction for the bounded electronic experiments."""
import json
import subprocess
import sys
import tarfile
from pathlib import Path

from stage158_finalize import archive_exact, gnu


def main(stage):
    assert stage in [188,189,190,191,192,193,194]
    root=Path(__file__).resolve().parents[1]
    out=root/f'workbook/stage{stage}_energy_ml'
    cache=root/f'ntuples/energy_ml_stage{stage}'
    soft=root/f'software/stage{stage}'
    spool=Path.home()/f'condor/nu_muAnalysis/stage{stage}'
    assert not (out/'storage_cleanup.json').exists()
    a=json.loads((out/'scheduler_accounting.json').read_text())
    assert not a['live_N'] and all(j['JobStatus'] in [3,4] for j in a['jobs'])
    assert a['total_CPU_s']<=({188:4800,189:2400,190:1200,191:60000,192:1200,193:300,194:1200}[stage])
    assert json.loads((out/'independent_validation.json').read_text())['passed']
    queue=json.loads(subprocess.check_output(['condor_q','-json','-attributes','ClusterId,Iwd'],text=True).strip() or '[]')
    assert all(Path(j.get('Iwd','/'))!=spool for j in queue)
    sources,logs,scalar_history,transports={},{},{},[]
    for f in sorted(out.glob('*_submission.json')):
        s=json.loads(f.read_text());phase=s['phase'];package=root/s['package']['path']
        with tarfile.open(package) as archive:
            for member in archive:
                if member.isfile() and (member.name.startswith('ml/') and not member.name.startswith('ml/artifacts/') or member.name.endswith(('protocol.json','build_spec.json'))):
                    sources[phase+'/'+member.name]=archive.extractfile(member).read()
        sources[phase+'/descriptor.sub']=s['descriptor'].encode()
        sources[phase+'/worker.sh']=(spool/f'worker_{package.parent.name}.sh').read_bytes()
        result=cache/f'{phase}_result.tar.gz'
        with tarfile.open(result) as archive:
            for member in archive:
                if not member.isfile():continue
                if member.name.endswith(('.log','_time.txt')):
                    logs[phase+'/'+member.name]=archive.extractfile(member).read()
                elif member.name.endswith(('.json','.tsv','.txt')):
                    scalar_history[phase+'/'+member.name]=archive.extractfile(member).read()
        transports.extend([package,result])
    for f in (root/'ml').glob(f'stage{stage}*'):
        if f.is_file():sources['final/'+f.name]=f.read_bytes()
    sources['final/worker.sh']=(root/f'AnalysisZipFramework/submission/run_ml_stage{stage}.sh').read_bytes()
    process=[dict(task=f.stem,**gnu(f)) for f in sorted(out.glob('*_time.txt'))]
    (out/'process_resources.json').write_text(json.dumps(process,indent=2)+'\n')
    soft.mkdir(exist_ok=True)
    archive_exact(soft/'source_snapshots.tar.gz',sources)
    archive_exact(soft/'execution_logs.tar.gz',logs)
    archive_exact(soft/'scalar_history.tar.gz',scalar_history)
    files=[f for f in spool.rglob('*') if f.is_file()]
    assert all(f.suffix in ['.sh','.sub','.out','.err','.log'] for f in files)
    archive_exact(soft/'terminal_spool.tar.gz',{str(f.relative_to(spool)):f.read_bytes() for f in files})
    before=json.loads((root/'workbook/stage158_energy_ml/preexisting_asset_snapshot.json').read_text())
    assert all((root/k).stat().st_size==v['bytes'] and (root/k).stat().st_mtime_ns==v['mtime_ns'] for k,v in before.items())
    retained=[f for f in cache.rglob('*') if f.is_file() and not f.name.endswith('_result.tar.gz')]
    artifacts=root/f'ml/artifacts/stage{stage}'
    if artifacts.exists():retained += [f for f in artifacts.rglob('*') if f.is_file()]
    size=sum(f.stat().st_size for f in retained)
    assert size<={188:16777216,189:33554432,190:16777216,191:100663296,192:16777216,193:1048576,194:16777216}[stage]
    deleted=[]
    for f in dict.fromkeys(transports+files+list(out.glob('*.log'))+list(out.glob('*_time.txt'))):
        deleted.append(dict(path=str(f),bytes=f.stat().st_size));f.unlink()
    for f in transports:
        if f.parent!=cache and f.parent.exists() and not any(f.parent.iterdir()):f.parent.rmdir()
    for f in sorted(spool.rglob('*'),key=lambda p:len(p.parts),reverse=True):
        if f.is_dir() and not any(f.iterdir()):f.rmdir()
    (spool/'execution_index.json').write_text(json.dumps(dict(stage=stage,jobs=[j['ClusterId'] for j in a['jobs']],archive=str(soft/'terminal_spool.tar.gz')),indent=2)+'\n')
    result=dict(passed=True,all_jobs_terminal=True,live_N=0,starts=a['starts'],scheduler_CPU_s=a['total_CPU_s'],
        scheduler_aggregate_wall_s=a['total_execute_wall_s'],
        failed_jobs=[f"{j['ClusterId']}.{j['ProcId']}" for j in a['jobs'] if j.get('ExitCode')!=0],
        exact_source_logs_scalar_spool_archives=True,Stage54_preserved_N=len(before),
        retained_cache_models_B=size,deleted_B=sum(r['bytes'] for r in deleted),deleted=deleted,
        no_ROOT_or_xAOD_persistence=True,overall_complete=False,promotion=False)
    (out/'storage_cleanup.json').write_text(json.dumps(result,indent=2)+'\n')
    print({k:v for k,v in result.items() if k!='deleted'})


if __name__=='__main__':main(int(sys.argv[1]))
