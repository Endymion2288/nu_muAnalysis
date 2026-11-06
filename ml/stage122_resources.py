"""Compact scheduler/GNU cost ledger, including failures and idle cancellations."""
import csv
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage122_energy_ml'
SPOOL=Path('/afs/cern.ch/user/x/xcheng/condor/nu_muAnalysis/stage122')


def main():
    jobs=[]
    for path in sorted((SPOOL/'logs').glob('*.log')):
        text=path.read_text();starts=len(re.findall(r'001 \(',text));ended='005 (' in text;removed='009 (' in text
        times=re.findall(r'Usr (\d+) (\d+):(\d+):(\d+), Sys (\d+) (\d+):(\d+):(\d+)  -  Total Remote Usage',text)
        cpu=None
        if times:
            t=list(map(int,times[-1]));cpu=sum(t[i]*86400+t[i+1]*3600+t[i+2]*60+t[i+3] for i in [0,4])
        exits=re.findall(r'Normal termination \(return value (\d+)\)',text);wall=re.findall(r'TimeExecute \(s\)\s*:\s*(\d+)',text)
        rows=[]
        for key in ['Cpus','Memory (MB)','GPUs']:
            match=re.findall(re.escape(key)+r'\s*:\s*([^\n]*)',text)
            rows.append(match[-1].strip() if match else None)
        jobs.append(dict(job=path.stem,starts=starts,state='terminated' if ended else 'removed' if removed else 'pending_or_running',exitcode=int(exits[-1]) if exits else None,CPU_s_scheduler_rounded=cpu,execute_wall_s=int(wall[-1]) if wall else None,cpus_usage_request_allocated=rows[0],memory_MB_usage_request_allocated=rows[1],gpu_usage_request_allocated=rows[2]))
    with (OUT/'resource_jobs.tsv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=jobs[0].keys(),delimiter='\t');w.writeheader();w.writerows(jobs)
    # These GNU logs are nested in scheduler job usage; never add them to it.
    records=[]
    paths=list(OUT.rglob('*_time.txt'))+list((ROOT/'ntuples/energy_ml_stage122').glob('candidates_*/*_time.txt'))
    for path in paths:
        t=path.read_text();v=dict(path=str(path.relative_to(ROOT)))
        for label,name in [('User time (seconds)','user_CPU_s'),('System time (seconds)','system_CPU_s'),('Maximum resident set size (kbytes)','max_RSS_KiB'),('Exit status','exitcode')]:
            m=re.search(re.escape(label)+r':\s*(\S+)',t)
            if m:v[name]=float(m[1])
        m=re.search(r'Elapsed \(wall clock\) time \(h:mm:ss or m:ss\):\s*(\S+)',t)
        if m:v['wall_s']=sum(float(x)*60**j for j,x in enumerate(m[1].split(':')[::-1]))
        records.append(v)
    fields=list(dict.fromkeys(k for r in records for k in r))
    with (OUT/'resource_GNU.tsv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=fields,delimiter='\t');w.writeheader();w.writerows(records)
    report=dict(jobs=len(jobs),starts=sum(r['starts'] for r in jobs),terminated=sum(r['state']=='terminated' for r in jobs),idle_removed=sum(r['state']=='removed' and r['starts']==0 for r in jobs),failed_terminated=sum(r['state']=='terminated' and r['exitcode']!=0 for r in jobs),pending=sum(r['state']=='pending_or_running' for r in jobs),CPU_s_scheduler_rounded=sum(r['CPU_s_scheduler_rounded'] or 0 for r in jobs),aggregate_execute_wall_s=sum(r['execute_wall_s'] or 0 for r in jobs),GNU_log_N=len(records),largest_GNU_process_RSS_KiB=max((r.get('max_RSS_KiB',0) for r in records),default=0),GPU_jobs=0,caveats=['scheduler CPU rounded to integer seconds; all starts/failures included','execute wall summed across parallel jobs is not session elapsed','GNU subprocess timings overlap scheduler job totals; not additive','GNU maxRSS is not concurrent process-tree aggregate peak','physical network traffic, speedup against single-core and GPU speedup not measured'])
    (OUT/'resource_summary.json').write_text(json.dumps(report,indent=2)+'\n');print(report)


if __name__=='__main__':main()
