#!/usr/bin/env python3
"""Collect four successful fixed stage76 inference jobs; no retries."""
import json
import subprocess
import tarfile
from pathlib import Path
from exact_conditional_decision import *


def main():
    start=begin();cluster=json.loads((OUT/'package.json').read_text())['cluster']
    attrs='ClusterId,ProcId,JobStatus,NumJobStarts,ExitCode,RemoteWallClockTime,RemoteUserCpu,RemoteSysCpu,ResidentSetSize,RequestCpus,RequestMemory,RequestDisk,MaxRuntime,BytesRecvd,BytesSent'
    history=json.loads(subprocess.check_output(['condor_history',str(cluster),'-match','4','-json','-attributes',attrs],text=True,timeout=60))
    assert len(history)==4 and all(h['JobStatus']==4 and h['ExitCode']==0 and h['NumJobStarts']==1 for h in history)
    assert all((h['RequestCpus'],h['RequestMemory'],h['MaxRuntime'])==(1,3000,1800) for h in history)
    assert sum(h['RemoteUserCpu']+h['RemoteSysCpu'] for h in history)<=3600
    assert all(h['RemoteWallClockTime']<=1800 for h in history)
    save(OUT/'condor_history.json',history)
    for job in JOBS:
        allowed={f'workbook/stage76_energy_ml/{job}/{n}' for n in ['inference.json','worker.time']}
        allowed|={f'ml/artifacts/stage76/{job}/{n}' for n in ['predictions.npz']}
        with tarfile.open(CACHE/(job+'.tar.gz')) as tar:
            for item in tar.getmembers():
                if item.isdir():continue
                assert item.isfile() and item.name in allowed,item.name
                path=REPO/item.name;assert not path.exists();path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(tar.extractfile(item).read())
    log=Path(f'/afs/cern.ch/user/x/xcheng/nu_mu_stage76/logs/decision.{cluster}.log')
    (OUT/'condor_events.txt').write_text('\n'.join(v.rstrip() for v in log.read_text().splitlines())+'\n')
    save(OUT/'condor_resources.json',dict(cluster=cluster,jobs=4,formal_fits=0,formal_point_jobs=4,starts=4,successful_jobs=4,
        remote_CPU_s=sum(h['RemoteUserCpu']+h['RemoteSysCpu'] for h in history),
        remote_wall_sum_s=sum(h['RemoteWallClockTime'] for h in history),
        request_CPUs_each=1,request_memory_MB_each=3000,scheduled_MaxRuntime_s=[h['MaxRuntime'] for h in history],
        result_transport_bytes=sum((CACHE/(j+'.tar.gz')).stat().st_size for j in JOBS),
        actual_EOS_physical_network_bytes='未测量',**resources(start)))
    print((OUT/'condor_resources.json').read_text())


if __name__=='__main__':main()
