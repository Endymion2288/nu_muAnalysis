"""Complete pilot and actual auxiliary inventory determine one bounded full run."""
import json
import math
from stage158_finalize import gnu
from stage197_ops import OUT,monitor

if __name__=='__main__':
    a=monitor();assert not a['live_N']
    assert (OUT/'pilot_exitcode.txt').read_text().strip()=='0'
    s=json.loads((OUT/'pilot_summary.json').read_text());p=json.loads((OUT/'protocol.json').read_text())
    total=gnu(OUT/'pilot_time.txt')['CPU_s'];f=s['files'][0]
    projection=None
    if s['passed']:
        blocks=f['block_resources'];steady=max(r['CPU_s']/r['N'] for r in blocks[1:])
        data=3*(f['CPU_s']+14237355*steady)
        aux=s['aux_resources'];aux_projection=0.
        if aux.get('supported') and not aux.get('not_needed_native'):
            measured=aux['block_resources'];rate=max(r['CPU_s']/r['N'] for r in measured)
            aux_projection=3*(aux['CPU_s']+aux['total_available_N']*rate)
        projection=3*max(0.,total-f['CPU_s']-aux.get('CPU_s',0.))+data+aux_projection
    result=dict(admitted=bool(s['passed'] and projection is not None and projection<=16000 and a['total_CPU_s']+projection+3600<=20000),
        complete_pilot_CPU_s=total,threefold_full_projection_CPU_s=projection,actual_data_source_N=14237355,
        used_CPU_s=a['total_CPU_s'],audit_reserve_CPU_s=3600,total_budget_CPU_s=20000,
        actual_aux_support=s['aux_resources'].get('supported',False),no_effect_size_gate=True)
    (OUT/'admission.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
