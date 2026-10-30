#!/usr/bin/env python3
"""Record actual stage15 Condor completion and /usr/bin/time measurements."""
import argparse
import json
import re
from datetime import datetime
from pathlib import Path

from train_bdt import write_table


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--extraction-cluster',type=int,required=True)
    p.add_argument('--oracle-cluster',type=int,required=True)
    p.add_argument('--log-dir',type=Path)
    args=p.parse_args(); records=[]
    logs=args.log_dir if args.log_dir is not None else args.repo/'logs'
    for name,cluster,count,memory in [('primary_extract',args.extraction_cluster,19,1200),('muon_oracle',args.oracle_cluster,3,1500)]:
        log=(logs/f'ml_{name}_{cluster}.log').read_text()
        events={proc:{} for proc in range(count)}
        for block in log.split('...'):
            match=re.search(r'(\d{3}) \(\d+\.(\d+)\.000\) (\d\d/\d\d \d\d:\d\d:\d\d)',block)
            if not match:continue
            code,proc,stamp=match.groups();proc=int(proc)
            if code in ['000','001','005']:
                stamp=datetime.strptime('2026/'+stamp,'%Y/%m/%d %H:%M:%S')
                events[proc][code]=(stamp,block)
        for proc,e in events.items():
            if not all(code in e for code in ['000','001','005']):raise RuntimeError(f'Unfinished {cluster}.{proc}')
            done=e['005'][1]; exitcode=int(re.search(r'return value (\d+)',done).group(1))
            if exitcode:raise RuntimeError(f'Failed {cluster}.{proc}: {exitcode}')
            timing=(logs/f'ml_{name}_{cluster}.{proc}.err').read_text()
            measured=re.search(r'wall_s=([\d.]+) max_rss_KiB=(\d+) user_s=([\d.]+) system_s=([\d.]+)',timing)
            if not measured:raise RuntimeError('Missing resource measurement')
            wall,rss,user,system=map(float,measured.groups())
            times=re.findall(r'(?:Usr|Sys) (\d+) (\d+):(\d+):(\d+)',done)[:2]
            remote_cpu=sum(int(d)*86400+int(h)*3600+int(m)*60+int(s) for d,h,m,s in times)
            records.append(dict(study=name,cluster=cluster,proc=proc,exit_code=exitcode,
                                submitted_local=e['000'][0].isoformat(),executed_local=e['001'][0].isoformat(),
                                terminated_local=e['005'][0].isoformat(),
                                submit_to_finish_s=(e['005'][0]-e['000'][0]).total_seconds(),
                                execute_to_finish_s=(e['005'][0]-e['001'][0]).total_seconds(),
                                reported_time_execute_s=int(re.search(r'TimeExecute \(s\)\s*:\s*(\d+)',done).group(1)),
                                remote_cpu_s=remote_cpu,wrapper_wall_s=wall,wrapper_max_rss_KiB=int(rss),
                                wrapper_user_s=user,wrapper_system_s=system,requested_cpus=1,
                                submit_memory_MB=memory,allocated_memory_MB=int(re.search(r'Memory = (\d+)',e['001'][1]).group(1))))
    out=args.repo/'workbook/stage15_energy_ml'
    write_table(out/'condor_resources.tsv',records)
    summary={}
    for name in ['primary_extract','muon_oracle']:
        rows=[r for r in records if r['study']==name]
        summary[name]=dict(jobs=len(rows),all_exit_zero=True,
                           submit_to_last_finish_s=max(r['submit_to_finish_s'] for r in rows),
                           execute_wall_sum_s=sum(r['reported_time_execute_s'] for r in rows),
                           remote_cpu_sum_s=sum(r['remote_cpu_s'] for r in rows),
                           wrapper_wall_sum_s=sum(r['wrapper_wall_s'] for r in rows),
                           wrapper_cpu_sum_s=sum(r['wrapper_user_s']+r['wrapper_system_s'] for r in rows),
                           wrapper_peak_rss_KiB=max(r['wrapper_max_rss_KiB'] for r in rows))
    (out/'condor_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
