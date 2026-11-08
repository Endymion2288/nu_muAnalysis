import json
from stage158_finalize import gnu
from stage189_ops import OUT,monitor

account=monitor();assert account['live_N']==0
assert (OUT/'pilot_exitcode.txt').read_text().strip()=='0'
result=json.loads((OUT/'pilot_summary.json').read_text());assert result['passed']
cpu=gnu(OUT/'pilot_time.txt')['CPU_s'];projection=3*cpu*3*70/62
rss=result['fit']['RSS_KiB']*4/1024
admitted=projection<=1400 and projection+account['total_CPU_s']+600<=2400 and rss<=8000
r=dict(admitted=admitted,complete_GNU_baseline3fits_CPU_s=cpu,
    full_three_arm_threefold_dimension_scaled_CPU_s=projection,projected_RSS_MB=rss,
    scheduler_used_CPU_s=account['total_CPU_s'],audit_reserved_CPU_s=600,CPU_budget_s=2400)
(OUT/'admission.json').write_text(json.dumps(r,indent=2)+'\n');print(r)
