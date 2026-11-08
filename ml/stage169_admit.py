"""Admission from the complete fixed-pilot GNU cost and actual completed source count."""
import json
from stage158_finalize import gnu
from pathlib import Path
OUT=Path(__file__).resolve().parents[1]/'workbook/stage169_energy_ml'
def write(name, value):
    (OUT/name).write_text(json.dumps(value, indent=2)+'\n')
from stage169_ops import monitor

account = monitor()
assert account['live_N'] == 0 and (OUT / 'pilot_exitcode.txt').read_text().strip() == '0'
pilot = json.loads((OUT / 'pilot_summary.json').read_text())
cost = gnu(OUT / 'pilot_time.txt')
projected = 3 * cost['CPU_s'] * 666 / 16
admitted = bool(pilot['passed'] and len(pilot['records']) == 16 and projected <= 120
                and projected + account['total_CPU_s'] + 120 <= 300)
write('admission.json', dict(admitted=admitted, actual_completed_source_N=666,
    pilot_GNU_CPU_s=cost['CPU_s'], safety_factor=3, projected_full_CPU_s=projected,
    used_scheduler_CPU_s=account['total_CPU_s'], audit_reserve_CPU_s=120, budget_CPU_s=300,
    interpretation='Pilot startup and all fixed pilot files included; conservative projection is not measured full cost.'))
print('admitted', admitted, 'projection', projected)
