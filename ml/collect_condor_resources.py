#!/usr/bin/env python3
"""Read only the known number of process ClassAds, querying current jobs first."""
import argparse
import json
import subprocess
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('jobs',nargs='+',help='schedd:cluster:process_count');a=p.parse_args()
attrs=['ClusterId','ProcId','JobStatus','NumJobStarts','QDate','JobStartDate','CompletionDate','RemoteWallClockTime','RemoteUserCpu','RemoteSysCpu',
       'ResidentSetSize','RequestMemory','RequestCpus','ExitCode','LastRemoteHost','HoldReason','Args']
records=[]
for item in a.jobs:
    schedd,cluster,count=item.split(':');expected=int(count);found={}
    for command in ['condor_q','condor_history']:
        remaining=expected-len(found)
        if command=='condor_history' and remaining==0:continue
        cmd=[command,'-name',schedd,cluster,'-json','-attributes',','.join(attrs)]
        if command=='condor_history':cmd+=['-limit',str(remaining)]
        rows=json.loads(subprocess.check_output(cmd,text=True,timeout=30) or '[]')
        for row in rows:found[(row['ClusterId'],row['ProcId'])]=dict(schedd=schedd,**row)
    assert len(found)==expected,(item,len(found));records+=list(found.values())
records.sort(key=lambda r:(r['schedd'],r['ClusterId'],r['ProcId']))
a.output.write_text(json.dumps(records,indent=2)+'\n');print(json.dumps(dict(processes=len(records),complete=sum(r['JobStatus']==4 for r in records),starts=sum(r.get('NumJobStarts',0) for r in records))))
