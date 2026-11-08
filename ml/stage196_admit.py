"""Measured complete native read and joint statistics before the original64/12."""
import json
from stage158_finalize import gnu
from stage196_ops import OUT,monitor

if __name__=='__main__':
    account=monitor();assert account['live_N']==0
    assert (OUT/'pilot_exitcode.txt').read_text().strip()=='0'
    raw=json.loads((OUT/'pilot_raw_summary.json').read_text());s=json.loads((OUT/'pilot_summary.json').read_text())
    raw_cpu=gnu(OUT/'pilot_raw_time.txt')['CPU_s'];stat_cpu=gnu(OUT/'pilot_statistics_time.txt')['CPU_s']
    slowest=max(raw['event_CPU_s'][1:]);projection=raw_cpu+3*60*slowest+3*6*stat_cpu
    valid=s['passed'] and s['original4_scalar_checks_N']>0 and s['MC_ideal_closure']['passed'] and s['random_controls_N']==116
    r=dict(admitted=valid and projection<=1600 and account['total_CPU_s']+projection+400<=2400,
        scientific_checks_passed=valid,complete_pilot_raw_CPU_s=raw_cpu,complete_pilot_statistics_CPU_s=stat_cpu,
        slowest_postfirst_raw_CPU_s=slowest,threefold_full_projection_CPU_s=projection,
        used_scheduler_CPU_s=account['total_CPU_s'],audit_reserved_CPU_s=400,total_budget_CPU_s=2400)
    (OUT/'admission.json').write_text(json.dumps(r,indent=2)+'\n');print(r)
