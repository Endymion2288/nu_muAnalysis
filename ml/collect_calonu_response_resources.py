#!/usr/bin/env python3
"""Record every submitted response job and timed local operation."""
import json
import re
from datetime import datetime
from pathlib import Path
from report_calonu_native import table

repo=Path(__file__).resolve().parents[1];out=repo/'workbook/stage40_energy_ml'
logs=Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage40/logs');cluster=17556151
events={i:{} for i in range(3)}
for block in (logs/f'{cluster}.log').read_text().split('...'):
    match=re.search(r'(000|001|005) \(\d+\.(\d+)\.000\) (\d\d/\d\d \d\d:\d\d:\d\d)',block)
    if match:
        code,proc,stamp=match.groups();events[int(proc)][code]=(datetime.strptime('2026/'+stamp,'%Y/%m/%d %H:%M:%S'),block)
rows=[];operations=[]
for proc,record in events.items():
    assert all(k in record for k in ['000','001','005']),proc
    stderr=(logs/f'{cluster}.{proc}.err').read_text();stdout=(logs/f'{cluster}.{proc}.out').read_text()
    measurements=re.findall(r'stage40_(locate_\d+|native_\d+|source) wall_s=([\d.]+) max_rss_KiB=(\d+) user_s=([\d.]+) system_s=([\d.]+)',stderr)
    assert len(measurements)==(1 if proc==2 else 6)
    for operation,wall,rss,user,system in measurements:
        operations.append(dict(cluster=cluster,proc=proc,operation=operation,wall_s=float(wall),CPU_s=float(user)+float(system),max_RSS_KiB=int(rss)))
    block=record['005'][1];exit_code=int(re.search(r'return value (\d+)',block).group(1));assert exit_code==0
    rows.append(dict(cluster=cluster,proc=proc,source_groups=['2,43,49','105,111,119','synthetic_noise'][proc],
                     schedd='bigbird14.cern.ch',exit_code=exit_code,descriptor_CPUs=1,descriptor_memory_MB=4000,site_CPUs=2,site_memory_MB=6000,GPUs=0,
                     submitted_local=record['000'][0].isoformat(),terminated_local=record['005'][0].isoformat(),
                     queue_wait_s=(record['001'][0]-record['000'][0]).total_seconds(),
                     execute_s=int(re.search(r'TimeExecute \(s\)\s*:\s*(\d+)',block).group(1)),
                     wrapper_wall_s=sum(float(m[1]) for m in measurements),wrapper_CPU_s=sum(float(m[3])+float(m[4]) for m in measurements),
                     max_RSS_KiB=max(int(m[2]) for m in measurements),native_cases=stdout.count('NATIVE_CASE')))
table(out/'condor_resources.tsv',rows);table(out/'operation_resources.tsv',operations)
summary=dict(jobs=3,successes=3,failures=0,technical_resubmissions=0,wrapper_wall_s=sum(r['wrapper_wall_s'] for r in rows),
             wrapper_CPU_s=sum(r['wrapper_CPU_s'] for r in rows),max_RSS_KiB=max(r['max_RSS_KiB'] for r in rows),
             first_submit_to_last_finish_s=(max(datetime.fromisoformat(r['terminated_local']) for r in rows)-min(datetime.fromisoformat(r['submitted_local']) for r in rows)).total_seconds(),
             new_ML_fits=0,new_G4_events=0,GPU_allocation_s=0)
if (out/'summary.json').exists():
    extracted=json.loads((out/'summary.json').read_text())['extraction_resources']
    summary.update(native_internal_wall_s=sum(r['wall_s'] for r in extracted),native_events_per_s=sum(r['events'] for r in extracted)/sum(r['wall_s'] for r in extracted))
(out/'condor_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
local=[dict(path=str(p),timing=p.read_text().strip()) for p in sorted(Path('/tmp').glob('stage40*.time'))]
(out/'local_timing_records.json').write_text(json.dumps(local,indent=2)+'\n')
print(json.dumps(summary))
