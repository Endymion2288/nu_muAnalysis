"""Gate complete cached-response cost without relaxing the frozen allowance."""
import json
from pathlib import Path
from stage158_finalize import gnu
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage182_energy_ml'
p=json.loads((OUT/'protocol.json').read_text());s=json.loads((OUT/'pilot_summary.json').read_text())
assert s['passed'] and (OUT/'pilot_exitcode.txt').read_text().strip()=='0'
cost=gnu(OUT/'pilot_time.txt')['CPU_s'];projection=3*cost*len(p['indices'])
used=json.loads((OUT/'scheduler_accounting.json').read_text())['total_CPU_s']
r=dict(admitted=projection<=150 and used+projection+100<=300,complete_pilot_CPU_s=cost,threefold_full_CPU_s=projection,used_CPU_s=used,audit_reserved_s=100,CPU_budget_s=300)
(OUT/'admission.json').write_text(json.dumps(r,indent=2)+'\n');print(r);assert r['admitted']
