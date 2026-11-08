"""Cost-only admission using the completed smoke GNU process, with frozen audit reserve."""
import json
import re
from pathlib import Path
from stage170_ops import monitor
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage170_energy_ml'
account=monitor();assert account['live_N']==0
smoke=json.loads((OUT/'smoke_summary.json').read_text());assert smoke['passed'] and smoke['reference']['passed']
assert smoke['valid_single_TLB_N']>0
text=(OUT/'smoke_time.txt').read_text()
user=float(re.search(r'User time \(seconds\): ([\d.]+)',text)[1])
sys=float(re.search(r'System time \(seconds\): ([\d.]+)',text)[1])
projected=3*(user+sys)*8192/56
admitted=account['total_CPU_s']+projected+300<=1200
result=dict(admitted=admitted,smoke_complete_GNU_CPU_s=user+sys,full_threefold_CPU_s=projected,
    scheduler_used_CPU_s=account['total_CPU_s'],audit_reserve_s=300,CPU_budget_s=1200,
    includes_imports_and_scientific_processing=True,compilation_accounted_in_scheduler_used=True)
(OUT/'admission.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
