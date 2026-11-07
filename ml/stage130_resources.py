"""Unique scheduler-attempt ledger, including removed and failed submissions."""
import csv
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'workbook/stage130_energy_ml'
ATTRS = ['ClusterId', 'ProcId', 'JobStatus', 'NumJobStarts', 'ExitCode',
         'RemoteUserCpu', 'RemoteSysCpu', 'RemoteWallClockTime', 'RequestCpus',
         'RequestMemory', 'RequestGpus', 'JobStartDate', 'CompletionDate', 'EnteredCurrentStatus', 'HoldReason']


def main():
    submitted = {}
    for path in sorted(OUT.glob('*_submission_[0-9]*.json')):
        record = json.loads(path.read_text())
        cluster = int(re.match(r'\d+', record['result'])[0])
        batches = record.get('batches', [[]])
        for proc, indices in enumerate(batches):
            submitted[cluster, proc] = dict(cluster=cluster, proc=proc,
                phase=record['phase'], source_indices=','.join(map(str, indices)),
                package=record['package']['path'])
    correction = json.loads((OUT / 'preexecution_submission_correction.json').read_text())
    submitted.setdefault((correction['cluster'], 0), dict(cluster=correction['cluster'],
        proc=0, phase='preexecution_correction', source_indices=','.join(map(str, correction['wrong_indices'])),
        package='not_executed'))
    clusters = sorted({c for c, _ in submitted})
    constraint = ' || '.join(f'ClusterId == {c}' for c in clusters)
    measured = {}
    for command in ['condor_history', 'condor_q']:
        # History is completion-ordered. Bound the scan to before this stage's
        # earliest submission rather than scanning years of unrelated jobs.
        options = ['-since', 'CompletionDate < 1794054000'] if command == 'condor_history' else []
        payload = subprocess.check_output([command, *options, '-constraint', constraint,
            '-json', '-attributes', ','.join(ATTRS)], text=True, timeout=60)
        records = json.loads(payload.strip() or '[]')
        for record in records:
            measured[record['ClusterId'], record['ProcId']] = record
    rows = []
    for key, submission in sorted(submitted.items()):
        record = measured.get(key, {})
        status = record.get('JobStatus')
        rows.append(dict(**submission, status=status, observed=bool(record),
            terminal=status in [3, 4], starts=record.get('NumJobStarts', 0),
            exit_code=record.get('ExitCode'), removed=status == 3,
            scheduler_CPU_s=record.get('RemoteUserCpu', 0) + record.get('RemoteSysCpu', 0),
            execute_wall_s=record.get('RemoteWallClockTime', 0),
            start_epoch=record.get('JobStartDate', 0),
            completion_epoch=record.get('CompletionDate', 0) or (record.get('EnteredCurrentStatus', 0) if status in [3, 4] else 0),
            requested_CPUs=record.get('RequestCpus'), requested_memory_MB=record.get('RequestMemory'),
            requested_GPUs=record.get('RequestGpus', 0), hold_reason=record.get('HoldReason', '')))
    with (OUT / 'resource_jobs.tsv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter='\t',
                                lineterminator='\n', quoting=csv.QUOTE_NONNUMERIC)
        writer.writeheader()
        writer.writerows(rows)
    events = {}
    for row in rows:
        start, finish = row['start_epoch'], row['completion_epoch']
        if not start or (row['terminal'] and not row['starts'] and not row['execute_wall_s']):
            continue
        for stamp, sign in [(start, 1)] + ([(finish, -1)] if finish else []):
            jobs, cores = events.get(stamp, (0, 0))
            events[stamp] = jobs+sign, cores+sign*(row['requested_CPUs'] or 0)
    active_jobs = active_cores = peak_jobs = peak_cores = 0
    for _, (jobs, cores) in sorted(events.items()):
        active_jobs += jobs
        active_cores += cores
        peak_jobs, peak_cores = max(peak_jobs, active_jobs), max(peak_cores, active_cores)
    summary = dict(unique_submitted=len(rows), observed=sum(r['observed'] for r in rows),
        unmaterialized_or_missing=sum(not r['observed'] for r in rows),
        terminal=sum(r['terminal'] for r in rows), starts=sum(r['starts'] for r in rows),
        removed=sum(r['removed'] for r in rows),
        failed=sum(r['terminal'] and r['exit_code'] not in [0, None] for r in rows),
        scheduler_CPU_s=sum(r['scheduler_CPU_s'] for r in rows),
        aggregate_execute_wall_s=sum(r['execute_wall_s'] for r in rows),
        scheduler_start_completion_peak_jobs=peak_jobs,
        scheduler_start_completion_peak_requested_CPUs=peak_cores,
        allocated_execute_core_s=sum(r['execute_wall_s']*(r['requested_CPUs'] or 0) for r in rows),
        GPU_jobs=sum(bool(r['requested_GPUs']) for r in rows),
        scope='scheduler cumulative user+system and execute wall per unique attempt;includes failures/removals;child GNU time not added;peak from1s start/completion intervals and requested cores,not instantaneous hardware utilization;unmaterialized factory procs remain pending;live usage may lag')
    (OUT / 'resource_summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(summary)


if __name__ == '__main__':
    main()
