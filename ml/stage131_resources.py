"""Exact submitted-attempt scheduler ledger, including every engineering failure."""
import json
import re
import subprocess
from stage131_common import OUT,table
ATTRS=['ClusterId','ProcId','JobStatus','NumJobStarts','ExitCode','ExitBySignal','ExitSignal','RemoteUserCpu','RemoteSysCpu','RemoteWallClockTime','RequestCpus','RequestMemory','RequestGpus','JobStartDate','CompletionDate','EnteredCurrentStatus','HoldReason']

def main():
    submitted={}
    for path in sorted(OUT.glob('*_submission_[0-9]*.json')):
        r=json.loads(path.read_text());cluster=int(re.match(r'\d+',r['result'])[0])
        for proc,index in enumerate(r['indices']):submitted[cluster,proc]=dict(cluster=cluster,proc=proc,phase=r['phase'],task_index=index)
    clusters=sorted({k[0] for k in submitted});constraint=' || '.join(f'ClusterId == {i}' for i in clusters);measured={}
    for command in ['condor_history','condor_q']:
        args=['-since','CompletionDate < 1794063000'] if command=='condor_history' else []
        payload=subprocess.check_output([command,*args,'-constraint',constraint,'-json','-attributes',','.join(ATTRS)],text=True,timeout=60)
        for r in json.loads(payload.strip() or '[]'):measured[r['ClusterId'],r['ProcId']]=r
    rows=[];events={}
    for key,record in sorted(submitted.items()):
        r=measured.get(key,{});status=r.get('JobStatus');terminal=status in [3,4];start=r.get('JobStartDate',0);end=r.get('CompletionDate',0) or (r.get('EnteredCurrentStatus',0) if terminal else 0);cores=r.get('RequestCpus',0);wall=r.get('RemoteWallClockTime',0)
        rows.append(dict(**record,observed=bool(r),status=status,terminal=terminal,starts=r.get('NumJobStarts',0),exit_code=r.get('ExitCode'),exit_by_signal=r.get('ExitBySignal'),exit_signal=r.get('ExitSignal'),scheduler_CPU_s=r.get('RemoteUserCpu',0)+r.get('RemoteSysCpu',0),execute_wall_s=wall,requested_CPUs=cores,requested_memory_MB=r.get('RequestMemory'),requested_GPUs=r.get('RequestGpus',0),start_epoch=start,end_epoch=end,hold_reason=r.get('HoldReason','')))
        if start and not (terminal and not r.get('NumJobStarts',0) and not wall):
            for stamp,sign in [(start,1)]+([(end,-1)] if end else []):
                a,b=events.get(stamp,(0,0));events[stamp]=a+sign,b+sign*cores
    active=core=peak=peakcore=0
    for _,(a,b) in sorted(events.items()):active+=a;core+=b;peak=max(peak,active);peakcore=max(peakcore,core)
    table('resource_jobs.tsv',rows)
    summary=dict(unique_submitted=len(rows),observed=sum(r['observed'] for r in rows),terminal=sum(r['terminal'] for r in rows),starts=sum(r['starts'] for r in rows),failed=sum(r['terminal'] and (r['exit_code'] not in [0,None] or bool(r['exit_by_signal'])) for r in rows),scheduler_CPU_s=sum(r['scheduler_CPU_s'] for r in rows),aggregate_execute_wall_s=sum(r['execute_wall_s'] for r in rows),allocated_execute_core_s=sum(r['execute_wall_s']*r['requested_CPUs'] for r in rows),peak_jobs=peak,peak_requested_CPUs=peakcore,GPU_jobs=sum(bool(r['requested_GPUs']) for r in rows),scope='cumulative scheduler user+system per uniqueattempt,includes allfailed/terminated; nested GNU times never added; live usage may lag; peak requestedcores at secondresolution,not measured hardwareutilization')
    (OUT/'resource_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(summary)

if __name__=='__main__':main()
