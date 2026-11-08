"""Terminal exact-byte archives and storage accounting, without event analysis."""
import csv
import json
import subprocess
import tarfile
from pathlib import Path

from stage158_finalize import archive_exact, gnu

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'workbook/stage165_energy_ml'
CACHE = ROOT / 'ntuples/energy_ml_stage165'
SOFTWARE = ROOT / 'software/stage165'
SPOOL = Path.home() / 'condor/nu_muAnalysis/stage165'


def main():
    account = json.loads((OUT / 'scheduler_accounting.json').read_text())
    assert account['live_N'] == 0 and account['total_CPU_s'] <= 600
    assert all(r['JobStatus'] in [3, 4] for r in account['jobs'])
    assert json.loads((OUT / 'independent_validation.json').read_text())['passed']
    assert json.loads((OUT / 'analysis_summary.json').read_text())['passed']
    assert json.loads((OUT / 'analysis_summary.json').read_text())['energy_fits'] == 0
    assert not (OUT / 'storage_cleanup.json').exists()
    baseline = json.loads((ROOT / 'workbook/stage158_energy_ml/preexisting_asset_snapshot.json').read_text())
    assert all((ROOT / p).stat().st_size == v['bytes'] and (ROOT / p).stat().st_mtime_ns == v['mtime_ns']
               for p, v in baseline.items())
    SOFTWARE.mkdir(parents=True, exist_ok=True)
    source_payload, transports, checks = {}, [], []
    for path in sorted(OUT.glob('*_submission.json')):
        record = json.loads(path.read_text()); phase = record['phase']
        package = ROOT / record['package']['path']
        with tarfile.open(package, 'r:gz') as archive:
            for member in archive:
                if not member.isfile():
                    continue
                data = archive.extractfile(member).read()
                if member.name.endswith(('.npz', '.ubj')):
                    assert (ROOT / member.name).read_bytes() == data, member.name
                else:
                    source_payload[phase + '/' + member.name] = data
        worker = SPOOL / ('worker_' + package.parent.name + '.sh')
        source_payload[phase + '/submission/worker.sh'] = worker.read_bytes()
        source_payload[phase + '/submission/descriptor.sub'] = record['descriptor'].encode()
        transports.append(package)
        cluster = int(record['result'].split('.')[0])
        row = next(r for r in account['jobs'] if r['ClusterId'] == cluster)
        result = CACHE / (phase + '_result.tar.gz')
        if row.get('NumJobStarts', 0) == 0 and row['JobStatus'] == 3:
            assert not result.exists()
            checks.append(dict(phase=phase, removed_unstarted=True, CPU_s=0))
            continue
        assert row.get('ExitCode') == 0 and result.exists(), phase
        with tarfile.open(result, 'r:gz') as archive:
            for member in archive:
                if member.isfile():
                    assert (ROOT / member.name).read_bytes() == archive.extractfile(member).read(), member.name
        transports.append(result)
        checks.append(dict(phase=phase, result_archive_exact=True))
    archive_exact(SOFTWARE / 'source_snapshots.tar.gz', source_payload)
    times = sorted(OUT.glob('*_time.txt'))
    resources = [dict(task=p.stem.removesuffix('_time'), **gnu(p)) for p in times]
    with (OUT / 'process_resources.tsv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(resources[0]), delimiter='\t', lineterminator='\n')
        writer.writeheader(); writer.writerows(resources)
    archive_exact(SOFTWARE / 'execution_audits.tar.gz', {str(p.relative_to(ROOT)): p.read_bytes() for p in times})
    logs = sorted(OUT.glob('*.log'))
    logs.extend(SPOOL / 'logs' / f"{r['ClusterId']}.{r['ProcId']}.{suffix}"
                for r in account['jobs'] for suffix in ['out', 'err', 'log']
                if (SPOOL / 'logs' / f"{r['ClusterId']}.{r['ProcId']}.{suffix}").exists())
    archive_exact(SOFTWARE / 'worker_logs.tar.gz', {
        str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else 'scheduler/' + p.name: p.read_bytes() for p in logs})
    final_files = list(CACHE.glob('*.npz'))
    assert not final_files and not (ROOT / 'ml/artifacts/stage165').exists()
    total_bytes = sum(p.stat().st_size for p in final_files)
    assert total_bytes <= 1048576
    report = dict(scheduler_CPU_s=account['total_CPU_s'], scheduler_aggregate_wall_s=account['total_execute_wall_s'],
        submissions=len(account['jobs']), starts=account['starts'], live_N=0,
        removed_unstarted=[r['ClusterId'] for r in account['jobs'] if r['JobStatus'] == 3 and r.get('NumJobStarts', 0) == 0],
        request_CPUs=4, request_memory_MB=12000,
        scheduler_RequestCpus=sorted({r['RequestCpus'] for r in account['jobs'] if 'RequestCpus' in r}),
        scheduler_RequestMemory_MB=sorted({r['RequestMemory'] for r in account['jobs'] if 'RequestMemory' in r}),
        scheduler_max_ResidentSetSize_KiB=max(r.get('ResidentSetSize', 0) for r in account['jobs']),
        GPU_jobs=0, new_G4=0, new_independent_nu=0, energy_fits=0, model_forward=0,
        interpretation='Scheduler totals include analysis workers; do not add nested GNU or process CPU. No matched serial speedup measured.')
    (OUT / 'resource_audit.json').write_text(json.dumps(report, indent=2) + '\n')
    # Query the live queue before removing only this stage's terminal submission files.
    payload = subprocess.check_output(['condor_q', '-json', '-attributes', 'ClusterId,Iwd'], text=True).strip()
    active = json.loads(payload) if payload else []
    assert all(Path(r.get('Iwd', '/')) != SPOOL for r in active)
    spool_files = [p for p in SPOOL.rglob('*') if p.is_file()]
    assert all(p.suffix in ['.sh', '.sub', '.out', '.err', '.log'] for p in spool_files)
    archive_exact(SOFTWARE / 'terminal_spool.tar.gz', {str(p.relative_to(SPOOL)): p.read_bytes() for p in spool_files})
    deleted = []
    for path in transports + times + [p for p in logs if p.is_relative_to(OUT)] + spool_files:
        if path.exists():
            deleted.append(dict(path=str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path), bytes=path.stat().st_size))
            path.unlink()
    for path in transports:
        if path.parent != CACHE and path.parent.exists() and not any(path.parent.iterdir()):
            path.parent.rmdir()
    index = dict(stage=165, terminal_jobs=[r['ClusterId'] for r in account['jobs']],
        archive=str(SOFTWARE / 'terminal_spool.tar.gz'), source_and_logs_exact=True)
    (SPOOL / 'execution_index.json').write_text(json.dumps(index, indent=2) + '\n')
    result = dict(all_jobs_terminal=True, event_inputs_byte_equality=True, source_and_logs_byte_equality=True,
        transport_checks=checks, final_event_features_and_models_bytes=total_bytes, limit_bytes=1048576,
        final_files=[dict(path=str(p.relative_to(ROOT)), bytes=p.stat().st_size) for p in final_files],
        archives=[dict(path=str(p.relative_to(ROOT)), bytes=p.stat().st_size) for p in SOFTWARE.glob('*.tar.gz')],
        deleted=deleted, deleted_bytes=sum(r['bytes'] for r in deleted),
        no_persistent_ROOT=True, Stage54_size_mtime_preserved=True, live_queue_Iwd_checked=True)
    (OUT / 'storage_cleanup.json').write_text(json.dumps(result, indent=2) + '\n')
    print(report)
    print({k: v for k, v in result.items() if k not in ['deleted', 'transport_checks', 'final_files']})


if __name__ == '__main__':
    main()
