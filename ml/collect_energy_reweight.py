#!/usr/bin/env python3
"""Collect exactly four successful jobs; no resubmission or retraining."""
import json
import subprocess
import tarfile
from energy_reweight import *


def main():
    cluster=json.loads((OUT/'package.json').read_text())['cluster']
    attrs='ClusterId,ProcId,JobStatus,NumJobStarts,ExitCode,RemoteWallClockTime,RemoteUserCpu,RemoteSysCpu,ResidentSetSize,RequestCpus,RequestMemory,RequestDisk,MaxRuntime,BytesRecvd,BytesSent'
    history=json.loads(subprocess.check_output(['condor_history',str(cluster),'-match','4','-json','-attributes',attrs],text=True))
    assert len(history)==4 and all(h['JobStatus']==4 and h['ExitCode']==0 and h['NumJobStarts']==1 for h in history)
    assert all(h['RequestCpus']==1 and h['RequestMemory']==3000 for h in history)
    failed=json.loads((OUT/'failed_launch_history.json').read_text())
    total_CPU=sum(h['RemoteUserCpu']+h['RemoteSysCpu'] for h in history+failed)
    assert total_CPU<=3600
    assert all(h['RemoteWallClockTime']<=1800 for h in history)
    save(OUT/'condor_history.json',history)
    for job in ['fold0','fold1','fold2','final']:
        allowed={f'workbook/stage73_energy_ml/{job}/{n}' for n in ['fit.json','weights.tsv','worker.time']}
        allowed|={f'ml/artifacts/stage73/{job}/{n}' for n in ['U.ubj','S.ubj','F.ubj','predictions.npz']}
        with tarfile.open(CACHE/(job+'.tar.gz')) as tar:
            for item in tar.getmembers():
                if item.isdir():continue
                assert item.isfile() and item.name in allowed,item.name
                path=REPO/item.name;assert not path.exists();path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(tar.extractfile(item).read())
    save(OUT/'condor_resources.json',dict(cluster=cluster,jobs=4,formal_fits=12,
        remote_CPU_s=sum(h['RemoteUserCpu']+h['RemoteSysCpu'] for h in history),
        failed_launch_CPU_s=sum(h['RemoteUserCpu']+h['RemoteSysCpu'] for h in failed),
        total_remote_CPU_s=total_CPU,submitted_jobs=8,failed_before_fit_jobs=4,successful_jobs=4,
        remote_wall_sum_s=sum(h['RemoteWallClockTime'] for h in history),
        request_CPUs_each=1,request_memory_MB_each=3000,scheduled_MaxRuntime_s=[h['MaxRuntime'] for h in history],
        final_scheduler_RSS_MiB=[h.get('ResidentSetSize',0)/1024 for h in history],
        result_transport_bytes=sum((CACHE/(j+'.tar.gz')).stat().st_size for j in ['fold0','fold1','fold2','final']),
        actual_EOS_physical_network_bytes='未测量'))
    print((OUT/'condor_resources.json').read_text())


if __name__=='__main__':main()
