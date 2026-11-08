"""Close a bounded pilot including its failed attempt and unused submission transport."""
import json,subprocess,tarfile
from pathlib import Path
from stage158_finalize import archive_exact,gnu
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage176_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage176';SOFT=ROOT/'software/stage176';SPOOL=Path.home()/'condor/nu_muAnalysis/stage176'
if __name__=='__main__':
    assert not (OUT/'storage_cleanup.json').exists()
    account=json.loads((OUT/'scheduler_accounting.json').read_text());assert account['live_N']==0
    assert all(r['JobStatus']==4 for r in account['jobs'])
    assert sorted(r['ExitCode'] for r in account['jobs'])==[0,0,1]
    assert json.loads((OUT/'independent_validation.json').read_text())['passed']
    assert not json.loads((OUT/'admission.json').read_text())['admitted']
    # Original failed bytes were overwritten in later scratch phases; retain the exact returned transport.
    failed=CACHE/'preflight_result.tar.gz';saved=SOFT/'failed_worker_result.tar.gz';saved.write_bytes(failed.read_bytes());assert saved.read_bytes()==failed.read_bytes()
    source={};transport=[]
    for path in OUT.glob('*_submission.json'):
        r=json.loads(path.read_text());phase=r['phase'];package=ROOT/r['package']['path']
        with tarfile.open(package) as t:
            for m in t:
                if not m.isfile():continue
                data=t.extractfile(m).read()
                if m.name.startswith('ntuples/') or m.name.endswith('observer-runtime.tar.gz'):assert (ROOT/m.name).read_bytes()==data
                else:source[phase+'/'+m.name]=data
        source[phase+'/submission/descriptor.sub']=r['descriptor'].encode()
        source[phase+'/submission/worker.sh']=(SPOOL/('worker_'+package.parent.name+'.sh')).read_bytes()
        result=CACHE/(phase+'_result.tar.gz')
        if phase!='preflight':
            with tarfile.open(result) as t:
                for m in t:
                    if m.isfile():assert (ROOT/m.name).read_bytes()==t.extractfile(m).read(),m.name
        transport.extend([package,result])
    for p in (ROOT/'ml').glob('stage176*.py'):source['final/'+str(p.relative_to(ROOT))]=p.read_bytes()
    for p in (ROOT/'ml/stage176_observer').rglob('*'):
        if p.is_file():source['final/'+str(p.relative_to(ROOT))]=p.read_bytes()
    source['final/ml/stage176_state.hxx']=(ROOT/'ml/stage176_state.hxx').read_bytes()
    unique={};seen={};idx={}
    for name,data in source.items():
        if data not in seen:seen[data]=name;unique[name]=data
        idx[name]=seen[data]
    unique['source_versions.json']=(json.dumps(idx,indent=2)+'\n').encode();archive_exact(SOFT/'source_snapshots.tar.gz',unique)
    times=list(OUT.glob('*_time.txt'));logs=list(OUT.glob('*.log'))
    (OUT/'process_resources.json').write_text(json.dumps([dict(phase=p.stem,**gnu(p)) for p in times],indent=2)+'\n')
    archive_exact(SOFT/'execution_audits.tar.gz',{str(p.relative_to(ROOT)):p.read_bytes() for p in times})
    archive_exact(SOFT/'worker_logs.tar.gz',{str(p.relative_to(ROOT)):p.read_bytes() for p in logs})
    active=json.loads(subprocess.check_output(['condor_q','-json','-attributes','ClusterId,Iwd'],text=True).strip() or '[]');assert all(Path(r.get('Iwd','/'))!=SPOOL for r in active)
    spool=[p for p in SPOOL.rglob('*') if p.is_file()];assert all(p.suffix in ['.sh','.sub','.out','.err','.log'] for p in spool)
    archive_exact(SOFT/'terminal_spool.tar.gz',{str(p.relative_to(SPOOL)):p.read_bytes() for p in spool})
    extra=[p for p in SOFT.glob('*/energy-ml-stage176.tar.gz') if p not in transport]
    extras=[dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,executed=False,reason='Unsubmitted audit packaging stopped on incorrect cache directory; corrected before condor_submit.') for p in extra]
    baseline=json.loads((ROOT/'workbook/stage158_energy_ml/preexisting_asset_snapshot.json').read_text());assert all((ROOT/p).stat().st_size==v['bytes'] and (ROOT/p).stat().st_mtime_ns==v['mtime_ns'] for p,v in baseline.items())
    deleted=[]
    for p in transport+times+logs+spool+extra:
        if p.exists():deleted.append(dict(path=str(p),bytes=p.stat().st_size));p.unlink()
    for p in transport+extra:
        if p.parent!=CACHE and p.parent.exists() and not any(p.parent.iterdir()):p.parent.rmdir()
    (SPOOL/'execution_index.json').write_text(json.dumps(dict(stage=176,terminal_jobs=[r['ClusterId'] for r in account['jobs']],archive=str(SOFT/'terminal_spool.tar.gz')),indent=2)+'\n')
    result=dict(passed=True,all_terminal=True,failed_attempts=1,successful_attempts=2,failed_original_bytes_retained=True,unsubmitted_packaging_errors=extras,
        source_logical_N=len(source),source_unique_N=len(seen),deleted_bytes=sum(r['bytes'] for r in deleted),deleted=deleted,
        retained_event_and_summary_bytes=sum(p.stat().st_size for p in CACHE.glob('*') if p.is_file())+sum(p.stat().st_size for p in OUT.glob('parent_50*json')),
        observer_runtime_bytes=(SOFT/'observer-runtime.tar.gz').stat().st_size,scheduler_CPU_s=account['total_CPU_s'],scheduler_aggregate_wall_s=account['total_execute_wall_s'],starts=account['starts'],live_N=0,
        scheduler_RequestCpus=sorted({r['RequestCpus'] for r in account['jobs']}),scheduler_RequestMemory_MB=sorted({r['RequestMemory'] for r in account['jobs']}),
        Stage54_preserved=True,queue_Iwd_checked=True,full_remaining11_admitted=False,new_independent_nu=0,energy_fits=0,GPU_jobs=0,overall_complete=False)
    (OUT/'storage_cleanup.json').write_text(json.dumps(result,indent=2)+'\n');print({k:v for k,v in result.items() if k!='deleted'})
