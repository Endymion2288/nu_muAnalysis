"""Same96 profiling resolves file startup versus event-loop cost, within original budget."""
import json
from stage158_finalize import gnu
from stage175_ops import ROOT,OUT,monitor
account=monitor();assert account['live_N']==0
assert (OUT/'profile_exitcode.txt').read_text().strip()=='0'
p=json.loads((OUT/'protocol.json').read_text());profile=json.loads((OUT/'profile_summary.json').read_text());assert profile['passed']
complete=gnu(OUT/'profile_time.txt')['CPU_s'];mapping=gnu(OUT/'mapping_time.txt')['CPU_s']
readCPU=sum(r['CPU_s'] for r in profile['sources']);loop=sum(r['subsequent_loop_CPU_s'] for r in profile['sources']);n=sum(r['N'] for r in profile['sources'])
fileoverhead=readCPU-loop;startup=max(0,complete-readCPU)
projected=3*(fileoverhead*280/3+loop*p['original_N']/(n-3)+startup*8/3+mapping)
admitted=projected<=3600 and projected+account['total_CPU_s']+600<=4500
r=dict(admitted=admitted,initial_admission=False,cost_profile_addendum='cost_profile_addendum.json',profile_original96_exact=True,pilot_complete_GNU_CPU_s=complete,
 pilot_file_overhead_CPU_s=fileoverhead,pilot_subsequent_entry_CPU_s=loop,pilot_N=n,pilot_process_startup_CPU_s=startup,mapping_complete_GNU_CPU_s=mapping,
 full_threefold_projected_CPU_s=projected,audit_reserved_CPU_s=600,scheduler_used_CPU_s=account['total_CPU_s'],CPU_budget_s=4500)
(OUT/'admission.json').write_text(json.dumps(r,indent=2)+'\n');print(r)
