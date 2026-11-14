#!/usr/bin/env python3
"""Compact Condor completion accounting for material-map reconstruction production."""
import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cluster', action='append', required=True, help='label=cluster ID')
    p.add_argument('--log', action='append', required=True, help='label=Condor event log; bound the accounting to this production')
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(); result = {}; logs = dict(item.split('=',1) for item in args.log)
    fields = ['ClusterId','ProcId','JobStatus','ExitCode','ExitBySignal','ExitSignal',
              'RemoteWallClockTime','JobStartDate','CompletionDate','LastRemoteHost',
              'MemoryUsage','NumJobStarts','HoldReason']
    for item in args.cluster:
        label, cluster = item.split('=',1); assert cluster.isdigit()
        jobs = []
        for executable in ['condor_q','condor_history']:
            cmd = [executable, cluster, '-json', '-attributes', ','.join(fields)]
            if executable == 'condor_history':
                cmd += ['-userlog', logs[label]]
            output = subprocess.check_output(cmd,text=True).strip()
            jobs += json.loads(output) if output else []
        unique = {}
        for job in jobs: unique[job['ClusterId'],job['ProcId']] = job
        jobs = sorted(unique.values(),key=lambda j:j['ProcId'])
        done = [j for j in jobs if j['JobStatus'] == 4]
        failed = [j for j in done if j.get('ExitCode') != 0 or j.get('ExitBySignal',False)]
        result[label] = dict(cluster=int(cluster), states=dict(Counter(j['JobStatus'] for j in jobs)),
            completed=len(done), failed=len(failed), failed_proc_ids=[j['ProcId'] for j in failed], jobs=jobs)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:{kk:vv for kk,vv in v.items() if kk!='jobs'} for k,v in result.items()},indent=2))


if __name__ == '__main__': main()
