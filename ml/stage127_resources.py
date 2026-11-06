"""Compact actual Condor and GNU-time audit for both stage127 phases."""
import json
import re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage127_energy_ml'


def timing(path):
    text=path.read_text()
    get=lambda pattern:float(re.search(pattern,text)[1])
    elapsed=re.search(r'Elapsed .*: ([\d:.]+)',text)[1].split(':')
    return dict(user_CPU_s=get(r'User time \(seconds\): ([\d.]+)'),system_CPU_s=get(r'System time \(seconds\): ([\d.]+)'),
                wall_s=sum(float(v)*60**i for i,v in enumerate(elapsed[::-1])),max_process_RSS_KiB=int(get(r'Maximum resident set size \(kbytes\): (\d+)')))


def main():
    phases={}
    for phase,count,cores in [('coordinates',8,4),('scan',1,8)]:
        submission=json.loads((OUT/f'submission_{phase}.json').read_text());cluster=int(submission['result'].split('.')[0])
        log=(Path.home()/f'condor/nu_muAnalysis/stage127/logs/{cluster}.log').read_text();jobs=[]
        for chunk in log.split('...'):
            match=re.search(rf'005 \({cluster}\.(\d+)\.000\).*?Normal termination \(return value (\d+)\)',chunk,re.S)
            if match:
                get=lambda pattern:int(re.search(pattern,chunk)[1])
                jobs.append(dict(proc=int(match[1]),exit_code=int(match[2]),execute_s=get(r'TimeExecute \(s\)\s*:\s*(\d+)'),
                    memory_MB=get(r'Memory \(MB\)\s*:\s*(\d+)'),disk_KB=get(r'Disk \(KB\)\s*:\s*(\d+)'),record=chunk.strip()))
        assert len(jobs)==count and all(j['exit_code']==0 for j in jobs)
        times=[timing(OUT/f'coordinates_{i}.time') for i in range(8)] if phase=='coordinates' else [timing(OUT/'scan.time')]
        cpu=sum(t['user_CPU_s']+t['system_CPU_s'] for t in times);wall=sum(t['wall_s'] for t in times)
        phases[phase]=dict(cluster=cluster,jobs=count,cores_per_job=cores,CPU_s=cpu,sum_analysis_wall_s=wall,
              allocated_core_utilization=cpu/(cores*wall),max_Condor_memory_MB=max(j['memory_MB'] for j in jobs),times=times,events=jobs)
    out=dict(phases=phases,new_fits=0,new_model_forwards=0,GPU_used=False,
             total_CPU_s=sum(p['CPU_s'] for p in phases.values()),uproot_requested_bytes=json.loads((OUT/'coordinate_validation.json').read_text())['requested_uproot_bytes'])
    (OUT/'resources.json').write_text(json.dumps(out,indent=2)+'\n');print({k:{a:b for a,b in v.items() if a not in ['times','events']} for k,v in phases.items()})


if __name__=='__main__':main()
