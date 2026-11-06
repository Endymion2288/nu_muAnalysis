"""Collect actual Condor exit codes, resource events, and GNU time records."""
import json
import re
import tarfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'workbook/stage126_energy_ml'


def main():
    cluster=int(json.loads((OUT/'submission.json').read_text())['result'].split('.')[0])
    spool=Path.home()/'condor/nu_muAnalysis/stage126'
    log=(spool/f'logs/{cluster}.log').read_text()
    completed=[]
    for chunk in log.split('...'):
        match=re.search(rf'005 \({cluster}\.(\d+)\.000\).*?Normal termination \(return value (\d+)\)',chunk,re.S)
        if not match:
            continue
        def get(pattern):
            return int(re.search(pattern,chunk)[1])
        completed.append(dict(proc=int(match[1]),exit_code=int(match[2]),
            execute_s=get(r'TimeExecute \(s\)\s*:\s*(\d+)'),
            memory_usage_MB=get(r'Memory \(MB\)\s*:\s*(\d+)'),
            disk_usage_KB=get(r'Disk \(KB\)\s*:\s*(\d+)'),record=chunk.strip()))
    assert len(completed)==16 and all(c['exit_code']==0 for c in completed)
    times=[]
    for batch in range(16):
        path=ROOT/f'ntuples/energy_ml_stage126/batch_{batch}.tar.gz'
        if path.exists():
            with tarfile.open(path) as archive:
                text=archive.extractfile(f'workbook/stage126_energy_ml/batch_{batch}.time').read().decode()
        else:
            text=(OUT/f'batch_{batch}.time').read_text()
        (OUT/f'batch_{batch}.time').write_text(text)
        user=float(re.search(r'User time \(seconds\): ([\d.]+)',text)[1])
        system=float(re.search(r'System time \(seconds\): ([\d.]+)',text)[1])
        elapsed=re.search(r'Elapsed .*: ([\d:.]+)',text)[1].split(':')
        wall=sum(float(x)*60**i for i,x in enumerate(elapsed[::-1]))
        times.append(dict(batch=batch,user_CPU_s=user,system_CPU_s=system,wall_s=wall,
            max_process_RSS_KiB=int(re.search(r'Maximum resident set size \(kbytes\): (\d+)',text)[1])))
    user=sum(r['user_CPU_s'] for r in times);system=sum(r['system_CPU_s'] for r in times)
    wall=sum(r['wall_s'] for r in times)
    result=dict(cluster=cluster,completed_jobs=16,cores_per_job=4,worker_processes_per_job=4,
        inner_threads=1,GPU_used=False,user_CPU_s=user,system_CPU_s=system,total_CPU_s=user+system,
        sum_job_analysis_wall_s=wall,aggregate_CPU_utilization_relative_to_allocated_4cores=(user+system)/(4*wall),
        sum_Condor_execute_s=sum(c['execute_s'] for c in completed),
        max_Condor_memory_MB=max(c['memory_usage_MB'] for c in completed),jobs=times,condor_events=completed)
    (OUT/'resources.json').write_text(json.dumps(result,indent=2)+'\n')
    print({k:v for k,v in result.items() if k not in ['jobs','condor_events']})


if __name__=='__main__':
    main()
