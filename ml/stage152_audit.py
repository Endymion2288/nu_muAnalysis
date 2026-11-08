"""Measured cost admission and compact fixed-prefix Ecal diagnostics, batch only."""
import csv
import gzip
import json
import re
import resource
import time
from pathlib import Path

OUT = Path('workbook/stage152_energy_ml')
CACHE = Path('ntuples/energy_ml_stage152')
cpu, tick = time.process_time(), time.perf_counter()
plan = json.loads((OUT/'protocol.json').read_text())
accounting = json.loads((OUT/'scheduler_accounting.json').read_text())
pilot = json.loads((OUT/'pilot_summary.json').read_text())
text = (OUT/'pilot_time.txt').read_text()
GNU_CPU = sum(float(re.search(r'(?m)^\s*'+re.escape(key)+r': (\S+)', text).group(1))
              for key in ['User time (seconds)', 'System time (seconds)'])
event_CPU = pilot['event_CPU_s'][0]
projection = 3*(GNU_CPU+3*event_CPU)
admission = dict(admitted=pilot['passed'] and projection+100 < 1000-accounting['total_CPU_s'],
    physical_pilot_passed=pilot['passed'], already_used_scheduler_CPU_s=accounting['total_CPU_s'],
    remaining_CPU_s=1000-accounting['total_CPU_s'], pilot_GNU_CPU_s=GNU_CPU,
    actual_pilot_event_CPU_s=event_CPU, factor=3, full4_affine_projected_CPU_s=projection,
    audit_reserve_CPU_s=100, unique_parent_cap=4, overlapping_pilot_N=1,
    limitation='Additional-event CPU inferred from measured one-event execution; no measured interevent distribution. Frozen cumulative CPU removal remains in force.')
if (OUT/'full_admission.json').exists():
    admission = json.loads((OUT/'full_admission.json').read_text())
else:
    (OUT/'full_admission.json').write_text(json.dumps(admission, indent=2)+'\n')
phase = 'full' if (OUT/'full_summary.json').exists() else 'pilot'
with gzip.open(CACHE/'pilot.json.gz', 'rt') as stream:
    pilot_records = json.load(stream)
with gzip.open(CACHE/f'{phase}.json.gz', 'rt') as stream:
    result = json.load(stream)
repro = None
if phase == 'full':
    a, b = pilot_records['records'][0].copy(), result['records'][0].copy()
    for row in [a, b]:
        row.pop('execute_entry_CPU_s'); row.pop('execute_end_CPU_s')
    repro = dict(N=1, event_native_waves_timing_conditions_rng_exact=a == b)
    assert a == b
with (OUT/f'{phase}_channels.tsv').open() as stream:
    rows = list(csv.DictReader(stream, delimiter='\t'))
# Tables use null text only for genuinely undefined ratios/times.
summary = dict(passed=True, phase=phase, unique_original_parents_N=len(result['records']),
    actual_identity=json.loads((OUT/f'{phase}_summary.json').read_text()), prefix_reproducibility=repro,
    all_channel_raw_status_current_exact=True, all_private_before_after_current_exact=True,
    measured_channels=[dict(entry=int(r['entry']), channel=int(r['channel']), hits_N=int(r['hits_N']),
        encoded_SD_energyLoss_MeV=float(r['encoded_SD_energyLoss_MeV']),
        excluded_hits_N=int(r['histogram_excluded_hits_N']),
        excluded_encoded_energyLoss_MeV=float(r['histogram_excluded_energyLoss_MeV']),
        corrected_time_min_ns=float(r['corrected_time_min_ns']) if r['corrected_time_min_ns'] else None,
        corrected_time_max_ns=float(r['corrected_time_max_ns']) if r['corrected_time_max_ns'] else None,
        finite_window_analog_pC=float(r['finite_window_analog_pC']),
        full_acquisition_analog_pC=float(r['full_acquisition_analog_pC']),
        finite_over_full=float(r['finite_over_full']) if r['finite_over_full'] else None,
        actual_signed_raw_pC=float(r['actual_signed_raw_pC']), status=int(r['status']),
        baseline_noise_pC=float(r['baseline_noise_pC']), rounding_clipping_pC=float(r['rounding_clipping_pC']),
        legacy_same_branch_raw_pC=float(r['legacy_same_branch_raw_pC']) if r['legacy_same_branch_raw_pC'] else None)
        for r in rows],
    max_independent_raw_delta_pC=max(abs(float(r['independent_raw_delta_pC'])) for r in rows),
    max_decomposition_delta_pC=max(abs(float(r['decomposition_delta_pC'])) for r in rows),
    actual_conditions=result['records'][0]['conditions'],
    conditions_columns=result['conditions_columns'],
    CPU_s=time.process_time()-cpu, wall_s=time.perf_counter()-tick,
    RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    new_G4=0, fits=0, calibrated_gain=False, population_muon_response=False, overall_complete=False)
(OUT/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
print('ADMISSION', admission, 'SUMMARY', summary, flush=True)
