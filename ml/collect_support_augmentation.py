#!/usr/bin/env python3
"""Collect one successful frozen stage71 job, preserving schedd and userlog costs."""
import argparse
import json
import subprocess
import tarfile
from pathlib import Path
from support_augmentation import REPO, OUT, ART, CACHE, save


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--cluster',required=True,type=int);args=parser.parse_args()
    attrs=['ClusterId','ProcId','JobStatus','NumJobStarts','ExitCode','JobStartDate','CompletionDate','RemoteWallClockTime',
           'RemoteUserCpu','RemoteSysCpu','ResidentSetSize','RequestCpus','RequestMemory','RequestDisk','MaxRuntime','BytesRecvd','BytesSent']
    history=json.loads(subprocess.check_output(['condor_history',str(args.cluster),'-match','1','-json','-attributes',','.join(attrs)],text=True))
    assert len(history)==1
    ad=history[0];assert ad['JobStatus']==4 and ad['NumJobStarts']==1 and ad['ExitCode']==0
    assert (ad['RequestCpus'],ad['RequestMemory'])==(1,3000)
    assert ad['RemoteUserCpu']+ad['RemoteSysCpu']<=900 and ad['RemoteWallClockTime']<=900
    save(OUT/'condor_history.json',history)
    eventlog=Path(f'/afs/cern.ch/user/x/xcheng/nu_mu_stage71/logs/augmentation.{args.cluster}.log')
    userlog=json.loads(subprocess.check_output(['condor_history','-userlog',str(eventlog),'-json'],text=True))
    save(OUT/'condor_userlog_history.json',userlog)
    (OUT/'condor_events.log').write_text('\n'.join(line.rstrip() for line in eventlog.read_text().splitlines())+'\n')
    protocol=OUT/'protocol.json';p=json.loads(protocol.read_text())
    allowed={'workbook/stage71_energy_ml/'+n for n in ['fit.json','worker.time']}
    allowed|={f'ml/artifacts/stage71/{seed}.ubj' for seed in p['seeds']}|{'ml/artifacts/stage71/predictions.npz'}
    assert not ART.exists()
    with tarfile.open(CACHE/'results.tar.gz') as tar:
        for item in tar.getmembers():
            if item.isdir():continue
            assert item.isfile()
            if item.name=='workbook/stage71_energy_ml/protocol.json':
                assert tar.extractfile(item).read()==protocol.read_bytes();continue
            assert item.name in allowed,item.name
            path=REPO/item.name;assert not path.exists();path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(tar.extractfile(item).read())
    assert all((REPO/n).exists() for n in allowed)
    save(OUT/'condor_resources.json',dict(cluster=args.cluster,starts=1,exitcode=0,request_CPUs=1,request_memory_MB=3000,
        remote_CPU_s=ad['RemoteUserCpu']+ad['RemoteSysCpu'],remote_wall_s=ad['RemoteWallClockTime'],
        requested_MaxRuntime_s=900,scheduled_MaxRuntime_s=ad['MaxRuntime'],
        MaxRuntime_request_preserved=ad['MaxRuntime']==900,
        resource_deviation='dry-run900s -> schedd3600s with microcentury; worker timeout880s and callback850s remain frozen, actual job under900s' if ad['MaxRuntime']!=900 else 'none',
        history_last_RSS_MiB=ad.get('ResidentSetSize',0)/1024,history_RSS_scope='final scheduler sample, not an exact peak',
        received_bytes=ad.get('BytesRecvd'),sent_bytes=ad.get('BytesSent'),
        transport_bytes=(CACHE/'results.tar.gz').stat().st_size,physical_EOS_network_bytes='未测量',
        resources_scope='formal job only; local preparation/report/validation separately timed'))
    print('one job successful;3fixed models and predictions collected',ad['RemoteWallClockTime'])


if __name__=='__main__':main()
