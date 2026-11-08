"""Original predeclared conservative cost gate, using complete-process GNU time."""
import json
from pathlib import Path
from stage158_finalize import gnu
OUT=Path(__file__).resolve().parents[1]/'workbook/stage184_energy_ml'
p=json.loads((OUT/'protocol.json').read_text());account=json.loads((OUT/'scheduler_accounting.json').read_text())
assert account['live_N']==0
assert (OUT/'preflight_exitcode.txt').read_text().strip()=='0'
assert json.loads((OUT/'reference_summary.json').read_text())['passed']
assert json.loads((OUT/'preflight_source_0_summary.json').read_text())['passed']
times=gnu(OUT/'preflight_source_0_time.txt')
print(times)
CPU_s=times['CPU_s']
projected=3*CPU_s*92/4
result=dict(admitted=projected<=2200 and account['total_CPU_s']+projected+1000<=4000,
    measured_complete4parent_CPU_s=CPU_s,remaining_parents_N=92,conservative3x_remaining_CPU_s=projected,
    includes_literal_convolution_and_full_startup_per4=True,used_scheduler_CPU_s=account['total_CPU_s'],
    audit_reserve_CPU_s=1000,full_allowance_s=2200,CPU_budget_s=4000,scientific_preflight=True,
    not_full_cohort_admission=True)
(OUT/'admission.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
