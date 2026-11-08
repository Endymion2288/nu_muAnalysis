"""Lossless compact completed scientific outputs; local text/archive work only."""
import gzip
import io
import json
import tarfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage157_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage157'


def main():
    account=json.loads((OUT/'scheduler_accounting.json').read_text())
    summary=json.loads((OUT/'summary.json').read_text())
    assert account['live_N']==0 and not account['unresolved_ids'] and summary['passed']
    if summary['phase']=='full':assert summary['independent_parent_N']==4096 and summary['prefix128_current_and_RNG_exact']
    paths=list(CACHE.glob('chains/*/native.json.gz'))+list(CACHE.glob('chains/*/paired.json.gz'))+list(OUT.glob('chains/*/seeds.json'))
    payload={}
    for path in paths:
        if path.suffix=='.gz':
            with gzip.open(path,'rt') as stream:text=stream.read()
        else:text=path.read_text()
        payload[str(path.relative_to(ROOT))]=text
    target=CACHE/'event_records.json.gz'
    with gzip.open(target,'wt') as stream:json.dump(payload,stream,separators=(',',':'))
    with gzip.open(target,'rt') as stream:assert json.load(stream)==payload
    assert target.stat().st_size<=33554432,target.stat().st_size
    capsule=ROOT/'software/stage157/source_snapshots.tar.gz';capsule.parent.mkdir(parents=True,exist_ok=True)
    transports=[];sources={}
    with tarfile.open(capsule,'w:gz') as archive:
        for path in sorted(OUT.glob('*_submission.json')):
            record=json.loads(path.read_text());package=ROOT/record['package']['path']
            with tarfile.open(package,'r:gz') as source:
                for member in source:
                    if not member.isfile() or not member.name.endswith(('.py','.hxx','.sh','protocol.json')):continue
                    data=source.extractfile(member).read();name=record['phase']+'/'+member.name
                    info=tarfile.TarInfo(name);info.size=len(data);archive.addfile(info,io.BytesIO(data));sources[name]=data
            worker=Path.home()/'condor/nu_muAnalysis/stage157'/('worker_'+package.parent.name+'.sh')
            data=worker.read_bytes();name=record['phase']+'/submission/worker.sh'
            info=tarfile.TarInfo(name);info.size=len(data);archive.addfile(info,io.BytesIO(data));sources[name]=data
            transports.extend([package,CACHE/(record['phase']+'_result.tar.gz')])
    with tarfile.open(capsule,'r:gz') as archive:
        assert all(archive.extractfile(name).read()==data for name,data in sources.items())
    meta=list(OUT.glob('chains/*/input_metadata.json'))
    if meta:
        text=meta[0].read_text();assert all(p.read_text()==text for p in meta)
        (OUT/'input_metadata.json').write_text(text)
    chain_files=[p for p in OUT.glob('chains/*/*') if p.is_file() and p not in paths and p.suffix!='.log']
    audit_capsule=capsule.with_name('chain_audits.tar.gz')
    with tarfile.open(audit_capsule,'w:gz') as archive:
        for path in chain_files:archive.add(path,arcname=str(path.relative_to(ROOT)))
    with tarfile.open(audit_capsule,'r:gz') as archive:
        assert all(archive.extractfile(str(path.relative_to(ROOT))).read()==path.read_bytes() for path in chain_files)
    logs=list(OUT.glob('chains/*/*.log'))
    logs.extend(Path.home()/'condor/nu_muAnalysis/stage157/logs'/f"{r['ClusterId']}.{r['ProcId']}.{s}" for r in account['jobs'] for s in ['out','err','log'])
    log_capsule=capsule.with_name('worker_logs.tar.gz')
    def log_name(path):return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else 'scheduler/'+path.name
    with tarfile.open(log_capsule,'w:gz') as archive:
        for path in logs:archive.add(path,arcname=log_name(path))
    with tarfile.open(log_capsule,'r:gz') as archive:
        assert all(archive.extractfile(log_name(path)).read()==path.read_bytes() for path in logs)
    deleted=[]
    candidates=paths+transports+chain_files+[p for p in logs if p.is_relative_to(OUT)]+[CACHE/'pilot_reference.json.gz']
    for path in candidates:
        if path.exists():
            deleted.append(dict(path=str(path.relative_to(ROOT)),bytes=path.stat().st_size));path.unlink()
    for path in transports:
        if path.parent!=CACHE and path.parent.exists() and not any(path.parent.iterdir()):path.parent.rmdir()
    report=dict(all_jobs_terminal=True,event_text_equality=True,
        failed_job_ids=[f"{r['ClusterId']}.{r['ProcId']}" for r in account['jobs'] if r.get('ExitCode')!=0],
        merged=dict(path=str(target.relative_to(ROOT)),bytes=target.stat().st_size),
        source_capsule=dict(path=str(capsule.relative_to(ROOT)),bytes=capsule.stat().st_size),
        chain_audits=dict(N=len(chain_files),path=str(audit_capsule.relative_to(ROOT)),bytes=audit_capsule.stat().st_size,byte_equality=True),
        logs=dict(N=len(logs),path=str(log_capsule.relative_to(ROOT)),bytes=log_capsule.stat().st_size,byte_equality=True),
        identical_metadata_copies_merged=len(meta),deleted=deleted,deleted_bytes=sum(r['bytes'] for r in deleted),
        no_persistent_ROOT=True,original_HITS_PHYS_other_stages_Stage54_untouched=True)
    (OUT/'storage_cleanup.json').write_text(json.dumps(report,indent=2)+'\n')
    print({k:v for k,v in report.items() if k!='deleted'},flush=True)


if __name__=='__main__':main()
