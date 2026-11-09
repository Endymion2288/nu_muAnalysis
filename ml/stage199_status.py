"""Bounded scheduler queries and compact per-start accounting, including failures."""
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage199_energy_ml'
fields=['ClusterId','ProcId','JobStatus','ExitCode','ExitBySignal','NumJobStarts','RemoteUserCpu','RemoteSysCpu',
        'RemoteWallClockTime','RequestCpus','RequestMemory','MemoryUsage','QDate','CompletionDate','JobStartDate','HoldReason','RemoveReason']
adjustment=OUT/'execution_adjustment.json'
cancelled=set(json.loads(adjustment.read_text())['cancelled_unstarted_condor']) if adjustment.exists() else set()
jobs=[];unknown=[]
for path in OUT.glob('*_submission.json'):
    d=json.loads(path.read_text())
    if d.get('platform')=='kubeflow':continue
    cluster=int(d['result'].split('.')[0]);expected=len(d.get('batches',[[]]))
    live=json.loads(subprocess.check_output(['condor_q',str(cluster),'-json','-attributes',','.join(fields)],text=True).strip() or '[]')
    # Use the submission descriptor mtime only as a historical query bound,
    # never as evidence of whether a job is live or terminal.
    since=int(path.stat().st_mtime)-600
    history=json.loads(subprocess.check_output(['condor_history','-constraint',f'ClusterId == {cluster}',
        '-since',f'CompletionDate < {since}','-limit',str(expected),'-json','-attributes',','.join(fields)],text=True).strip() or '[]')
    byid={int(r['ProcId']):dict(r,phase=d['phase']) for r in history}
    for r in live:byid[int(r['ProcId'])]=dict(r,phase=d['phase'])
    jobs.extend(byid.values())
    if len(byid)<expected:unknown.append(dict(cluster=cluster,expected=expected,observed=len(byid),
        state='not materialized or not yet observable; do not restart from this count'))
def intentional_unstarted(r):
    return f"{r['ClusterId']}.{r['ProcId']}" in cancelled and r['JobStatus']==3 and r.get('NumJobStarts')==0
result=dict(jobs=jobs,unmaterialized_or_unobserved=unknown,
    live_N=sum(r['JobStatus'] not in [3,4] for r in jobs),terminal_N=sum(r['JobStatus'] in [3,4] for r in jobs),
    starts=sum(r.get('NumJobStarts',0) for r in jobs),
    scheduler_CPU_s=sum(r.get('RemoteUserCpu',0)+r.get('RemoteSysCpu',0) for r in jobs),
    aggregate_execute_wall_s=sum(r.get('RemoteWallClockTime',0) for r in jobs),
    intentionally_cancelled_unstarted=[f"{r['ClusterId']}.{r['ProcId']}" for r in jobs if intentional_unstarted(r)],
    failed=[dict(cluster=r['ClusterId'],proc=r['ProcId'],exit=r.get('ExitCode')) for r in jobs
            if r['JobStatus'] in [3,4] and r.get('ExitCode')!=0 and not intentional_unstarted(r)])
(OUT/'scheduler_accounting.json').write_text(json.dumps(result,indent=2)+'\n')
print({k:v for k,v in result.items() if k!='jobs'})
