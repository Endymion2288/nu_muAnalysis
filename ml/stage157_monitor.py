"""Query submitted IDs together; reuse terminal accounting to avoid repeated history IO."""
import json
import subprocess
from pathlib import Path
from stage143_monitor import ATTR as BASE_ATTR
ATTR = BASE_ATTR+["MemoryUsage","RequestMemory","CpusUsage","ProportionalSetSizeKb"]

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage157_energy_ml'
submissions=list(OUT.glob('*_submission.json'))
ids={int(json.loads(p.read_text())['result'].split('.')[0]) for p in submissions}
old=json.loads((OUT/'scheduler_accounting.json').read_text()) if (OUT/'scheduler_accounting.json').exists() else {}
terminal={r['ClusterId']:r for r in old.get('jobs',[]) if r['JobStatus'] in [3,4]}
query=sorted(ids-set(terminal));live=[];missing=[]
if query:
    text=subprocess.check_output(['condor_q']+[str(i) for i in query]+['-json','-attributes',','.join(ATTR)],text=True).strip()
    rows=json.loads(text) if text else [];live=rows
    absent=set(query)-{r['ClusterId'] for r in rows}
    if absent:
        constraint=' || '.join(f'ClusterId == {i}' for i in sorted(absent))
        text=subprocess.check_output(['condor_history','-constraint',constraint,'-limit',str(len(absent)),
            '-since','CompletionDate < 1794084000','-json','-attributes',','.join(ATTR)],text=True).strip()
        for r in json.loads(text) if text else []:terminal[r['ClusterId']]=r
        missing=sorted(absent-set(terminal))
rows=list(terminal.values())+live
report=dict(jobs=rows,total_CPU_s=sum(r.get('RemoteUserCpu',0)+r.get('RemoteSysCpu',0) for r in rows),
    total_execute_wall_s=sum(r.get('RemoteWallClockTime',0) for r in rows),starts=sum(r.get('NumJobStarts',0) for r in rows),
    live_N=len(live),completed_N=sum(r['JobStatus']==4 for r in rows),unresolved_ids=missing,CPU_budget_s=60000)
(OUT/'scheduler_accounting.json').write_text(json.dumps(report,indent=2)+'\n')
print({k:v for k,v in report.items() if k!='jobs'},flush=True)
if report['total_CPU_s']>=60000 and live:
    subprocess.run(['condor_rm']+[str(r['ClusterId'])+'.'+str(r['ProcId']) for r in live],check=True)
    raise RuntimeError('Frozen cumulative CPU exhausted')
