import json
from stage158_finalize import gnu
from stage177_ops import OUT,monitor
account=monitor();assert account['live_N']==0 and (OUT/'pilot_exitcode.txt').read_text().strip()=='0'
r=json.loads((OUT/'pilot_summary.json').read_text());assert r['passed']
cpu=gnu(OUT/'pilot_time.txt')['CPU_s'];projected=3*cpu*2
admitted=projected<=1400 and projected+account['total_CPU_s']+600<=2400
result=dict(admitted=admitted,complete_GNU_baseline3fits_CPU_s=cpu,full_two_arm_threefold_CPU_s=projected,scheduler_used_CPU_s=account['total_CPU_s'],audit_reserved_CPU_s=600,CPU_budget_s=2400)
(OUT/'admission.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
