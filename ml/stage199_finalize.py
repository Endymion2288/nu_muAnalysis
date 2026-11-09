"""Compact verified terminal returns using exact bytes, without local event analysis."""
import csv
import io
import json
import shutil
import subprocess
import tarfile
from pathlib import Path

from stage158_finalize import gnu

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'workbook/stage199_energy_ml'
CACHE = ROOT / 'ntuples/energy_ml_stage199'
SOFTWARE = ROOT / 'software/stage199'
SPOOL = Path.home() / 'condor/nu_muAnalysis/stage199'


def read(name):
    return json.loads((OUT / name).read_text())


def exact_archive(target, paths):
    """Store original compressed bytes once; verify every member before deletion."""
    with tarfile.open(target, 'w') as archive:
        for path in paths:
            archive.add(path, arcname=str(path.relative_to(ROOT)), recursive=False)
    with tarfile.open(target) as archive:
        assert len(archive.getmembers()) == len(paths)
        for path in paths:
            assert archive.extractfile(str(path.relative_to(ROOT))).read() == path.read_bytes()


def main():
    assert not (OUT / 'storage.json').exists(), 'Already compacted; no repeated cleanup'
    status = read('scheduler_accounting.json')
    assert status['live_N'] == 0 and not status['unmaterialized_or_unobserved'] and not status['failed']
    assert read('independent_validation.json')['passed']
    assert read('prepare.json')['sources_N'] == 1134 and read('fit.json')['formal_fits_N'] == 6
    kubeflow = {}
    for phase in ['prepare', 'fit', 'report', 'audit']:
        if read(phase + '_submission.json')['platform'] != 'kubeflow':
            continue
        name = read(phase + '_submission.json').get('job_name') or 'nu-mu-energy-stage199-' + phase
        job = json.loads(subprocess.check_output(
            ['kubectl', 'get', 'job', name, '-n', 'xcheng', '-o', 'json'], text=True))
        pods = json.loads(subprocess.check_output(
            ['kubectl', 'get', 'pods', '-n', 'xcheng', '-l', 'job-name=' + name, '-o', 'json'], text=True))
        assert job['status'].get('succeeded') == 1 and not job['status'].get('active', 0)
        assert len(pods['items']) == 1 and pods['items'][0]['status']['phase'] == 'Succeeded'
        pod = pods['items'][0]
        terminated = next(v for v in pod['status']['containerStatuses'] if v['name'] == phase)['state']['terminated']
        assert terminated['exitCode'] == 0
        (OUT / f'kubeflow_{phase}_job.json').write_text(json.dumps(job, indent=2) + '\n')
        (OUT / f'kubeflow_{phase}_pod.json').write_text(json.dumps(pod, indent=2) + '\n')
        log = subprocess.check_output(['kubectl', 'logs', '-n', 'xcheng', pod['metadata']['name'], '-c', phase])
        (OUT / f'kubeflow_{phase}.log').write_bytes(log)
        kubeflow[phase] = dict(job=job['metadata']['name'], pod=pod['metadata']['name'],
            node=pod['spec']['nodeName'], resources=pod['spec']['containers'][0]['resources'],
            startedAt=terminated['startedAt'], finishedAt=terminated['finishedAt'], exitCode=0,
            process=gnu(OUT / f'{phase}.time'))
    failures = read('execution_failures.json') if (OUT / 'execution_failures.json').exists() else []
    (OUT / 'kubeflow_accounting.json').write_text(json.dumps(
        dict(phases=kubeflow, exitCode=0, failed_attempts=failures,
             failed_attempt_process_CPU_unmeasured=True, scheduler_CPU_unmeasured=True), indent=2) + '\n')

    source_archives = []
    expanded = []
    resource_rows = []
    source_rows = []
    for phase in ['pilot', 'production']:
        sub, collection = read(phase + '_submission.json'), read(phase + '_collection.json')
        assert collection['returned'] == len(sub['indices']) == collection['success'] and not collection['failed']
        for index in sub['indices']:
            path = CACHE / f'{phase}_{index}.tar.gz'
            directory = CACHE / f'{phase}_{index}'
            # Compare all unwrapped members with their original transport bytes.
            with tarfile.open(path) as archive:
                original = {str(Path(m.name).relative_to('result')): archive.extractfile(m).read()
                            for m in archive.getmembers() if m.isfile()}
            assert set(original) == {str(p.relative_to(directory)) for p in directory.rglob('*') if p.is_file()}
            assert all((directory / name).read_bytes() == data for name, data in original.items())
            timings = [dict(phase=phase, index=index, process=timing.stem, **gnu(timing))
                       for timing in sorted(directory.glob('*.time'))]
            resource_rows.extend(timings)
            summary = json.loads((directory / 'summary.json').read_text())
            source_rows.append(dict(phase=phase, index=index, mode=summary['source']['mode'],
                full_source=phase == 'production' or summary['source']['mode'] == 'local',
                parent_N=summary.get('original_parent_N', summary['raw_N']), raw_extracted_N=summary['raw_N'],
                selected_N=summary['selected_N'], nested_CPU_s=sum(t['CPU_s'] for t in timings),
                nested_wall_s=sum(t['wall_s'] for t in timings),
                extraction_uproot_requested_bytes=summary['requested_uproot_bytes']))
            source_archives.append(path)
            expanded.append(directory)
    source_archive = SOFTWARE / 'source_results.tar'
    exact_archive(source_archive, source_archives)
    for phase in ['prepare', 'fit', 'report', 'audit']:
        assert (OUT / f'{phase}_exitcode.txt').read_text().strip() == '0'
        resource_rows.append(dict(phase=phase, index='', process='science', **gnu(OUT / f'{phase}.time')))
    with (OUT / 'process_resources.tsv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(resource_rows[0]), delimiter='\t', lineterminator='\n')
        writer.writeheader()
        writer.writerows(resource_rows)
    with (OUT / 'source_resources.tsv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(source_rows[0]), delimiter='\t', lineterminator='\n')
        writer.writeheader()
        writer.writerows(source_rows)
    complete = [r for r in source_rows if r['full_source']]
    cpu = sum(r['nested_CPU_s'] for r in complete)
    resource_audit = dict(full_new_sources_N=len(complete),
        full_original_parents_N=sum(r['parent_N'] for r in complete),
        full_new_selected_N=sum(r['selected_N'] for r in complete),
        full_nested_CPU_s=cpu, full_nested_wall_s=sum(r['nested_wall_s'] for r in complete),
        full_original_parents_per_nested_CPU_s=sum(r['parent_N'] for r in complete) / cpu,
        full_new_selected_per_nested_CPU_s=sum(r['selected_N'] for r in complete) / cpu,
        full_extraction_uproot_requested_bytes=sum(r['extraction_uproot_requested_bytes'] for r in complete),
        total_analysis_reconstruction_IO_unmeasured=True,
        scheduler_CPU_s=status['scheduler_CPU_s'], scheduler_aggregate_wall_s=status['aggregate_execute_wall_s'],
        interpretation='Nested source times exclude cached666 sources and are already within scheduler CPU. Not a matched serial speedup; do not add these CPU totals.')
    (OUT / 'resource_audit.json').write_text(json.dumps(resource_audit, indent=2) + '\n')

    logs = sorted(OUT.glob('*.log'))
    for row in status['jobs']:
        for suffix in ['out', 'err', 'log']:
            path = SPOOL / 'logs' / f"{row['ClusterId']}.{row['ProcId']}.{suffix}"
            if path.is_file():
                logs.append(path)
            else:
                assert f"{row['ClusterId']}.{row['ProcId']}" in status['intentionally_cancelled_unstarted']
    assert all(path.is_file() for path in logs)
    log_archive = SOFTWARE / 'worker_logs.tar.gz'
    payload = {(str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else 'scheduler/' + path.name): path.read_bytes()
               for path in logs}
    with tarfile.open(log_archive, 'w:gz') as archive:
        for name, data in payload.items():
            member = tarfile.TarInfo(name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    with tarfile.open(log_archive) as archive:
        assert set(archive.getnames()) == set(payload)
        assert all(archive.extractfile(name).read() == data for name, data in payload.items())

    science_archives = [CACHE / f'{phase}_result.tar.gz' for phase in ['prepare', 'fit', 'report', 'audit']]
    for path in science_archives:
        with tarfile.open(path) as archive:
            for member in archive.getmembers():
                if member.isfile():
                    assert (ROOT / member.name).read_bytes() == archive.extractfile(member).read(), member.name
    removed = []
    # Old inputs, immutable source packages and other stages remain outside this list.
    for path in source_archives + science_archives + expanded + [p for p in logs if p.is_relative_to(OUT)]:
        size = sum(p.stat().st_size for p in path.rglob('*') if p.is_file()) if path.is_dir() else path.stat().st_size
        removed.append(dict(path=str(path.relative_to(ROOT)), bytes=size))
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    retained = [p for directory in [CACHE, SOFTWARE, ROOT / 'ml/artifacts/stage199']
                for p in directory.rglob('*') if p.is_file()]
    result = dict(passed=True, all_jobs_terminal=True, original_return_and_expanded_bytes_verified=True,
                  source_archive=str(source_archive.relative_to(ROOT)), source_return_archives_N=len(source_archives),
                  retained_scientific_bytes=sum(p.stat().st_size for p in retained),
                  removed_duplicate_bytes=sum(r['bytes'] for r in removed), removed=removed,
                  retained=[dict(path=str(p.relative_to(ROOT)), bytes=p.stat().st_size) for p in retained],
                  no_persistent_ROOT=not any(p.suffix == '.root' for p in retained),
                  other_stages_and_untracked_user_work_untouched=True,
                  rerun_audit_requires_restoring_source_results_archive=True)
    (OUT / 'storage.json').write_text(json.dumps(result, indent=2) + '\n')
    print({k: v for k, v in result.items() if k not in ['removed', 'retained']})


if __name__ == '__main__':
    main()
