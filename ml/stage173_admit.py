"""Predefined full16/pilot2 conservative complete-process cost gate."""
import json,re
from stage173_ops import ROOT,OUT,monitor
account=monitor();assert account['live_N']==0
assert (OUT/'pilot_exitcode.txt').read_text().strip()=='0'
text=(OUT/'pilot_time.txt').read_text()
cpu=sum(float(re.search(k+r' time \(seconds\): ([\d.]+)',text)[1]) for k in ['User','System'])
projected=3*cpu*16/2
admitted=account['total_CPU_s']+projected+250<=900
(OUT/'admission.json').write_text(json.dumps(dict(admitted=admitted,pilot_complete_GNU_CPU_s=cpu,
 full_threefold_projected_CPU_s=projected,scheduler_used_CPU_s=account['total_CPU_s'],audit_reserved_CPU_s=250,CPU_budget_s=900),indent=2)+'\n')
print(admitted,projected)
