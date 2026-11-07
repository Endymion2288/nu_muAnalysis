"""Stdlib scheduler ledger: unique job attempts, including failures and retries."""
import csv
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage129_energy_ml';SPOOL=Path('/afs/cern.ch/user/x/xcheng/condor/nu_muAnalysis/stage129')


def seconds(value):
    day,h,m,s=map(int,value.split());return day*86400+h*3600+m*60+s


def main():
    jobs={}
    for p in sorted(OUT.glob('submission_*.json')):
        a=json.loads(p.read_text());cluster=int(re.match(r'\d+',a['result'])[0])
        for proc,index in enumerate(a['package']['indices']):
            key=(cluster,proc)
            if key in jobs:continue
            path=SPOOL/'logs'/f'{cluster}.{proc}.log';text=path.read_text() if path.exists() else ''
            starts=len(re.findall(r'^001 \(',text,re.M));terminal='005 (' in text or '009 (' in text
            codes=re.findall(r'Normal termination \(return value (\d+)\)',text)
            pairs=re.findall(r'Usr (\d+) (\d+):(\d+):(\d+), Sys (\d+) (\d+):(\d+):(\d+)\s+-\s+Total Remote Usage',text)
            cpu=sum(seconds(' '.join(v[:4]))+seconds(' '.join(v[4:])) for v in pairs)
            execute=re.findall(r'TimeExecute \(s\)\s*:\s*(\d+)',text)
            removed='009 (' in text
            history=OUT/f'job_history_{cluster}_{proc}.json'
            if history.exists():
                h=json.loads(history.read_text());cpu=h['RemoteUserCpu']+h['RemoteSysCpu'];execute=[str(h['RemoteWallClockTime'])]
            requests={k:int(v) for k,v in re.findall(r'^\s*(Cpus|Memory|GPUs) = (\d+)',text,re.M)}
            jobs[key]=dict(cluster=cluster,proc=proc,phase=a['phase'],index=index,starts=starts,terminal=terminal,removed=removed,exit_code=int(codes[-1]) if codes else None,scheduler_CPU_s=cpu,execute_wall_s=sum(map(float,execute)),allocated_CPUs=requests.get('Cpus'),allocated_memory_MB=requests.get('Memory'),allocated_GPUs=requests.get('GPUs'),input_package=a['package']['path'],input_package_bytes=a['package']['bytes'])
    rows=list(jobs.values())
    with (OUT/'resource_jobs.tsv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n');w.writeheader();w.writerows(rows)
    summary=dict(unique_submitted=len(rows),starts=sum(r['starts'] for r in rows),terminal=sum(r['terminal'] for r in rows),removed=sum(r['removed'] for r in rows),failed=sum(r['terminal'] and r['exit_code'] not in [0,None] for r in rows),scheduler_CPU_s=sum(r['scheduler_CPU_s'] for r in rows),aggregate_execute_wall_s=sum(r['execute_wall_s'] for r in rows),allocated_GPU_jobs=sum(bool(r['allocated_GPUs']) for r in rows),scope='unique scheduler attempts including pilot failures/retries. CPU integral seconds; GNU and child timing are nested crosschecks, never added to schedulerCPU. Running attempts not final; role resources can be site rounded')
    (OUT/'resource_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(summary)


if __name__=='__main__':main()
