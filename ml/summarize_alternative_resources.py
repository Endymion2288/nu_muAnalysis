#!/usr/bin/env python3
"""Final stage70 Condor and measured subprocess resources, no data event reads."""
import ast
import json
import re
import subprocess
from pathlib import Path

from collect_alternative_support import REPO, OUT, CACHE, write_table


def timing(path):
    return {name:float(value) for name,value in re.findall(r'(wall_s|user_s|system_s|maxRSS_KiB)=([\d.]+)',path.read_text())}


def main():
    spool = Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage70')
    eventlog = spool/'logs/support.9662832.log'
    active=json.loads(subprocess.check_output(['condor_q','9662832','-json'],text=True).strip() or '[]')
    assert not active, 'wait for both jobs to leave the queue; never publish running jobs as failures'
    userlog_history = json.loads(subprocess.check_output(['condor_history','-userlog',str(eventlog),'-json'],text=True))
    attributes=['ClusterId','ProcId','JobStatus','ExitCode','NumJobStarts','RemoteUserCpu','RemoteSysCpu','RemoteWallClockTime',
                'JobStartDate','CompletionDate','EnteredCurrentStatus','RemoveReason','HoldReason','RequestCpus','RequestMemory','RequestDisk',
                'MemoryUsage','ResidentSetSize','BytesSent','BytesRecvd','MaxRuntime']
    history = json.loads(subprocess.check_output(['condor_history','9662832','-match','2','-json','-attributes',','.join(attributes)],text=True))
    assert len(history)==2 and all(r['JobStatus'] in [3,4] and r['NumJobStarts']==1 for r in history)
    (OUT/'condor_history.json').write_text(json.dumps(history,indent=2)+'\n')
    (OUT/'condor_userlog_history.json').write_text(json.dumps(userlog_history,indent=2)+'\n')
    (OUT/'condor_events.log').write_text('\n'.join(line.rstrip() for line in eventlog.read_text().splitlines())+'\n')
    rows, diagnostics = [], []
    for index,component in enumerate(['pi','k']):
        ad = next(r for r in history if r['ProcId']==index)
        if ad['JobStatus']!=4 or ad.get('ExitCode')!=0:
            assert not (CACHE/str(index)/'selected.npz').exists(), 'inspect partial artifact before accepting failure'
            continue
        for step in ['copy','reco','ntuple','extract']:
            t=timing(CACHE/str(index)/(step+'.time'))
            rows.append(dict(component=component,step=step,**t,CPU_s=t['user_s']+t['system_s']))
        text=(CACHE/str(index)/'production_validation.txt').read_text()
        first=text.splitlines()[0]
        values=ast.literal_eval(first[first.index('{'):])
        for line in text.splitlines():
            if not line.startswith('log='):continue
            level_match=re.search(r'levels=(\{.*?\})',line)
            fpe_match=re.search(r'FPE_totals=(\{.*?\})',line)
            levels=ast.literal_eval(level_match[1]);fpe=ast.literal_eval(fpe_match[1])
            diagnostics.append(dict(component=component,step='reco' if line.startswith('log=reco') else 'ntuple',
                                    WARNING=levels.get('WARNING',0),ERROR=levels.get('ERROR',0),FATAL=levels.get('FATAL',0),
                                    **{k:fpe.get(k,0) for k in ['OVERFLOW','INVALID','DIVBYZERO']},**values))
    write_table(OUT/'subprocess_resources.tsv',rows)
    write_table(OUT/'production_diagnostics.tsv',diagnostics)
    record=dict(cluster=9662832,jobs=[dict(proc=r['ProcId'],starts=r['NumJobStarts'],exitcode=r.get('ExitCode'),status=r['JobStatus'],
                success=r['JobStatus']==4 and r.get('ExitCode')==0,remove_reason=r.get('RemoveReason'),
                remote_CPU_s=r['RemoteUserCpu']+r['RemoteSysCpu'],remote_wall_s=r['RemoteWallClockTime']) for r in history],
                total_remote_CPU_s=sum(r['RemoteUserCpu']+r['RemoteSysCpu'] for r in history),
                sum_remote_wall_s=sum(r['RemoteWallClockTime'] for r in history),
                measured_pipeline_CPU_s=sum(r['CPU_s'] for r in rows),
                sum_pipeline_wall_s=sum(r['wall_s'] for r in rows),
                pipeline_peak_RSS_MiB=max(r['maxRSS_KiB'] for r in rows)/1024,
                per_job_requests=dict(CPU=1,memory_MB=3000,disk_MB=5500,MaxRuntime_s=3600,max_retries=0),
                total_CPU_budget_s=7200,input_RDO_logical_copy_bytes=42220266+1293229936,
                physical_EOS_network_read_write_bytes='未测量; logical copy size, uproot requests and Condor transport are separate counters',
                local_QA=dict(reco_CPU_s=sum(timing(Path('/tmp/nu_mu_stage70_qa')/c/'reco.time')[k] for c in ['pi','k'] for k in ['user_s','system_s']),
                              ntuple_CPU_s=sum(timing(Path('/tmp/nu_mu_stage70_qa')/c/'ntuple.time')[k] for c in ['pi','k'] for k in ['user_s','system_s']),
                              successful_native_CPU_s=sum(timing(Path('/tmp/nu_mu_stage70_qa')/('native_'+c+'.time'))[k] for c in ['pi','k'] for k in ['user_s','system_s']),
                              retry_accounting='reader_retry.json: attempt2 CPU31.62s; attempt1/failed first-event reader CPU未测量; do not call remote CPU the complete stage cost'))
    record['pipeline_timing_scope']='completed returned sources only; failed source has scheduler resources and runtime_observation.json, no invented pipeline timing'
    observation=json.loads((OUT/'runtime_observation.json').read_text())
    sampled_rss=[r.get('ResidentSetSize',0) or 0 for r in history]+[r.get('ResidentSetSize',0) or 0 for r in observation['observations']]
    record['scheduler_observed_max_RSS_MiB']=max(sampled_rss)/1024
    record['scheduler_RSS_scope']='maximum of recorded scheduler samples; not a continuous or exact failed-pipeline peak'
    record['scheduler_wall_scope']='schedd history RemoteWallClockTime; userlog execute intervals are separately preserved and may differ (pi151 versus148s)'
    record['requests_verified']=all(r['RequestCpus']==1 and r['RequestMemory']==3000 and r['MaxRuntime']==3600 for r in history)
    assert record['requests_verified'] and record['scheduler_observed_max_RSS_MiB']<3000
    assert record['total_remote_CPU_s']<=7200
    assert record['pipeline_peak_RSS_MiB']<=3000
    (OUT/'condor_resources.json').write_text(json.dumps(record,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(record,indent=2,ensure_ascii=False))


if __name__=='__main__':
    main()
