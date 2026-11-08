"""Terminal exact-byte archive and prefix deduplication, no scientific calculation."""
import json,subprocess,tarfile
from pathlib import Path
from stage158_finalize import archive_exact,gnu
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage175_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage175';SOFT=ROOT/'software/stage175';SPOOL=Path.home()/'condor/nu_muAnalysis/stage175'
if __name__=='__main__':
    assert not (OUT/'storage_cleanup.json').exists()
    account=json.loads((OUT/'scheduler_accounting.json').read_text());assert account['live_N']==0
    assert all(r['JobStatus']==4 and r['ExitCode']==0 for r in account['jobs'])
    audit=json.loads((OUT/'independent_validation.json').read_text());assert audit['passed'] and len(audit['actual_source_checks'])==3
    full=json.loads((OUT/'full_summary.json').read_text());assert full['pilot_selected_rows_exact'] and full['all_identity_and_roles_exact']
    source={};transport=[]
    for path in OUT.glob('*_submission.json'):
        r=json.loads(path.read_text());phase=r['phase'];package=ROOT/r['package']['path']
        with tarfile.open(package) as t:
            for m in t:
                if not m.isfile():continue
                data=t.extractfile(m).read()
                if m.name.startswith('ntuples/'):assert (ROOT/m.name).read_bytes()==data
                else:source[phase+'/'+m.name]=data
        source[phase+'/submission/descriptor.sub']=r['descriptor'].encode()
        source[phase+'/submission/worker.sh']=(SPOOL/('worker_'+package.parent.name+'.sh')).read_bytes()
        result=CACHE/(phase+'_result.tar.gz')
        with tarfile.open(result) as t:
            for m in t:
                if m.isfile():assert (ROOT/m.name).read_bytes()==t.extractfile(m).read(),m.name
        transport.extend([package,result])
    for p in (ROOT/'ml').glob('stage175*.py'):source['final/'+str(p.relative_to(ROOT))]=p.read_bytes()
    unique={};seen={};idx={}
    for name,data in source.items():
        if data not in seen:seen[data]=name;unique[name]=data
        idx[name]=seen[data]
    unique['source_versions.json']=(json.dumps(idx,indent=2)+'\n').encode();archive_exact(SOFT/'source_snapshots.tar.gz',unique)
    with tarfile.open(SOFT/'source_snapshots.tar.gz') as t:assert all(t.extractfile(idx[n]).read()==v for n,v in source.items())
    times=list(OUT.glob('*_time.txt'));logs=list(OUT.glob('*.log'))
    resources=[dict(phase=p.stem,**gnu(p)) for p in times];(OUT/'process_resources.json').write_text(json.dumps(resources,indent=2)+'\n')
    archive_exact(SOFT/'execution_audits.tar.gz',{str(p.relative_to(ROOT)):p.read_bytes() for p in times})
    archive_exact(SOFT/'worker_logs.tar.gz',{str(p.relative_to(ROOT)):p.read_bytes() for p in logs})
    active=json.loads(subprocess.check_output(['condor_q','-json','-attributes','ClusterId,Iwd'],text=True).strip() or '[]')
    assert all(Path(r.get('Iwd','/'))!=SPOOL for r in active)
    spool=[p for p in SPOOL.rglob('*') if p.is_file()];assert all(p.suffix in ['.sh','.sub','.out','.err','.log'] for p in spool)
    archive_exact(SOFT/'terminal_spool.tar.gz',{str(p.relative_to(SPOOL)):p.read_bytes() for p in spool})
    baseline=json.loads((ROOT/'workbook/stage158_energy_ml/preexisting_asset_snapshot.json').read_text())
    assert all((ROOT/p).stat().st_size==v['bytes'] and (ROOT/p).stat().st_mtime_ns==v['mtime_ns'] for p,v in baseline.items())
    indices=json.loads((OUT/'protocol.json').read_text())['pilot_indices']
    prefixes=[CACHE/f'{phase}_{i}.npz' for phase in ['pilot','profile','audit'] for i in indices]
    summaries=list(OUT.glob('full_*_summary.json'))
    source_rows={r['index']:r for r in full['sources']}
    assert all(json.loads(p.read_text())==source_rows[int(p.name.split('_')[1])] for p in summaries)
    deleted=[]
    for p in transport+times+logs+spool+prefixes+summaries:
        if p.exists():deleted.append(dict(path=str(p),bytes=p.stat().st_size));p.unlink()
    for p in transport:
        if p.parent!=CACHE and p.parent.exists() and not any(p.parent.iterdir()):p.parent.rmdir()
    (SPOOL/'execution_index.json').write_text(json.dumps(dict(stage=175,terminal_jobs=[r['ClusterId'] for r in account['jobs']],archive=str(SOFT/'terminal_spool.tar.gz')),indent=2)+'\n')
    result=dict(passed=True,all_terminal=True,exact_source_metadata_bytes=True,source_logical_N=len(source),source_unique_N=len(seen),
        deleted_bytes=sum(r['bytes'] for r in deleted),deleted=deleted,Stage54_preserved=True,queue_Iwd_checked=True,
        retained_cohort_array_bytes=(CACHE/'cohort.npz').stat().st_size,source_summary_duplicates_removed_N=len(summaries),
        prefix_dedup_scientifically_verified=True,scheduler_CPU_s=account['total_CPU_s'],scheduler_aggregate_wall_s=account['total_execute_wall_s'],starts=account['starts'],live_N=0,
        scheduler_RequestCpus=sorted({r['RequestCpus'] for r in account['jobs']}),scheduler_RequestMemory_MB=sorted({r['RequestMemory'] for r in account['jobs']}),
        archives=[dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size) for p in SOFT.glob('*.tar.gz')],
        energy_fits=0,model_forward=0,new_G4=0,GPU_jobs=0,overall_complete=False)
    (OUT/'storage_cleanup.json').write_text(json.dumps(result,indent=2)+'\n');print({k:v for k,v in result.items() if k not in ['deleted','archives']})
