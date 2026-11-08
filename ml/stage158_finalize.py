"""Compact terminal Stage158 records with exact byte readback; no array analysis."""
import csv
import gzip
import io
import json
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'workbook/stage158_energy_ml'
CACHE = ROOT / 'ntuples/energy_ml_stage158'
SOFTWARE = ROOT / 'software/stage158'
SPOOL = Path.home() / 'condor/nu_muAnalysis/stage158'


def table(name, rows):
    with (OUT / name).open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter='\t', lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def archive_exact(target, payload):
    with tarfile.open(target, 'w:gz') as archive:
        for name, data in payload.items():
            member = tarfile.TarInfo(name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    with tarfile.open(target, 'r:gz') as archive:
        assert set(archive.getnames()) == set(payload)
        assert all(archive.extractfile(name).read() == data for name, data in payload.items())


def gnu(path):
    result = {}
    for line in path.read_text().splitlines():
        key, sep, value = line.strip().partition(': ')
        if sep:
            result[key] = value
    wall = result['Elapsed (wall clock) time (h:mm:ss or m:ss)']
    seconds = 0.
    for field in wall.split(':'):
        seconds = 60 * seconds + float(field)
    return dict(CPU_s=float(result['User time (seconds)']) + float(result['System time (seconds)']),
                wall_s=seconds, RSS_KiB=int(result['Maximum resident set size (kbytes)']))


def main():
    account = json.loads((OUT / 'scheduler_accounting.json').read_text())
    assert account['live_N'] == 0 and not account['unresolved_ids']
    assert all(r['JobStatus'] in [3, 4] for r in account['jobs'])
    assert json.loads((OUT / 'validation_summary.json').read_text())['passed']
    assert json.loads((OUT / 'comparison_summary.json').read_text())['passed']
    assert not (OUT / 'storage_cleanup.json').exists()
    SOFTWARE.mkdir(parents=True, exist_ok=True)

    # Native JSON is transported losslessly, without deriving scientific quantities locally.
    event_paths = sorted(CACHE.glob('native_*.json.gz')) + [CACHE / 'pilot.json.gz', CACHE / 'repeat.json.gz']
    assert len(event_paths) == 39
    event_payload = {}
    for path in event_paths:
        with gzip.open(path, 'rt') as stream:
            event_payload[str(path.relative_to(ROOT))] = stream.read()
    events = CACHE / 'event_records.json.gz'
    with gzip.open(events, 'wt') as stream:
        json.dump(event_payload, stream, separators=(',', ':'))
    with gzip.open(events, 'rt') as stream:
        assert json.load(stream) == event_payload

    source_payload, transports = {}, []
    for path in sorted(OUT.glob('*_submission.json')):
        record = json.loads(path.read_text())
        package = ROOT / record['package']['path']
        with tarfile.open(package, 'r:gz') as archive:
            for member in archive:
                if member.isfile() and member.name.endswith(('.py', '.hxx', '.sh', 'protocol.json')):
                    source_payload[record['phase'] + '/' + member.name] = archive.extractfile(member).read()
        worker = SPOOL / ('worker_' + package.parent.name + '.sh')
        source_payload[record['phase'] + '/submission/worker.sh'] = worker.read_bytes()
        transports.extend([package, CACHE / (record['phase'] + '_result.tar.gz')])
    archive_exact(SOFTWARE / 'source_snapshots.tar.gz', source_payload)

    summary_paths = sorted(OUT.glob('native_*_summary.json')) + [OUT / 'pilot_summary.json', OUT / 'repeat_summary.json']
    details = {str(p.relative_to(ROOT)): p.read_bytes() for p in summary_paths}
    archive_exact(SOFTWARE / 'native_audits.tar.gz', details)
    resources = []
    for path in sorted(OUT.glob('*_time.txt')):
        resources.append(dict(task=path.name.removesuffix('_time.txt'), **gnu(path)))
    table('process_resources.tsv', resources)
    summary_rows, source_rows = [], []
    for path in summary_paths:
        data = json.loads(path.read_text())
        summary_rows.append({k: data[k] for k in ['phase', 'N', 'count_closed_N', 'leading_match_N',
            'valid_geometry_parent_N', 'CPU_s', 'wall_s', 'ROOT_read_bytes', 'RSS_KiB', 'event_bytes']})
        if data['phase'].startswith('native_'):
            for source in data['metadata']:
                schema = source['schema']
                source_rows.append(dict(phase=data['phase'], request_index=source['request_index'],
                    origin=source['origin'], component=source['component'], REC=source['REC'],
                    parent_N=source['parent_N'], requested_N=source['requested_N'], schema_verified=schema['verified'],
                    parameter_type=schema['collection_parameter_member_type'], value_type=schema['parameter_value_member_type']))
    table('native_resources.tsv', summary_rows)
    table('source_schema.tsv', source_rows)
    native = [r for r in summary_rows if r['phase'].startswith('native_')]
    driver = [json.loads(p.read_text()) for p in sorted(OUT.glob('batch_*_driver.json'))]
    native_wall = sum(r['wall_s'] for r in native)
    driver_wall = sum(r['wall_s'] for r in driver)
    total_parents = sum(r['N'] for r in native)
    resource_report = dict(scheduler_CPU_s=account['total_CPU_s'], scheduler_aggregate_wall_s=account['total_execute_wall_s'],
        starts=account['starts'], submitted_request_CPUs=4, submitted_memory_MB=16000,
        scheduler_RequestCpus=sorted({r['RequestCpus'] for r in account['jobs'] if 'RequestCpus' in r}),
        scheduler_RequestMemory_MB=sorted({r['RequestMemory'] for r in account['jobs'] if 'RequestMemory' in r}),
        scheduler_max_reported_ResidentSetSize_KiB=max(r.get('ResidentSetSize', 0) for r in account['jobs']),
        scheduler_MemoryUsage_unresolved_expression=any(isinstance(r.get('MemoryUsage'), str) for r in account['jobs']),
        failed_jobs=[f"{r['ClusterId']}.{r['ProcId']}" for r in account['jobs'] if r.get('ExitCode') != 0],
        full_native_parent_N=total_parents, actual_REC_N=len(source_rows),
        actual_origins=sorted({r['origin'] for r in source_rows}),
        native_parents_by_component={c: sum(r['requested_N'] for r in source_rows if r['component'] == c)
                                    for c in sorted({r['component'] for r in source_rows})},
        full_native_internal_CPU_s=sum(r['CPU_s'] for r in native),
        full_native_internal_wall_s=native_wall, full_driver_aggregate_wall_s=driver_wall,
        measured_chain_wall_overlap=native_wall / driver_wall,
        full_native_ROOT_read_bytes=sum(r['ROOT_read_bytes'] for r in native),
        full_native_ROOT_bytes_per_parent=sum(r['ROOT_read_bytes'] for r in native) / total_parents,
        full_native_internal_CPU_s_per_parent=sum(r['CPU_s'] for r in native) / total_parents,
        max_native_RSS_KiB=max(r['RSS_KiB'] for r in native), GPU_jobs=0,
        interpretation='Chain overlap is measured concurrency, not a matched serial speedup. Scheduler totals include descendants; do not add nested process CPU again.')
    (OUT / 'resource_audit.json').write_text(json.dumps(resource_report, indent=2) + '\n')

    logs = sorted(OUT.glob('*.log'))
    logs.extend(SPOOL / 'logs' / f"{r['ClusterId']}.{r['ProcId']}.{suffix}"
                for r in account['jobs'] for suffix in ['out', 'err', 'log'])
    log_payload = {(str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else 'scheduler/' + p.name): p.read_bytes() for p in logs}
    archive_exact(SOFTWARE / 'worker_logs.tar.gz', log_payload)
    execution_paths = sorted(OUT.glob('*_time.txt')) + sorted(OUT.glob('*_driver.json'))
    archive_exact(SOFTWARE / 'execution_audits.tar.gz',
                  {str(p.relative_to(ROOT)): p.read_bytes() for p in execution_paths})
    (OUT / 'drivers.json').write_text(json.dumps(
        [json.loads(p.read_text()) for p in sorted(OUT.glob('*_driver.json'))], indent=2) + '\n')
    final_files = [events, CACHE / 'features.npz'] + [p for p in (ROOT / 'ml/artifacts/stage158').rglob('*') if p.is_file()]
    total_bytes = sum(p.stat().st_size for p in final_files)
    assert total_bytes <= 134217728, total_bytes
    deleted = []
    for path in event_paths + transports + summary_paths + execution_paths + [p for p in logs if p.is_relative_to(OUT)]:
        if path.exists():
            deleted.append(dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size))
            path.unlink()
    for path in transports:
        if path.parent != CACHE and path.parent.exists() and not any(path.parent.iterdir()):
            path.parent.rmdir()
    report = dict(all_jobs_terminal=True, event_text_equality=True, source_and_logs_byte_equality=True,
        event_capsule=dict(path=str(events.relative_to(ROOT)), bytes=events.stat().st_size),
        final_event_features_and_models_bytes=total_bytes, limit_bytes=134217728,
        archives=[dict(path=str(p.relative_to(ROOT)), bytes=p.stat().st_size) for p in SOFTWARE.glob('*.tar.gz')],
        deleted=deleted, deleted_bytes=sum(r['bytes'] for r in deleted),
        no_persistent_ROOT=True, original_inputs_other_stages_and_Stage54_untouched=True)
    (OUT / 'storage_cleanup.json').write_text(json.dumps(report, indent=2) + '\n')
    print(resource_report)
    print({k: v for k, v in report.items() if k != 'deleted'})


if __name__ == '__main__':
    main()
