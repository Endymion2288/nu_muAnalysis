#!/usr/bin/env python3
"""Collect compact Condor provenance without retaining full duplicated ClassAds."""
import argparse
import json
import subprocess
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('jobs',nargs='+',help='schedd:cluster');a=p.parse_args()
attrs=['ClusterId','JobStatus','NumJobStarts','QDate','JobStartDate','CompletionDate','RemoteWallClockTime',
       'RemoteUserCpu','RemoteSysCpu','ResidentSetSize','MemoryUsage','RequestMemory','RequestCpus','ExitCode','LastRemoteHost','HoldReason']
records=[]
for item in a.jobs:
    schedd,cluster=item.split(':')
    result=[]
    for command in ['condor_q','condor_history']:
        args=[command,'-name',schedd,cluster,'-json','-attributes',','.join(attrs)]
        if command=='condor_history': args += ['-limit','1']
        raw=subprocess.check_output(args,text=True,timeout=20)
        result=json.loads(raw or "[]")
        if result:break
    assert len(result)==1,(item,result)
    rec=dict(schedd=schedd,**result[0]);records.append(rec)
out=Path(__file__).resolve().parents[1]/'workbook/stage44_energy_ml/condor_resources.json'
out.write_text(json.dumps(records,indent=2)+'\n');print(json.dumps(records))
