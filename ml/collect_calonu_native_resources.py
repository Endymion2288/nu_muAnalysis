#!/usr/bin/env python3
"""Preserve successful and failed bounded native-read job costs."""
import json
import re
from datetime import datetime
from pathlib import Path

from report_calonu_native import table


def main():
    repo = Path(__file__).resolve().parents[1]
    out = repo/'workbook/stage37_energy_ml'
    logs = Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage37/logs')
    rows = []
    for cluster, groups in [(2187365, [0, 5, 6, 11]), (2187366, [6, 11])]:
        events = {i: {} for i in range(len(groups))}
        for block in (logs/f'{cluster}.log').read_text().split('...'):
            m = re.search(r'(000|001|005) \(\d+\.(\d+)\.000\) (\d\d/\d\d \d\d:\d\d:\d\d)', block)
            if m:
                code, proc, stamp = m.groups()
                events[int(proc)][code] = (datetime.strptime('2026/'+stamp, '%Y/%m/%d %H:%M:%S'), block)
        for proc, e in events.items():
            assert all(k in e for k in ['000', '001', '005'])
            stderr = (logs/f'{cluster}.{proc}.err').read_text()
            measurements = re.findall(r'stage37_(locate|native) wall_s=([\d.]+) max_rss_KiB=(\d+) user_s=([\d.]+) system_s=([\d.]+)', stderr)
            assert len(measurements) == 2
            done = e['005'][1]
            code = int(re.search(r'return value (\d+)', done).group(1))
            rows.append(dict(cluster=cluster, proc=proc, group=groups[proc], schedd='bigbird21.cern.ch',
                             exit_code=code, requested_cpus=1, requested_memory_MB=3000, requested_gpus=0,
                             submitted_local=e['000'][0].isoformat(), terminated_local=e['005'][0].isoformat(),
                             submit_to_finish_s=(e['005'][0]-e['000'][0]).total_seconds(),
                             execute_s=int(re.search(r'TimeExecute \(s\)\s*:\s*(\d+)', done).group(1)),
                             locate_wall_s=float(measurements[0][1]), native_wall_s=float(measurements[1][1]),
                             wrapper_cpu_s=sum(float(m[3])+float(m[4]) for m in measurements),
                             peak_rss_KiB=max(int(m[2]) for m in measurements),
                             reason='success' if code == 0 else 'Over-strict BeamTruth mass equality; momentum identical, mass differs 1 float ULP'))
    table(out/'condor_resources.tsv', rows)
    summary = dict(jobs=len(rows), successful=sum(r['exit_code'] == 0 for r in rows), failed=sum(r['exit_code'] != 0 for r in rows),
                   wrapper_wall_s=sum(r['locate_wall_s']+r['native_wall_s'] for r in rows),
                   wrapper_cpu_s=sum(r['wrapper_cpu_s'] for r in rows), peak_rss_KiB=max(r['peak_rss_KiB'] for r in rows),
                   success_wrapper_wall_s=sum(r['locate_wall_s']+r['native_wall_s'] for r in rows if r['exit_code'] == 0),
                   failed_wrapper_wall_s=sum(r['locate_wall_s']+r['native_wall_s'] for r in rows if r['exit_code'] != 0),
                   first_submit_to_last_finish_s=(max(datetime.fromisoformat(r['terminated_local']) for r in rows)-min(datetime.fromisoformat(r['submitted_local']) for r in rows)).total_seconds(),
                   GPU_allocation_s=0, ML_fits=0, G4_events=0)
    (out/'condor_summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    # Local pilots/failures from the preceding worker remain in /tmp; preserve compact time records.
    local = []
    for path in sorted(Path('/tmp').glob('stage37*.time')):
        local.append(dict(path=str(path), timing=path.read_text().strip()))
    (out/'local_timing_records.json').write_text(json.dumps(local, indent=2)+'\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
