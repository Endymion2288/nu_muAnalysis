#!/usr/bin/env python3
"""Collect every extraction/training process, including queued or held jobs."""
import argparse
import json
import subprocess
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('jobs',nargs='+',help='schedd:cluster:expected_processes');a=p.parse_args()
attrs=['ClusterId','ProcId','JobStatus','NumJobStarts','QDate','JobStartDate','CompletionDate','RemoteWallClockTime',
       'RemoteUserCpu','RemoteSysCpu','ResidentSetSize','RequestMemory','RequestCpus','ExitCode','LastRemoteHost','HoldReason','Args']
records=[]
for item in a.jobs:
    schedd,cluster,count=item.split(':');found={};expected=int(count)
    for command in ['condor_q','condor_history']:
        remaining=expected-len(found)
        if command=='condor_history' and not remaining:continue
        cmd=[command,'-name',schedd,cluster,'-json','-attributes',','.join(attrs)]
        # Stop at the known completed count instead of scanning unrelated history for more matches.
        if command=='condor_history':cmd+=['-limit',str(remaining)]
        rows=json.loads(subprocess.check_output(cmd,text=True,timeout=30) or '[]')
        for row in rows:found[(row['ClusterId'],row['ProcId'])]=dict(schedd=schedd,**row)
    assert len(found)==expected,(item,len(found));records+=list(found.values())
records.sort(key=lambda r:(r['schedd'],r['ClusterId'],r['ProcId']))
out=Path(__file__).resolve().parents[1]/'workbook/stage47_energy_ml/condor_resources.json'
out.write_text(json.dumps(records,indent=2)+'\n')
print(json.dumps(dict(jobs=len(records),complete=sum(r['JobStatus']==4 for r in records),
                     starts=sum(r.get('NumJobStarts',0) for r in records),
                     wall_s=sum(r.get('RemoteWallClockTime',0) for r in records))))
