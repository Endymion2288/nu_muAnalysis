"""Profile startup and actual two chunks before all entries."""
import json
from stage158_finalize import gnu
from stage180_ops import OUT,monitor
account=monitor();assert account['live_N']==0
assert (OUT/'pilot_exitcode.txt').read_text().strip()=='0'
s=json.loads((OUT/'pilot_summary.json').read_text());assert s['passed']
cpu=gnu(OUT/'pilot_time.txt')['CPU_s'];loop=sum(s['loop_CPU_s']);startup=max(0,cpu-loop)
projection=3*(startup+loop*s['source_N']/s['N'])
r=dict(admitted=projection<=800 and projection+account['total_CPU_s']+200<=1200,
    measured_complete_pilot_CPU_s=cpu,measured_two_chunk_CPU_s=loop,startup_and_postprocess_CPU_s=startup,
    threefold_full_CPU_s=projection,scheduler_used_CPU_s=account['total_CPU_s'],audit_reserved_CPU_s=200,CPU_budget_s=1200,
    profile='Complete GNU startup/postprocessing plus actual two4096-chunk read CPU; no budget relaxation.')
(OUT/'admission.json').write_text(json.dumps(r,indent=2)+'\n');print(r)
