"""Bounded scheduler accounting and total CPU budget enforcement; stdlib only."""
import json
import subprocess
from pathlib import Path

OUT=Path(__file__).resolve().parents[1]/'workbook/stage140_energy_ml'
ATTR=['ClusterId','ProcId','JobStatus','ExitCode','ExitBySignal','RemoteUserCpu',
      'RemoteSysCpu','RemoteWallClockTime','NumJobStarts','ResidentSetSize',
      'RequestCpus','JobStartDate','CompletionDate','HoldReason']

def main():
    clusters=sorted({int(json.loads(p.read_text())['result'].split('.')[0])
                     for p in OUT.glob('*_submission.json')})
    jobs={};live=[]
    for cluster in clusters:
        for cmd in [['condor_q',str(cluster),'-json','-attributes',','.join(ATTR)],
                    ['condor_history','-since','CompletionDate < 1794077000',
                     '-constraint',f'ClusterId == {cluster}','-limit','600','-json','-attributes',','.join(ATTR)]]:
            payload=subprocess.check_output(cmd,text=True).strip()
            result=json.loads(payload) if payload else []
            for row in result:jobs[row['ClusterId'],row['ProcId']]=row
            if cmd[0]=='condor_q':live.extend(result)
    rows=list(jobs.values());cpu=sum(r.get('RemoteUserCpu',0)+r.get('RemoteSysCpu',0) for r in rows)
    budget=json.loads((OUT/'protocol.json').read_text())['resources']['CPU_budget_s']
    result=dict(jobs=rows,total_CPU_s=cpu,total_execute_wall_s=sum(r.get('RemoteWallClockTime',0) for r in rows),
                starts=sum(r.get('NumJobStarts',0) for r in rows),live_N=len(live),
                completed_N=sum(r['JobStatus']==4 for r in rows),CPU_budget_s=budget)
    (OUT/'scheduler_accounting.json').write_text(json.dumps(result,indent=2)+'\n')
    if cpu>=budget:
        for row in live:subprocess.run(['condor_rm',f"{row['ClusterId']}.{row['ProcId']}"],check=True)
        raise RuntimeError('Frozen cumulative CPU budget reached; inspect before any further work')
    print({k:v for k,v in result.items() if k!='jobs'})

if __name__=='__main__':main()
