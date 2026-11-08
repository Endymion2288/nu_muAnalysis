"""Complete measured one-parent cost gate before the original remaining11."""
import json
from stage158_finalize import gnu
from stage176_ops import OUT,monitor
account=monitor();assert account['live_N']==0
assert (OUT/'preflight_repair_exitcode.txt').read_text().strip()=='0'
p=json.loads((OUT/'protocol.json').read_text());summary=json.loads((OUT/'preflight_repair_summary.json').read_text());assert summary['passed']
preflight=gnu(OUT/'preflight_repair_time.txt')['CPU_s'];projected=3*preflight*11
admitted=projected<=7000 and projected+account['total_CPU_s']+1500<=10000
r=dict(admitted=admitted,complete_GNU_preflight_CPU_s=preflight,threefold_remaining11_CPU_s=projected,scheduler_used_CPU_s=account['total_CPU_s'],audit_reserved_CPU_s=1500,CPU_budget_s=10000,no_production_expansion=True)
(OUT/'admission.json').write_text(json.dumps(r,indent=2)+'\n');print(r)
