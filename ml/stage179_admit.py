"""Complete measured pilot cost gate, with original disjoint allowances."""
import json
from stage158_finalize import gnu
from stage179_ops import OUT,monitor
account=monitor();assert account['live_N']==0
phase='preflight_repair' if (OUT/'preflight_repair_submission.json').exists() else 'preflight'
assert (OUT/f'{phase}_exitcode.txt').read_text().strip()=='0'
assert json.loads((OUT/'parent_50_summary.json').read_text())['passed']
cost=gnu(OUT/f'{phase}_time.txt')['CPU_s'];projected=3*11*cost
r=dict(admitted=projected<=6000 and projected+account['total_CPU_s']+1000<=8000,
    complete_preflight_CPU_s=cost,threefold_remaining11_CPU_s=projected,scheduler_used_CPU_s=account['total_CPU_s'],
    audit_reserved_CPU_s=1000,CPU_budget_s=8000,budget_relaxed=False)
(OUT/'admission.json').write_text(json.dumps(r,indent=2)+'\n');print(r)
