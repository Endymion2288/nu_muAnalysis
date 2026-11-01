#!/usr/bin/env python3
"""Compact resource accounting from the task's own event logs (no global history scan)."""
import json
import re
from datetime import datetime
from pathlib import Path
from train_bdt import write_table

repo=Path(__file__).resolve().parents[1]; out=repo/'workbook/stage42_energy_ml'
logs=Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage42/logs')
submissions=json.loads((out/'submissions.json').read_text()); rows=[]; operations=[]
for sub in submissions:
    cluster=sub['cluster']; events={i:{} for i in range(sub['jobs'])}
    for block in (logs/f'{cluster}.log').read_text().split('...'):
        m=re.search(r'(000|001|005|009) \(\d+\.(\d+)\.000\) (\d\d/\d\d \d\d:\d\d:\d\d)',block)
        if m:
            code,proc,stamp=m.groups(); events[int(proc)][code]=(datetime.strptime('2026/'+stamp,'%Y/%m/%d %H:%M:%S'),block)
    for proc,e in events.items():
        assert '000' in e
        removed='009' in e and '001' not in e; end='009' if removed else '005'
        assert end in e,(cluster,proc,'not finished')
        ms=[]; exit_code=None; execute=0; site_cpus=None; site_memory=None
        if not removed:
            assert '001' in e
            stderr=(logs/f'{cluster}.{proc}.err').read_text()
            ms=re.findall(r'stage42_(native|train) wall_s=([\d.]+) max_rss_KiB=(\d+) user_s=([\d.]+) system_s=([\d.]+)',stderr)
            assert ms,(cluster,proc,'no measured operation')
            for op,wall,rss,user,system in ms:
                operations.append(dict(cluster=cluster,proc=proc,part=sub['part'],operation=op,wall_s=float(wall),CPU_s=float(user)+float(system),max_RSS_KiB=int(rss)))
            done=e['005'][1]; exit_code=int(re.search(r'return value (\d+)',done).group(1))
            for line in done.splitlines():
                if re.match(r'\s*Cpus\s*:',line): site_cpus=int(line.split(':')[1].split()[-1])
                if re.match(r'\s*Memory \(MB\)\s*:',line): site_memory=int(line.split(':')[1].split()[-1])
            assert site_cpus is not None and site_memory is not None
            execute=int(re.search(r'TimeExecute \(s\)\s*:\s*(\d+)',done).group(1))
        rows.append(dict(schedd=sub['schedd'],part=sub['part'],cluster=cluster,proc=proc,idle_relocation=removed,exit_code=exit_code,
                         submitted_local=e['000'][0].isoformat(),terminated_local=e[end][0].isoformat(),
                         queue_wait_s=(e.get('001',e[end])[0]-e['000'][0]).total_seconds(),execute_s=execute,
                         descriptor_CPUs=1,descriptor_memory_MB=sub.get('descriptor_memory_MB',4000),site_CPUs=site_cpus,site_memory_MB=site_memory,GPUs=0,
                         wrapper_wall_s=sum(float(m[1]) for m in ms),wrapper_CPU_s=sum(float(m[3])+float(m[4]) for m in ms),
                         max_RSS_KiB=max([int(m[2]) for m in ms],default=0)))
write_table(out/'condor_resources.tsv',rows);write_table(out/'operation_resources.tsv',operations)
summary=dict(jobs=len(rows),successful=sum(r['exit_code']==0 for r in rows),idle_relocations=sum(r['idle_relocation'] for r in rows),
             failed=sum(r['exit_code'] not in [None,0] for r in rows),technical_execution_retries=0,
             allocated_CPU_seconds=sum(r['execute_s']*(r['site_CPUs'] or 0) for r in rows),
             wrapper_wall_s=sum(r['wrapper_wall_s'] for r in rows),wrapper_CPU_s=sum(r['wrapper_CPU_s'] for r in rows),
             peak_RSS_KiB=max(r['max_RSS_KiB'] for r in rows),
             submit_to_last_finish_s=(max(datetime.fromisoformat(r['terminated_local']) for r in rows)-min(datetime.fromisoformat(r['submitted_local']) for r in rows)).total_seconds(),GPUs=0)
summary['rejected_submission_attempts']=json.loads((out/'submission_notes.json').read_text())['rejected_submission_attempts']
(out/'condor_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
