"""Physical support/cost admission and actual paired tag contrast."""
import gzip
import json
import re
import resource
import time
from pathlib import Path

from stage151_compare import compare, load

OUT = Path('workbook/stage151_energy_ml')
CACHE = Path('ntuples/energy_ml_stage151')
cpu, tick = time.process_time(), time.perf_counter()
plan = json.loads((OUT/'protocol.json').read_text())
account = json.loads((OUT/'scheduler_accounting.json').read_text())
pilot = json.loads((OUT/'pilot/summary.json').read_text())
native = load(CACHE/'pilot/native.json.gz')
pairs = load(CACHE/'pilot/paired.json.gz')
seeds = json.loads((OUT/'pilot/seeds.json').read_text())
reco = json.loads((OUT/'pilot/reco_timing.json').read_text())
assert native['configured_conditions'] == dict(conditions='OFLCOND-FASER-04', geometry='FASERNU-04')
assert reco['conditions'] == seeds['conditions'] == 'OFLCOND-FASER-04'


def timing(name):
    text = (OUT/f'pilot/{name}_time.txt').read_text()
    return sum(float(re.search(r'(?m)^\s*'+key+r': (\S+)', text).group(1))
               for key in [r'User time \(seconds\)', r'System time \(seconds\)'])


ends = dict(digi=[r['execute_end_CPU_s'] for r in seeds['records']], reco=reco['event_end_CPU_s'],
            native=[r['execute_end_CPU_s'] for r in native['records']])
costs = []
for name, values in ends.items():
    post = values[-1]-values[0]
    total = timing(name)
    projected = 3*(max(0, total-post)+63*post/3)
    costs.append(dict(step=name, CPU_s=total, first_event_end_CPU_s=values[0], post_first_3_CPU_s=post,
                      factor3_affine64_CPU_s=projected))
projection = sum(r['factor3_affine64_CPU_s'] for r in costs)+3*timing('extract')
required = ['VetoNu0', 'VetoNu1', 'Veto10', 'Veto20', 'Veto21', 'Timing0', 'Timing1', 'Timing2', 'Timing3',
            'Preshower0', 'Preshower1']+[f'Calo{i}' for i in range(4)]
support = bool(pilot['N'] == 4 and pilot['selected_finite_covariance_N'] > 0 and pilot['raw15_exact_N'] == 4
    and all(set(required).issubset({v['name'] for v in r['readout']}) and r['all_tracks_float32_exact']
            and any(v['present'] and v['raw_charge_pC'] is not None for v in r['readout']) for r in pairs))
remaining = plan['resources']['CPU_budget_s']-account['total_CPU_s']
admission = dict(admitted=support and projection+100 < remaining, physical_pilot_passed=support,
    already_used_scheduler_CPU_s=account['total_CPU_s'], remaining_CPU_s=remaining, factor=3, costs=costs,
    full64_projected_CPU_s=projection, audit_reserve_CPU_s=100, parent_cap=64, overlapping_pilot_N=4)
if (OUT/'full_admission.json').exists():
    admission = json.loads((OUT/'full_admission.json').read_text())
else:
    (OUT/'full_admission.json').write_text(json.dumps(admission, indent=2)+'\n')
phase = 'full' if (OUT/'full/summary.json').exists() else 'pilot'
repro = None
if phase == 'full':
    full_native, full_pairs = load(CACHE/'full/native.json.gz'), load(CACHE/'full/paired.json.gz')
    full_seeds = json.loads((OUT/'full/seeds.json').read_text())
    checks = []
    for i in range(4):
        a, b = native['records'][i].copy(), full_native['records'][i].copy()
        a.pop('execute_end_CPU_s'); b.pop('execute_end_CPU_s')
        checks.append(dict(entry=i, native_exact=a == b, paired_exact=pairs[i] == full_pairs[i],
            RNG_before_after_exact=all(seeds['records'][i][key] == full_seeds['records'][i][key]
                                      for key in ['run', 'event', 'roots', 'seeds', 'before', 'after'])))
    repro = dict(N=4, checks=checks, passed=all(r['native_exact'] and r['paired_exact'] and r['RNG_before_after_exact'] for r in checks))
    assert repro['passed'], repro
comparison = compare(phase)
summary = dict(passed=True, phase=phase, unique_original_parent_N=comparison['N'],
    current_identity=json.loads((OUT/phase/'summary.json').read_text()), prefix_reproducibility=repro,
    tag_contrast=dict(common_physical_channels=comparison['common_physical_channels'],
                      mapped04=comparison['tag04_mapped_channels'], mapped06=comparison['tag06_mapped_channels'],
                      selected04_N=comparison['selected04_N'], selected06_N=comparison['selected06_N']),
    CPU_s=time.process_time()-cpu, wall_s=time.perf_counter()-tick,
    RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    new_G4=0, fits=0, reserved_forward=0, calibrated_covariance_pull=False, overall_complete=False)
(OUT/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
print('ADMISSION', admission, 'SUMMARY', summary, flush=True)
