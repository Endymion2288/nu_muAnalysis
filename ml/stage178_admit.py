"""Admit only the new G4-only implementation, never the failed full chain."""
import json
from stage158_finalize import gnu
from stage178_ops import ROOT, OUT, monitor

account = monitor()
assert account['live_N'] == 0
assert (OUT / 'feasibility_exitcode.txt').read_text().strip() == '0'
assert json.loads((OUT / 'feasibility_summary.json').read_text())['passed']
p = json.loads((OUT / 'protocol.json').read_text())
measured = json.loads((ROOT / 'workbook/stage176_energy_ml/process_resources.json').read_text())
chain = sum(r['CPU_s'] for r in measured if r['phase'] in ['parent_50_sim_time', 'parent_50_hitscheck_time'])
complete = gnu(OUT / 'feasibility_time.txt')['CPU_s']
projected = 3 * len(p['replay_indices']) * (chain + complete)
passed = projected <= p['phase_CPU_allowance_s']['replay'] and projected + account['total_CPU_s'] + p['phase_CPU_allowance_s']['audit'] <= p['CPU_budget_s']
r = dict(admitted=passed, actual_sim_plus_HITScheck_CPU_s=chain, complete_feasibility_CPU_s=complete,
    threefold_remaining11_CPU_s=projected, scheduler_used_CPU_s=account['total_CPU_s'],
    audit_reserved_CPU_s=1200, CPU_budget_s=4500, no_budget_relaxation=True,
    implementation_change='No digitization/reconstruction/ntuple; conservative original state intervals instead of repeated native extraction.')
(OUT / 'admission.json').write_text(json.dumps(r, indent=2) + '\n')
print(r)
