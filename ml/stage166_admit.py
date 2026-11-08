"""Metadata-only cost gate; the event pilot has already run on Condor."""
import json
import math
from stage158_finalize import gnu
from stage166_common import OUT, plan, write

p = plan(); pilot = json.loads((OUT / 'pilot_summary.json').read_text())
account = json.loads((OUT / 'scheduler_accounting.json').read_text())
assert pilot['passed'] and account['live_N'] == 0
# Scheduler already includes the completed pilot GNU process: count it once.
projection = 3 * (pilot['first512_and_open_CPU_s'] + math.ceil((pilot['source_N'] - 512) / 512) * pilot['second512_CPU_s'])
admitted = projection <= 600 and account['total_CPU_s'] + projection + 300 <= 1200
timing = OUT / ('pilot_retry_time.txt' if (OUT / 'pilot_retry_time.txt').exists() else 'pilot_time.txt')
write('admission.json', dict(admitted=admitted, full_3x_projected_CPU_s=projection,
    used_scheduler_CPU_s=account['total_CPU_s'], pilot_GNU_CPU_s=gnu(timing)['CPU_s'],
    audit_reserve_CPU_s=300, total_budget_CPU_s=1200,
    note='pilot GNU is nested in scheduler and not added twice; full projection is not measured cost or guarantee'))
print(json.loads((OUT / 'admission.json').read_text()))
