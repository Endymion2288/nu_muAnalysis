#!/usr/bin/env python3
"""Collect exactly four first-attempt successes; never retry scientific jobs."""
import subprocess,tarfile
from risk_complementarity import *


def main():
    start=begin();cluster=json.loads((OUT/'package.json').read_text())['cluster']
    attrs='ClusterId,ProcId,JobStatus,NumJobStarts,ExitCode,RemoteWallClockTime,RemoteUserCpu,RemoteSysCpu,ResidentSetSize,RequestCpus,RequestMemory,MaxRuntime'
    history=json.loads(subprocess.check_output(['condor_history',str(cluster),'-match','4','-json','-attributes',attrs],text=True,timeout=45))
    assert len(history)==4 and all(h['JobStatus']==4 and h['ExitCode']==0 and h['NumJobStarts']==1 for h in history),history
    assert all(h['RequestCpus']==1 and h['RequestMemory']==3000 and h['MaxRuntime']==3600 for h in history)
    cpu=sum(h['RemoteUserCpu']+h['RemoteSysCpu'] for h in history)
    assert cpu<=7200 and all(h['RemoteWallClockTime']<=3600 for h in history)
    save(OUT/'condor_history.json',history)
    for job in JOBS:
        allowed={f'workbook/stage78_energy_ml/{job}/{n}' for n in ['fit.json','Q0_solver.json','Q_local_solver.json','worker.time']}
        allowed|={f'ml/artifacts/stage78/{job}/{n}' for n in ['head.json','head_training.npz','predictions.npz']}
        if job!='final':
            allowed|={f'ml/artifacts/stage78/{job}/inner{k}_{arm}.ubj' for k in range(3) if k!=int(job[-1]) for arm in ['U','F']}
        with tarfile.open(CACHE/(job+'.tar.gz')) as tar:
            for item in tar.getmembers():
                if item.isdir():continue
                assert item.isfile() and item.name in allowed,item.name
                path=REPO/item.name;assert not path.exists();path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(tar.extractfile(item).read())
    totals={k:sum(json.loads((OUT/j/'fit.json').read_text())[k] for j in JOBS) for k in ['formal_base_fits','formal_partition_fits','convex_problems','solver_calls']}
    assert totals==dict(formal_base_fits=12,formal_partition_fits=4,convex_problems=8,solver_calls=16)
    save(OUT/'condor_resources.json',dict(cluster=cluster,jobs=4,starts=4,retries=0,successful_jobs=4,**totals,
        remote_CPU_s=cpu,remote_wall_sum_s=sum(h['RemoteWallClockTime'] for h in history),request_CPUs_each=1,request_memory_MB_each=3000,
        scheduled_MaxRuntime_s=[h['MaxRuntime'] for h in history],result_transport_bytes=sum((CACHE/(j+'.tar.gz')).stat().st_size for j in JOBS),
        actual_EOS_physical_network_bytes='未测量',**resources(start)))
    print((OUT/'condor_resources.json').read_text())


if __name__=='__main__':main()
