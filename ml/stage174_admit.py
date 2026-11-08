"""Small-control complete-GNU projected budget gate before full calibration."""
import json,re
from stage174_ops import ROOT,OUT,monitor
account=monitor();assert account['live_N']==0
assert (OUT/'pilot_exitcode.txt').read_text().strip()=='0'
pilot=json.loads((OUT/'pilot_summary.json').read_text());assert pilot['all_schema_supported']
text=(OUT/'pilot_time.txt').read_text();cpu=sum(float(re.search(k+r' time \(seconds\): ([\d.]+)',text)[1]) for k in ['User','System'])
projected=3*cpu*4096/256;admitted=projected+account['total_CPU_s']+300<=1200
result=dict(admitted=admitted,pilot_complete_GNU_CPU_s=cpu,full_threefold_projected_CPU_s=projected,
 scheduler_used_CPU_s=account['total_CPU_s'],audit_reserved_CPU_s=300,CPU_budget_s=1200)
(OUT/'admission.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
