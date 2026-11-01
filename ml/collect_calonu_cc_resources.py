#!/usr/bin/env python3
"""Keep the eight bounded CC attempts, including failed identity checks and re-reads."""
import json
import re
from datetime import datetime
from pathlib import Path

from report_calonu_native import table


def main():
    repo=Path(__file__).resolve().parents[1];out=repo/'workbook/stage39_energy_ml'
    logs=Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage39/logs')
    rows=[];measurements=[]
    for cluster,groups in [(17555948,[[1],[44],[47],[106],[110],[120]]),(17555949,[[1,44,47],[106,110,120]])]:
        events={i:{} for i in range(len(groups))}
        for block in (logs/f'{cluster}.log').read_text().split('...'):
            m=re.search(r'(000|001|005) \(\d+\.(\d+)\.000\) (\d\d/\d\d \d\d:\d\d:\d\d)',block)
            if m:
                code,proc,stamp=m.groups();events[int(proc)][code]=(datetime.strptime('2026/'+stamp,'%Y/%m/%d %H:%M:%S'),block)
        for proc,e in events.items():
            assert all(k in e for k in ['000','001','005'])
            stderr=(logs/f'{cluster}.{proc}.err').read_text()
            stdout=(logs/f'{cluster}.{proc}.out').read_text()
            ms=re.findall(r'stage39_(locate|native)(?:_(\d+))? wall_s=([\d.]+) max_rss_KiB=(\d+) user_s=([\d.]+) system_s=([\d.]+)',stderr)
            assert len(ms)==2*len(groups[proc])
            for operation,group,wall,rss,user,system in ms:
                measurements.append(dict(cluster=cluster,proc=proc,group=int(group) if group else groups[proc][0],operation=operation,
                                         wall_s=float(wall),CPU_s=float(user)+float(system),max_RSS_KiB=int(rss)))
            done=e['005'][1];code=int(re.search(r'return value (\d+)',done).group(1))
            assert code==(1 if cluster==17555948 else 0)
            if code:assert 'BeamTruth mass differs by >=1 keV' in stderr
            rows.append(dict(cluster=cluster,proc=proc,groups=','.join(map(str,groups[proc])),schedd='bigbird14.cern.ch',exit_code=code,
                             descriptor_CPUs=1,descriptor_memory_MB=4000,site_request_CPUs=2,site_request_memory_MB=6000,GPUs=0,
                             submitted_local=e['000'][0].isoformat(),terminated_local=e['005'][0].isoformat(),
                             queue_wait_s=(e['001'][0]-e['000'][0]).total_seconds(),
                             execute_s=int(re.search(r'TimeExecute \(s\)\s*:\s*(\d+)',done).group(1)),
                             wrapper_wall_s=sum(float(m[2]) for m in ms),wrapper_CPU_s=sum(float(m[4])+float(m[5]) for m in ms),
                             max_RSS_KiB=max(int(m[3]) for m in ms),completed_case_lines=stdout.count('NATIVE_CASE'),
                             reason='Absolute-mass check is ill-conditioned for lightlike CC neutrinos' if code else 'Success'))
    table(out/'condor_resources.tsv',rows);table(out/'operation_resources.tsv',measurements)
    extraction=json.loads((out/'summary.json').read_text())['extraction_resources']
    summary=dict(jobs=len(rows),successful=2,failed=6,wrapper_wall_s=sum(r['wrapper_wall_s'] for r in rows),
                 wrapper_CPU_s=sum(r['wrapper_CPU_s'] for r in rows),max_RSS_KiB=max(r['max_RSS_KiB'] for r in rows),
                 successful_wrapper_wall_s=sum(r['wrapper_wall_s'] for r in rows if r['exit_code']==0),
                 failed_wrapper_wall_s=sum(r['wrapper_wall_s'] for r in rows if r['exit_code']!=0),
                 first_submit_to_last_finish_s=(max(datetime.fromisoformat(r['terminated_local']) for r in rows)-min(datetime.fromisoformat(r['submitted_local']) for r in rows)).total_seconds(),
                 native_internal_wall_s=sum(r['wall_s'] for r in extraction),native_events_per_s=sum(r['events'] for r in extraction)/sum(r['wall_s'] for r in extraction),
                 new_ML_fits=0,new_G4_events=0,GPU_allocation_s=0,
                 rejected_submission='bigbird24 EosSubmit disallows AFS executable/log paths; no committed jobs; switched to bigbird14')
    (out/'condor_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    local=[dict(path=str(p),timing=p.read_text().strip()) for p in sorted(Path('/tmp').glob('stage39*.time'))]
    (out/'local_timing_records.json').write_text(json.dumps(local,indent=2)+'\n')
    print(json.dumps(summary))


if __name__=='__main__':main()
