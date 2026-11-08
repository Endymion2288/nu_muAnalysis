"""Exact terminal archive and resource accounting; no local event-array analysis."""
import csv
import gzip
import json
import tarfile
from pathlib import Path

from stage158_finalize import archive_exact, gnu

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'workbook/stage163_energy_ml'
CACHE = ROOT / 'ntuples/energy_ml_stage163'
SOFTWARE = ROOT / 'software/stage163'
SPOOL = Path.home() / 'condor/nu_muAnalysis/stage163'


def table(name, rows):
    with (OUT / name).open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(dict.fromkeys(k for r in rows for k in r)),
                                delimiter='\t', lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def main():
    account = json.loads((OUT / 'scheduler_accounting.json').read_text())
    assert account['live_N'] == 0 and not account['unresolved_ids']
    assert account['total_CPU_s'] <= 12000
    assert json.loads((OUT / 'validation_summary.json').read_text())['passed']
    assert json.loads((OUT / 'comparison_summary.json').read_text())['passed']
    assert not (OUT / 'storage_cleanup.json').exists()
    baseline = json.loads((ROOT / 'workbook/stage158_energy_ml/preexisting_asset_snapshot.json').read_text())
    assert all((ROOT / p).stat().st_size == v['bytes'] and (ROOT / p).stat().st_mtime_ns == v['mtime_ns']
               for p, v in baseline.items())

    manifest = OUT / 'source_manifest.json'
    original_manifest = manifest.read_bytes()
    historical_manifest = (OUT/'source_manifest_original.json').read_bytes()
    historical_archive=CACHE/'source_manifest_original.json.gz'
    with gzip.open(historical_archive,'wb') as stream:stream.write(historical_manifest)
    with gzip.open(historical_archive,'rb') as stream:assert stream.read()==historical_manifest
    manifest_archive = CACHE / 'source_manifest.json.gz'
    with gzip.open(manifest_archive, 'wb') as stream:
        stream.write(original_manifest)
    with gzip.open(manifest_archive, 'rb') as stream:
        assert stream.read() == original_manifest
    raw_paths = [CACHE / (p + '.npz') for p in ['pilot', 'repeat'] + [f'batch_{i:02d}' for i in range(8)]]
    raw_payload = {str(p.relative_to(ROOT)): p.read_bytes() for p in raw_paths}
    archive_exact(CACHE / 'raw_inputs.tar.gz', raw_payload)

    source_payload, transport_paths, transport_checks = {}, [], []
    for path in sorted(OUT.glob('*_submission.json')):
        record = json.loads(path.read_text())
        package = ROOT / record['package']['path']
        phase = record['phase']
        with tarfile.open(package, 'r:gz') as archive:
            for member in archive:
                if not member.isfile():
                    continue
                # Retain every used source/config revision and historical accounting,
                # while exact existing event inputs are references, not repeated copies.
                if member.name in ['ntuples/energy_ml_stage119/old_input.npz',
                                   'workbook/stage124_energy_ml/native_contract.json'] or member.name.endswith(('.npz', '.ubj')):
                    current = ROOT / member.name
                    assert current.read_bytes() == archive.extractfile(member).read(), member.name
                elif member.name in ['workbook/stage163_energy_ml/source_manifest.json','workbook/stage163_energy_ml/source_manifest_original.json']:
                    assert archive.extractfile(member).read() in [original_manifest,historical_manifest]
                else:
                    source_payload[phase + '/' + member.name] = archive.extractfile(member).read()
        worker = SPOOL / ('worker_' + package.parent.name + '.sh')
        source_payload[phase + '/submission/worker.sh'] = worker.read_bytes()
        transport_paths.append(package)
        result = CACHE / (phase + '_result.tar.gz')
        cluster = int(record['result'].split('.')[0])
        row = next(r for r in account['jobs'] if r['ClusterId'] == cluster)
        if row.get('NumJobStarts', 0) == 0 and row['JobStatus'] == 3:
            assert not result.exists()
            transport_checks.append(dict(phase=phase,unstarted_removed=True,result_archive_expected=False))
            continue
        assert row.get('ExitCode') in [0,1] and result.exists(), phase
        if row.get('ExitCode')==1:assert phase in ['batch_02','batch_03','source_repair']
        with tarfile.open(result, 'r:gz') as archive:
            for member in archive:
                if member.isfile():
                    data=archive.extractfile(member).read()
                    if member.name=='workbook/stage163_energy_ml/source_manifest.json':
                        assert data in [original_manifest,historical_manifest]
                    elif member.name=='workbook/stage163_energy_ml/source_inventory.tsv':
                        assert data in [(OUT/'source_inventory.tsv').read_bytes(),(OUT/'source_inventory_original.tsv').read_bytes()]
                    else:assert (ROOT / member.name).read_bytes() == data, member.name
        transport_paths.append(result)
        transport_checks.append(dict(phase=phase,result_archive_exact=True))
    archive_exact(SOFTWARE / 'source_snapshots.tar.gz', source_payload)

    summary_paths = sorted(OUT.glob('batch_*_summary.json')) + [OUT / 'pilot_summary.json', OUT / 'repeat_summary.json']
    archive_exact(SOFTWARE / 'extraction_audits.tar.gz',
                  {str(p.relative_to(ROOT)): p.read_bytes() for p in summary_paths})
    extraction, sources = [], []
    for path in summary_paths:
        data = json.loads(path.read_text())
        extraction.append({k: v for k, v in data.items() if k not in ['sources', 'scope']})
        if data['phase'].startswith('batch_'):
            sources.extend(dict(r,phase=data['phase']) for r in data['sources'])
    table('extraction_resources.tsv', extraction)
    # Source TSVs already carry exact original source and missing-schema reasons.
    table('full_source_audit.tsv', sources)
    full = [r for r in extraction if r['phase'].startswith('batch_')]
    native_wall = sum(r['wall_s'] for r in sources)
    driver_wall = sum(r['wall_s'] for r in full)
    resources = dict(scheduler_CPU_s=account['total_CPU_s'],scheduler_aggregate_wall_s=account['total_execute_wall_s'],
        starts=account['starts'],submissions=len(account['jobs']),live_N=0,
        removed_unstarted=[r['ClusterId'] for r in account['jobs'] if r['JobStatus']==3 and r.get('NumJobStarts',0)==0],
        executed_failures=[r['ClusterId'] for r in account['jobs'] if r.get('NumJobStarts',0)>0 and r.get('ExitCode')!=0],
        submitted_request_CPUs=4,submitted_memory_MB=16000,
        scheduler_RequestCpus=sorted({r['RequestCpus'] for r in account['jobs'] if 'RequestCpus' in r}),
        scheduler_RequestMemory_MB=sorted({r['RequestMemory'] for r in account['jobs'] if 'RequestMemory' in r}),
        scheduler_max_reported_ResidentSetSize_KiB=max(r.get('ResidentSetSize',0) for r in account['jobs']),
        scheduler_MemoryUsage_unresolved_expression=any(isinstance(r.get('MemoryUsage'),str) for r in account['jobs']),
        full_parent_N=sum(r['N'] for r in full),identity_exact_N=sum(r['identity_exact_N'] for r in full),
        full_extraction_CPU_s=sum(r['CPU_s'] for r in full),full_extraction_aggregate_wall_s=driver_wall,
        measured_source_wall_overlap=native_wall/driver_wall,
        ROOT_read_bytes=sum(r['ROOT_read_bytes'] for r in full),max_extraction_RSS_KiB=max(r['RSS_KiB'] for r in full),
        GPU_jobs=0,new_G4=0,new_independent_nu=0,
        interpretation='Measured source-thread wall overlap is not a matched serial speedup; nested GNU/process CPU is not added to scheduler total.')
    (OUT / 'resource_audit.json').write_text(json.dumps(resources,indent=2)+'\n')
    times=sorted(OUT.glob('*_time.txt'))
    table('process_resources.tsv',[dict(task=p.name.removesuffix('_time.txt'),**gnu(p)) for p in times])
    archive_exact(SOFTWARE/'execution_audits.tar.gz',{str(p.relative_to(ROOT)):p.read_bytes() for p in times})
    logs=sorted(OUT.glob('*.log'))
    logs.extend(SPOOL/'logs'/f"{r['ClusterId']}.{r['ProcId']}.{s}" for r in account['jobs'] for s in ['out','err','log'] if (SPOOL/'logs'/f"{r['ClusterId']}.{r['ProcId']}.{s}").exists())
    archive_exact(SOFTWARE/'worker_logs.tar.gz',{
        str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else 'scheduler/'+p.name:p.read_bytes() for p in logs})
    final_paths=[manifest_archive,historical_archive,CACHE/'raw_inputs.tar.gz',CACHE/'features.npz']
    final_paths += [p for p in (ROOT/'ml/artifacts/stage163').rglob('*') if p.is_file()]
    total_bytes=sum(p.stat().st_size for p in final_paths)
    assert total_bytes<=67108864,total_bytes
    # Keep the original frozen event manifest once, with an explicit compact pointer in Git.
    manifest.write_text(json.dumps(dict(archived_exact_original=True,path=str(manifest_archive.relative_to(ROOT)),
        original_bytes=len(original_manifest),gzip_bytes=manifest_archive.stat().st_size,
        source_inventory='source_inventory.tsv',active_N=71376),indent=2)+'\n')
    (OUT/'source_manifest_original.json').write_text(json.dumps(dict(archived_exact_original=True,
        path=str(historical_archive.relative_to(ROOT)),original_bytes=len(historical_manifest),
        superseded_only_for_documented_Stage82_source_mapping=True),indent=2)+'\n')
    redundant_tsv=[OUT/(p.stem.removesuffix('_summary')+'_sources.tsv') for p in summary_paths]
    assert all(p.exists() for p in redundant_tsv)
    # These tables are exact representations worth preserving alongside the full audits.
    archive_exact(SOFTWARE/'source_tables.tar.gz',{str(p.relative_to(ROOT)):p.read_bytes() for p in redundant_tsv})
    deleted=[]
    for path in raw_paths+transport_paths+summary_paths+times+redundant_tsv+[p for p in logs if p.is_relative_to(OUT)]:
        if path.exists():
            deleted.append(dict(path=str(path.relative_to(ROOT)),bytes=path.stat().st_size));path.unlink()
    for path in transport_paths:
        if path.parent!=CACHE and path.parent.exists() and not any(path.parent.iterdir()):path.parent.rmdir()
    result=dict(all_jobs_terminal=True,source_and_logs_byte_equality=True,event_inputs_byte_equality=True,
        transport_checks=transport_checks,final_event_features_and_models_bytes=total_bytes,limit_bytes=67108864,
        archives=[dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size) for p in SOFTWARE.glob('*.tar.gz')],
        event_archives=[dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size) for p in [manifest_archive,historical_archive,CACHE/'raw_inputs.tar.gz']],
        deleted=deleted,deleted_bytes=sum(r['bytes'] for r in deleted),
        no_persistent_ROOT=True,Stage54_size_mtime_preserved=True)
    (OUT/'storage_cleanup.json').write_text(json.dumps(result,indent=2)+'\n')
    print(resources)
    print({k:v for k,v in result.items() if k not in ['deleted','transport_checks']})


if __name__=='__main__':main()
