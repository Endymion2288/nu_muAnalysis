#!/usr/bin/env python3
"""Archive actual stage38 scheduler and pilot resource measurements."""
import json
import re
from datetime import datetime
from pathlib import Path

from report_calonu_native import table


def main():
    repo=Path(__file__).resolve().parents[1]
    out=repo/'workbook/stage38_energy_ml'
    logs=Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage38/logs')
    cluster=17555947
    groups=[1,4,7,10]
    events={i:{} for i in range(4)}
    for block in (logs/f'{cluster}.log').read_text().split('...'):
        m=re.search(r'(000|001|005) \(\d+\.(\d+)\.000\) (\d\d/\d\d \d\d:\d\d:\d\d)',block)
        if m:
            code,proc,stamp=m.groups()
            events[int(proc)][code]=(datetime.strptime('2026/'+stamp,'%Y/%m/%d %H:%M:%S'),block)
    rows=[]
    for proc,e in events.items():
        assert all(k in e for k in ['000','001','005'])
        stderr=(logs/f'{cluster}.{proc}.err').read_text()
        measurements=re.findall(r'stage38_(locate|native|repair) wall_s=([\d.]+) max_rss_KiB=(\d+) user_s=([\d.]+) system_s=([\d.]+)',stderr)
        assert len(measurements)==3
        done=e['005'][1]
        code=int(re.search(r'return value (\d+)',done).group(1))
        assert code==0
        rows.append(dict(cluster=cluster,proc=proc,group=groups[proc],schedd='bigbird14.cern.ch',exit_code=code,
                         descriptor_cpus=1,descriptor_memory_MB=4000,site_request_cpus=2,site_request_memory_MB=6000,GPUs=0,
                         submitted_local=e['000'][0].isoformat(),terminated_local=e['005'][0].isoformat(),
                         queue_wait_s=(e['001'][0]-e['000'][0]).total_seconds(),
                         execute_s=int(re.search(r'TimeExecute \(s\)\s*:\s*(\d+)',done).group(1)),
                         **{m[0]+'_wall_s':float(m[1]) for m in measurements},
                         wrapper_cpu_s=sum(float(m[3])+float(m[4]) for m in measurements),
                         peak_rss_KiB=max(int(m[2]) for m in measurements)))
    table(out/'condor_resources.tsv',rows)
    extraction=json.loads((out/'confirmation_summary.json').read_text())['extraction_resources']
    summary=dict(jobs=len(rows),successful=4,failed=0,schedd='bigbird14.cern.ch',
                 wrapper_wall_s=sum(r[k+'_wall_s'] for r in rows for k in ['locate','native','repair']),
                 wrapper_cpu_s=sum(r['wrapper_cpu_s'] for r in rows),peak_rss_KiB=max(r['peak_rss_KiB'] for r in rows),
                 submit_to_last_finish_s=(max(e['005'][0] for e in events.values())-min(e['000'][0] for e in events.values())).total_seconds(),
                 native_internal_wall_s=sum(r['wall_s'] for r in extraction),
                 native_events_per_s=128/sum(r['wall_s'] for r in extraction),
                 new_ML_fits=0,new_G4_events=0,GPU_allocation_s=0)
    (out/'condor_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    local=[dict(path=str(p),timing=p.read_text().strip()) for p in sorted(Path('/tmp').glob('stage38*.time'))]
    (out/'local_timing_records.json').write_text(json.dumps(local,indent=2)+'\n')
    print(json.dumps(summary))


if __name__=='__main__': main()
