"""Exact-job scheduler accounting; never scan history for a live job."""
import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ATTR = ['ClusterId', 'ProcId', 'JobStatus', 'ExitCode', 'ExitBySignal',
        'RemoteUserCpu', 'RemoteSysCpu', 'RemoteWallClockTime', 'NumJobStarts',
        'ResidentSetSize', 'RequestCpus', 'JobStartDate', 'CompletionDate', 'HoldReason']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', type=int, default=143, choices=[143, 144, 145])
    stage = parser.parse_args().stage
    OUT = ROOT/f'workbook/stage{stage}_energy_ml'
    budget = json.loads((OUT/'protocol.json').read_text())['resources']['CPU_budget_s']
    jobs = []
    live = []
    for path in sorted(OUT.glob('*_submission.json')):
        cluster = int(json.loads(path.read_text())['result'].split('.')[0])
        cmd = ['condor_q', str(cluster), '-json', '-attributes', ','.join(ATTR)]
        payload = subprocess.check_output(cmd, text=True).strip()
        rows = json.loads(payload) if payload else []
        if rows:
            live.extend(rows)
        else:
            payload = subprocess.check_output([
                'condor_history', '-since', 'CompletionDate < 1794084000',
                '-constraint', f'ClusterId == {cluster}', '-limit', '2',
                '-json', '-attributes', ','.join(ATTR)], text=True).strip()
            rows = json.loads(payload) if payload else []
        jobs.extend(rows)
    cpu = sum(r.get('RemoteUserCpu', 0)+r.get('RemoteSysCpu', 0) for r in jobs)
    result = dict(jobs=jobs, total_CPU_s=cpu,
                  total_execute_wall_s=sum(r.get('RemoteWallClockTime', 0) for r in jobs),
                  starts=sum(r.get('NumJobStarts', 0) for r in jobs),
                  live_N=len(live), completed_N=sum(r['JobStatus'] == 4 for r in jobs),
                  CPU_budget_s=budget)
    (OUT/'scheduler_accounting.json').write_text(json.dumps(result, indent=2)+'\n')
    print({k: v for k, v in result.items() if k != 'jobs'})
    if cpu >= budget and live:
        for row in live:
            subprocess.run(['condor_rm', f"{row['ClusterId']}.{row['ProcId']}"], check=True)
        raise RuntimeError('Frozen cumulative CPU budget reached')


if __name__ == '__main__':
    main()
