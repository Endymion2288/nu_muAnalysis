#!/usr/bin/env python3
"""Collect successful extraction/training Condor jobs and measured resources."""
import argparse
import json
import re
from datetime import datetime
from pathlib import Path

from train_bdt import write_table


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--extraction-cluster',type=int,required=True)
    p.add_argument('--training-cluster',type=int,required=True);p.add_argument('--log-dir',type=Path)
    args=p.parse_args();repo=Path(__file__).resolve().parents[1];logs=args.log_dir or repo/'logs';rows=[]
    for name,cluster,n,gpu,memory in [('spatial_extract',args.extraction_cluster,19,0,1500),('spatial_train',args.training_cluster,3,1,3000)]:
        events={i:{} for i in range(n)}
        for block in (logs/f'ml_{name}_{cluster}.log').read_text().split('...'):
            m=re.search(r'(\d{3}) \(\d+\.(\d+)\.000\) (\d\d/\d\d \d\d:\d\d:\d\d)',block)
            if m and m[1] in ['000','001','005']:
                events[int(m[2])][m[1]]=(datetime.strptime('2026/'+m[3],'%Y/%m/%d %H:%M:%S'),block)
        for i,e in events.items():
            if not all(k in e for k in ['000','001','005']):raise RuntimeError(f'Unfinished {cluster}.{i}')
            done=e['005'][1];code=int(re.search(r'return value (\d+)',done)[1])
            if code:raise RuntimeError(f'Failed {cluster}.{i}: {code}')
            stderr=(logs/f'ml_{name}_{cluster}.{i}.err').read_text()
            m=re.search(r'wall_s=([\d.]+) max_rss_KiB=(\d+) user_s=([\d.]+) system_s=([\d.]+)',stderr)
            if m is None:raise RuntimeError(f'No timing {cluster}.{i}')
            wall,rss,user,system=map(float,m.groups())
            cpus=re.findall(r'(?:Usr|Sys) (\d+) (\d+):(\d+):(\d+)',done)[:2]
            gpu_memory=re.search(r'GpusMemory \(MB\)\s*:\s*([\d.]+)',done)
            rows.append(dict(study=name,cluster=cluster,proc=i,exit_code=code,submitted_local=e['000'][0].isoformat(),executed_local=e['001'][0].isoformat(),
                             terminated_local=e['005'][0].isoformat(),submit_to_finish_s=(e['005'][0]-e['000'][0]).total_seconds(),
                             condor_execute_s=int(re.search(r'TimeExecute \(s\)\s*:\s*(\d+)',done)[1]),
                             remote_cpu_s=sum(int(d)*86400+int(h)*3600+int(m)*60+int(s) for d,h,m,s in cpus),
                             wrapper_wall_s=wall,wrapper_cpu_s=user+system,wrapper_peak_rss_KiB=int(rss),requested_cpus=1,requested_gpus=gpu,
                             submit_memory_MB=memory,allocated_memory_MB=int(re.search(r'Memory = (\d+)',e['001'][1])[1]),
                             observed_gpu_memory_MB=float(gpu_memory[1]) if gpu_memory else 'unmeasured'))
    out=repo/'workbook/stage18_energy_ml';write_table(out/'condor_resources.tsv',rows);summary={}
    for study in ['spatial_extract','spatial_train']:
        selected=[r for r in rows if r['study']==study]
        summary[study]=dict(jobs=len(selected),all_exit_zero=True,submit_to_last_finish_s=max(r['submit_to_finish_s'] for r in selected),
                            condor_execute_sum_s=sum(r['condor_execute_s'] for r in selected),remote_cpu_sum_s=sum(r['remote_cpu_s'] for r in selected),
                            wrapper_wall_sum_s=sum(r['wrapper_wall_s'] for r in selected),wrapper_cpu_sum_s=sum(r['wrapper_cpu_s'] for r in selected),
                            wrapper_peak_rss_KiB=max(r['wrapper_peak_rss_KiB'] for r in selected))
    (out/'condor_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
