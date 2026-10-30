#!/usr/bin/env python3
"""Collect measured GPU Condor resources; fail on incomplete/failed jobs."""
import argparse
import json
import re
from datetime import datetime
from pathlib import Path

from train_bdt import write_table


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--cluster',type=int,required=True);p.add_argument('--log-dir',type=Path)
    args=p.parse_args();logs=args.log_dir or args.repo/'logs';out=args.repo/'workbook/stage16_energy_ml'
    log=(logs/f'ml_tabular_{args.cluster}.log').read_text();events={i:{} for i in range(8)}
    for block in log.split('...'):
        m=re.search(r'(\d{3}) \(\d+\.(\d+)\.000\) (\d\d/\d\d \d\d:\d\d:\d\d)',block)
        if m:
            code,proc,stamp=m.groups()
            if code in ['000','001','005']:events[int(proc)][code]=(datetime.strptime('2026/'+stamp,'%Y/%m/%d %H:%M:%S'),block)
    rows=[]
    for i,e in events.items():
        if not all(c in e for c in ['000','001','005']):raise RuntimeError(f'Incomplete job {args.cluster}.{i}')
        code=int(re.search(r'return value (\d+)',e['005'][1]).group(1))
        if code:raise RuntimeError(f'Job {i} exit {code}')
        stderr=(logs/f'ml_tabular_{args.cluster}.{i}.err').read_text()
        m=re.search(r'wall_s=([\d.]+) max_rss_KiB=(\d+) user_s=([\d.]+) system_s=([\d.]+)',stderr)
        if m is None:raise RuntimeError(f'Missing timing for job {i}')
        wall,rss,user,sys=map(float,m.groups());done=e['005'][1]
        gpu_memory=re.search(r'GpusMemory \(MB\)\s*:\s*([\d.]+)',done)
        cpu=re.findall(r'(?:Usr|Sys) (\d+) (\d+):(\d+):(\d+)',done)[:2]
        rows.append(dict(cluster=args.cluster,proc=i,exit_code=code,requested_cpus=1,requested_gpus=1,requested_memory_MB=3000,
                         allocated_memory_MB=int(re.search(r'Memory = (\d+)',e['001'][1]).group(1)),
                         submitted_local=e['000'][0].isoformat(),executed_local=e['001'][0].isoformat(),terminated_local=e['005'][0].isoformat(),
                         submit_to_finish_s=(e['005'][0]-e['000'][0]).total_seconds(),
                         condor_execute_s=int(re.search(r'TimeExecute \(s\)\s*:\s*(\d+)',done).group(1)),
                         condor_observed_gpu_memory_MB=float(gpu_memory.group(1)) if gpu_memory else 'unmeasured',
                         remote_cpu_s=sum(int(d)*86400+int(h)*3600+int(m)*60+int(s) for d,h,m,s in cpu),
                         wrapper_wall_s=wall,wrapper_peak_rss_KiB=int(rss),wrapper_user_s=user,wrapper_system_s=sys))
    write_table(out/'condor_resources.tsv',rows)
    summary=dict(cluster=args.cluster,jobs=8,all_exit_zero=True,submit_to_last_finish_s=max(r['submit_to_finish_s'] for r in rows),
                 condor_gpu_allocation_s=sum(r['condor_execute_s'] for r in rows),
                 remote_cpu_s=sum(r['remote_cpu_s'] for r in rows),wrapper_wall_s=sum(r['wrapper_wall_s'] for r in rows),
                 wrapper_cpu_s=sum(r['wrapper_user_s']+r['wrapper_system_s'] for r in rows),
                 wrapper_peak_rss_KiB=max(r['wrapper_peak_rss_KiB'] for r in rows))
    (out/'condor_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
