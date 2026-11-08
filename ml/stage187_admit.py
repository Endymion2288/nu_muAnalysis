"""Batch-only complete-pilot resource gate, fixed remaining analysis allowance."""
import json
from pathlib import Path
from stage158_finalize import gnu
OUT=Path('workbook/stage187_energy_ml')
if __name__=='__main__':
 r=gnu(OUT/'pilot_time.txt');projected=3*11*r['CPU_s']+20
 result=dict(admitted=projected<=100 and 40+projected+100<=240,complete_pilot_GNU=r,remaining11_threefold_plus_fixed20_CPU_reserve_s=projected,pilot_CPU_reserved_s=40,audit_CPU_reserved_s=100,total_projection_CPU_s=40+projected+100,cap_CPU_s=240,analysis_cap_CPU_s=100,reserve_note='20CPU s is a conservative unmeasured non-event/plot allowance, not a measured performance claim; pilot reservation40 also counts failed attempts if any.')
 (OUT/'admission.json').write_text(json.dumps(result,indent=2)+'\n');print(result,flush=True)
