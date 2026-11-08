"""Admission from the complete first-three GNU cost and actual PHYS file count."""
import json
from stage158_finalize import gnu
from pathlib import Path
OUT=Path(__file__).resolve().parents[1]/'workbook/stage167_energy_ml'
def write(name, value):
    (OUT/name).write_text(json.dumps(value, indent=2)+'\n')
from stage167_ops import monitor

account = monitor()
assert account['live_N'] == 0 and (OUT / 'pilot_exitcode.txt').read_text().strip() == '0'
pilot = json.loads((OUT / 'pilot_summary.json').read_text())
cost = gnu(OUT / 'pilot_time.txt')
projected = 3 * cost['CPU_s'] * pilot['actual_PHYS_N'] / 3
admitted = bool(pilot['passed'] and len(pilot['records']) == 3 and projected <= 900
                and projected + account['total_CPU_s'] + 300 <= 1500)
write('admission.json', dict(admitted=admitted, actual_PHYS_N=pilot['actual_PHYS_N'],
    pilot_GNU_CPU_s=cost['CPU_s'], safety_factor=3, projected_full_CPU_s=projected,
    used_scheduler_CPU_s=account['total_CPU_s'], audit_reserve_CPU_s=300, budget_CPU_s=1500,
    interpretation='Pilot startup and all three files included; conservative projection is not measured full cost.'))
print('admitted', admitted, 'projection', projected)
