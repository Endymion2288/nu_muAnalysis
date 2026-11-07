"""Fixed physical-support/cost admission and prefix-repeat audit; no fits."""
import gzip
import json
import re
import resource
import time
from pathlib import Path

import numpy as np

OUT = Path('workbook/stage149_energy_ml')
CACHE = Path('ntuples/energy_ml_stage149')
tick, cpu = time.perf_counter(), time.process_time()


def load(phase, name):
    with gzip.open(CACHE/phase/name, 'rt') as stream:
        return json.load(stream)


def timing(path):
    text = path.read_text()
    return sum(float(re.search(r'(?m)^\s*'+key+r': (\S+)', text).group(1))
               for key in ['User time \(seconds\)', 'System time \(seconds\)'])


accounting = json.loads((OUT/'scheduler_accounting.json').read_text())
summary = json.loads((OUT/'pilot/summary.json').read_text())
pilot_native = load('pilot', 'native.json.gz')
pilot_pairs = load('pilot', 'paired.json.gz')
pilot_seeds = json.loads((OUT/'pilot/seeds.json').read_text())
ends = dict(digi=[r['execute_end_CPU_s'] for r in pilot_seeds['records']],
            reco=json.loads((OUT/'pilot/reco_timing.json').read_text())['event_end_CPU_s'],
            native=[r['execute_end_CPU_s'] for r in pilot_native['records']])
costs = []
for name, times in ends.items():
    total = timing(OUT/f'pilot/{name}_time.txt')
    post = times[-1]-times[0]
    fixed = max(0, total-post)
    estimate = fixed+63*post/3
    costs.append(dict(step=name, process_total_CPU_s=total, first_event_end_CPU_s=times[0],
        post_first_3_intervals_CPU_s=post, fixed_including_first_CPU_s=fixed,
        affine_full64_CPU_s=estimate, factor3_full64_CPU_s=3*estimate))
projection = sum(r['factor3_full64_CPU_s'] for r in costs)+3*timing(OUT/'pilot/extract_time.txt')
remaining = 3000-accounting['total_CPU_s']
requested = ['VetoNu0', 'VetoNu1', 'Veto10', 'Veto20', 'Veto21',
             'Timing0', 'Timing1', 'Timing2', 'Timing3', 'Preshower0', 'Preshower1']+[f'Calo{i}' for i in range(4)]
requested_support = all(set(requested).issubset({v['name'] for v in r['readout']})
                        and all(v['exact'] for v in r['readout'] if v['name'] in requested) for r in pilot_pairs)
support = (summary['N'] == 4 and summary['selected_finite_covariance_N'] > 0
           and summary['leading_exact_N'] == 4 and summary['raw15_exact_N'] == 4 and requested_support
           and all(any(v['present'] and v['raw_charge_pC'] is not None for v in r['readout']) for r in pilot_pairs))
admission = dict(admitted=bool(support and projection+100 < remaining), physical_support=support,
    requested_raw15=requested, requested_raw15_support=requested_support, actual_mapped_channels=summary['channels'],
    costs=costs, factor=3, full64_projected_CPU_s=projection, final_audit_reserve_CPU_s=100,
    already_used_scheduler_CPU_s=accounting['total_CPU_s'], remaining_CPU_s=remaining,
    independent_parent_cap=64, prefix_overlap_N=4, new_G4=0, energy_fits=0)
if not (OUT/'full_admission.json').exists():
    (OUT/'full_admission.json').write_text(json.dumps(admission, indent=2)+'\n')
else:
    admission = json.loads((OUT/'full_admission.json').read_text())
repro = None
phase = 'full' if (OUT/'full/summary.json').exists() else 'pilot'
native, pairs = load(phase, 'native.json.gz'), load(phase, 'paired.json.gz')
if phase == 'full':
    full_seeds = json.loads((OUT/'full/seeds.json').read_text())
    checks = []
    for i in range(4):
        a, b = pilot_native['records'][i].copy(), native['records'][i].copy()
        a.pop('execute_end_CPU_s'); b.pop('execute_end_CPU_s')
        checks.append(dict(entry=i, native_exact=a == b,
            paired_exact=pilot_pairs[i] == pairs[i],
            RNG_before_after_exact=all(pilot_seeds['records'][i][key] == full_seeds['records'][i][key]
                                      for key in ['run', 'event', 'roots', 'seeds', 'before', 'after'])))
    repro = dict(N=4, checks=checks, passed=all(all(row[k] for k in ['native_exact', 'paired_exact', 'RNG_before_after_exact']) for row in checks))
    assert repro['passed'], repro
covs = [row['covariance_QA'] for row in pairs if row['covariance_QA']['finite']]
sigmas = np.asarray([row['sigma'] for row in covs])
tangent = []
for event, pair in zip(native['records'], pairs):
    k = pair['leading_index']
    if k is None or not pair['covariance_QA']['finite']:
        continue
    track = event['tracks'][k]
    phi, theta, qop = track['parameters'][2:]
    if qop == 0 or track['state'][5] <= 0:
        continue
    matrix = np.asarray(track['covariance']).reshape(5, 5)
    jacobian = np.zeros((3, 5))
    jacobian[0, 2], jacobian[0, 3] = -np.sin(phi)*np.tan(theta), np.cos(phi)/np.cos(theta)**2
    jacobian[1, 2], jacobian[1, 3] = np.cos(phi)*np.tan(theta), np.sin(phi)/np.cos(theta)**2
    jacobian[2, 3], jacobian[2, 4] = -np.tan(theta), -1/qop
    propagated = jacobian@matrix@jacobian.T
    tangent.append(dict(entry=event['entry'], pz0_GeV=track['state'][5]/1000,
        sigma_tx=float(np.sqrt(propagated[0, 0])), sigma_ty=float(np.sqrt(propagated[1, 1])),
        sigma_logpz0=float(np.sqrt(propagated[2, 2])),
        scope='Local first-order propagation of uncalibrated fitted covariance; no truth pull or coverage claim'))
with (OUT/'tangent_covariance.tsv').open('w') as stream:
    import csv
    writer = csv.DictWriter(stream, fieldnames=list(tangent[0]), delimiter='\t', lineterminator='\n')
    writer.writeheader(); writer.writerows(tangent)
readouts = [v for event in pairs for v in event['readout']]
leading_states = [event['tracks'][pair['leading_index']]['state'] for event, pair in zip(native['records'], pairs)
                  if pair['leading_index'] is not None]
typed = dict(signed_raw_charge_exact_minus1_N=sum(v['stored']['raw_charge'] == -1 for v in readouts),
    raw_charge_negative_N=sum(v['stored']['raw_charge'] < 0 for v in readouts),
    numeric_raw_sentinel_N=sum(v['stored']['raw_charge'] in [-999, -9999, -99999] for v in readouts),
    positive_baselineRMS_minus1_N=sum(v['stored']['baseline_rms'] == -1 for v in readouts),
    absent_native_channel_views_N=sum(not v['native_present'] for v in readouts),
    missing_measured_raw_N=sum(v['raw_charge_pC'] is None for v in readouts),
    nonzero_status_finite_native_localtime_N=sum(v['status'] != 0 and v['localtime'] is not None
                                              for event in native['records'] for v in event['waves']),
    negative_leading_chi2_N=sum(s[7] < 0 for s in leading_states))
assert typed['nonzero_status_finite_native_localtime_N'] == 0
report = dict(phase=phase, independent_parent_N=len(pairs), repeat_N=4 if phase == 'full' else 0,
    failed_first_attempt_physical_prefix_N=4, failed_infrastructure_attempt_physical_N=0,
    unique_original_entries=len(pairs), actual_physical_entry_executions=len(pairs)+(8 if phase == 'full' else 4),
    duplicate_original_entry_executions=8 if phase == 'full' else 4,
    current_summary=json.loads((OUT/phase/'summary.json').read_text()), prefix_reproducibility=repro,
    raw_status_by_name={name: {str(status): sum(v['name'] == name and v['status'] == status for v in readouts)
                             for status in sorted(set(v['status'] for v in readouts if v['name'] == name))}
                        for name in sorted(set(v['name'] for v in readouts))},
    typed_QA=typed, control_reference_z_mm_range=[min(s[2] for s in leading_states), max(s[2] for s in leading_states)],
    selection_migration={f'old{a}_new{b}': sum(r['old_selected'] == bool(a) and r['new_selected'] == bool(b) for r in pairs)
                         for a in [0, 1] for b in [0, 1]},
    selected_pz0_50_100_N=sum(r['new_selected'] and 50 < event['tracks'][r['leading_index']]['state'][5]/1000 < 100
                            for event, r in zip(native['records'], pairs) if r['leading_index'] is not None),
    sigma_basis=native['basis'], sigma_min=sigmas.min(0).tolist(), sigma_median=np.median(sigmas, axis=0).tolist(),
    sigma_max=sigmas.max(0).tolist(), covariance_parameter_types=sorted(set(t['parameter_type'] for r in native['records'] for t in r['tracks'])),
    leading_offdiagonal_nonzero_N=sum(r['offdiagonal_N'] for r in covs),
    leading_max_abs_offdiagonal_correlation_min=min(r['max_abs_offdiagonal_correlation'] for r in covs),
    leading_max_abs_offdiagonal_correlation_median=float(np.median([r['max_abs_offdiagonal_correlation'] for r in covs])),
    leading_max_abs_offdiagonal_correlation_max=max(r['max_abs_offdiagonal_correlation'] for r in covs),
    tangent_N=len(tangent), tangent_sigma_basis=['tx', 'ty', 'log(pz0)'],
    tangent_sigma_min=np.min([[r[k] for k in ['sigma_tx', 'sigma_ty', 'sigma_logpz0']] for r in tangent], axis=0).tolist(),
    tangent_sigma_median=np.median([[r[k] for k in ['sigma_tx', 'sigma_ty', 'sigma_logpz0']] for r in tangent], axis=0).tolist(),
    tangent_sigma_max=np.max([[r[k] for k in ['sigma_tx', 'sigma_ty', 'sigma_logpz0']] for r in tangent], axis=0).tolist(),
    surface_types=sorted(set(t['surface_type'] for r in native['records'] for t in r['tracks'])),
    native_clusters_N=sum(sum(r['clusters']) for r in native['records']),
    native_measurements_N=sum(r['measurements'] for r in native['records']),
    missing_measurement_links_N=sum(r['measurementMissing'] for r in native['records']),
    missing_raw_strip_links_N=sum(r['rawMissing'] for r in native['records']),
    invalidStrip_N=sum(r['invalidStrip'] for r in native['records']),
    cluster_ownership_columns=['leading_owned', 'other_owned', 'shared_by_multiple_tracks', 'unassigned'],
    ownership_sum_by_station=np.sum([r['ownership_by_station'] for r in native['records']], axis=0).tolist(),
    new_G4=0, energy_fits=0, score_refits=0, reserved_forward=0, GPU=0,
    covariance_calibration_measured=False, association_posterior_measured=False, data_transfer_certified=False,
    CPU_s=time.process_time()-cpu, wall_s=time.perf_counter()-tick,
    RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, overall_complete=False)
(OUT/'summary.json').write_text(json.dumps(report, indent=2)+'\n')
print(admission, report, flush=True)
