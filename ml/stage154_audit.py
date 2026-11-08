"""Actual geometry/identity support, admission and fixed-summary audit; batch only."""
import csv
import gzip
import json
import re
import resource
import time
from pathlib import Path
import numpy as np

OUT = Path('workbook/stage154_energy_ml')
CACHE = Path('ntuples/energy_ml_stage154')
cpu, tick = time.process_time(), time.perf_counter()
plan = json.loads((OUT/'protocol.json').read_text())
pilot = json.loads((OUT/'pilot_summary.json').read_text())
account = json.loads((OUT/'scheduler_accounting.json').read_text())
text = (OUT/'pilot_time.txt').read_text()
GNU_CPU = sum(float(re.search(r'(?m)^\s*'+re.escape(k)+r': (\S+)', text).group(1))
              for k in ['User time (seconds)', 'System time (seconds)'])
event = sum(pilot['event_CPU_s'])
startup = max(0, GNU_CPU-event)
projection = 3*(startup+10*event)
physical = pilot['passed'] and pilot['N'] == pilot['leading_identity_known_N'] == pilot['exact_old_count_N']
physical = physical and pilot['same_process_first_parent_repeat'] and pilot['native_support']
admission = dict(admitted=physical and projection+100 < 1200-account['total_CPU_s'],
    physical_pilot_support=bool(physical), already_used_scheduler_CPU_s=account['total_CPU_s'],
    GNU_pilot_CPU_s=GNU_CPU, pilot_execute_CPU_s=event, startup_CPU_s=startup,
    full40_3x_affine_projected_CPU_s=projection, audit_reserve_CPU_s=100,
    remaining_CPU_s=1200-account['total_CPU_s'], overlapping_pilot_N=4, parent_cap=40,
    limitation='Four ordered event execute times estimate event cost; startup retained; this is an admission projection, not a measured full runtime.')
if (OUT/'full_admission.json').exists():
    admission = json.loads((OUT/'full_admission.json').read_text())
else:
    (OUT/'full_admission.json').write_text(json.dumps(admission, indent=2)+'\n')
phase = 'full' if (OUT/'full_summary.json').exists() else 'pilot'
native = json.loads((OUT/f'{phase}_summary.json').read_text())
with gzip.open(CACHE/f'{phase}.json.gz', 'rt') as stream:
    payload = json.load(stream)
records = payload['records']
# Diagnostics only: never alter the frozen geometry tolerance or availability.
# The inspected p2 converter stores global positions in vector<float>. Test
# compatibility on the already bounded QA excerpt, not an asserted producer ID.
precision_QA = []
for parent in payload['QA']:
    for anchor in parent['anchors']:
        if len(anchor['global_position_mm']) != 3 or len(anchor['transform']) != 16:
            continue
        g = np.array(anchor['global_position_mm'])
        f = g.astype(np.float32)
        prev = np.nextafter(f, np.float32(-np.inf)).astype(np.float64)
        nxt = np.nextafter(f, np.float32(np.inf)).astype(np.float64)
        lo, hi = (prev+f.astype(np.float64))/2, (nxt+f.astype(np.float64))/2
        transform = np.array(anchor['transform']).reshape(4, 4)
        normal = transform[:3, 2]
        lower = anchor['normal_mm']+np.minimum(normal*(lo-g), normal*(hi-g)).sum()
        upper = anchor['normal_mm']+np.maximum(normal*(lo-g), normal*(hi-g)).sum()
        precision_QA.append(dict(entry=parent['entry'], wafer=anchor['wafer'],
            global_coordinates_exact_float32=bool(np.array_equal(g, f.astype(np.float64))),
            actual_normal_mm=anchor['normal_mm'], original_geometry_valid=anchor['valid'],
            float32_rounding_compatible_normal_interval_mm=[float(lower), float(upper)],
            exact_plane_compatible_with_float32_rounding=bool(lower <= 0 <= upper)))
request = json.loads(Path(plan['input_native_request']).read_text())['requests'][0]
expected = sorted((r for r in request['cases'] if r['role'] == 1), key=lambda r: r['entry'])[:40 if phase == 'full' else 4]
assert len(records) == len(expected) == native['N'] and len(payload['QA']) <= 4
for actual, original in zip(records, expected):
    assert all(actual[k] == original[k] for k in ['row', 'entry', 'run', 'event', 'role'])
    assert actual['old_counts_exact']
    if actual['independent_dx_max_delta_mm'] is not None:
        assert actual['independent_dx_max_delta_mm'] <= 1e-8
repro = None
if phase == 'full':
    with gzip.open(CACHE/'pilot.json.gz', 'rt') as stream:
        prefix = json.load(stream)
    checks = []
    for a, b in zip(prefix['records'], records):
        a, b = a.copy(), b.copy()
        a.pop('execute_CPU_s'); b.pop('execute_CPU_s')
        assert a == b
        checks.append(dict(entry=a['entry'], exact=True))
    assert prefix['QA'] == payload['QA']
    repro = dict(N=4, records_exact=True, QA_exact=True, checks=checks)

def extent(values):
    v = [x for x in values if x is not None]
    return dict(N=len(v), min=min(v) if v else None, max=max(v) if v else None, distinct_N=len(set(v)))

stations = []
keys = ['clusters', 'leadingOwned', 'nonleading', 'offMeasuredWafer', 'onMeasuredWafer',
        'measuredWafers', 'eligibleWafers', 'duplicateAnchors', 'eligibleCandidates',
        'candidateSurfaceMismatch', 'candidateInvalidLocal', 'unusableAnchorCandidates',
        'candidateMissingElement', 'candidateInvalidRDO', 'candidateRoundtripFailure']
for station in range(4):
    rows = [r['stations'][station] for r in records]
    for s in rows:
        assert s['clusters'] == s['leadingOwned']+s['nonleading']
        assert s['nonleading'] == s['offMeasuredWafer']+s['onMeasuredWafer']
        assert s['onMeasuredWafer'] == sum(s[k] for k in ['eligibleCandidates']+keys[9:])
        if not s['available']:
            assert all(s[k] is None for k in ['candidate_N', 'mean_abs_dx_mm', 'min_abs_dx_mm', 'max_abs_dx_mm', 'RMS_dx_mm'])
    stations.append(dict(station=station, available_parent_N=sum(s['available'] for s in rows),
        nonzero_candidate_parent_N=sum(s['eligibleCandidates'] > 0 for s in rows),
        **{k: sum(s[k] for s in rows) for k in keys},
        feature_ranges={k: extent([s[k] for s in rows]) for k in
            ['candidate_N', 'mean_abs_dx_mm', 'min_abs_dx_mm', 'max_abs_dx_mm', 'RMS_dx_mm']}))
with (OUT/'station_support.tsv').open('w') as stream:
    flat = [{k: v for k, v in s.items() if k != 'feature_ranges'} for s in stations]
    writer = csv.DictWriter(stream, fieldnames=list(flat[0]), delimiter='\t', lineterminator='\n')
    writer.writeheader(); writer.writerows(flat)
summary = dict(passed=True, phase=phase, N=len(records), original_identities_exact=True,
    leading_identity_known_N=native['leading_identity_known_N'], first_parent_repeat_exact=True,
    anchors={k: sum(r['anchor_counts'][k] for r in records) for k in records[0]['anchor_counts']},
    diagnostics={k: extent([r[k] for r in records]) for k in ['max_abs_normal_mm',
        'max_state_roundtrip_mm', 'max_PRD_roundtrip_mm', 'independent_dx_max_delta_mm', 'max_candidate_roundtrip_mm']},
    stations=stations, new_geometry_content_support=native['native_support'],
    prefix_reproducibility=repro, native_resources=native,
    precision_QA_diagnostic=precision_QA,
    precision_QA_scope='At most4 QA parents and4anchors each; does not change the frozen1e-6mm criterion or certify historical producer/schema.',
    calibrated_covariance=False, calibrated_association=False, population_muon_FPR_measured=False,
    CPU_s=time.process_time()-cpu, wall_s=time.perf_counter()-tick,
    RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    new_G4=0, fits=0, promotion=False, overall_complete=False)
(OUT/'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False)+'\n')
print('ADMISSION', admission, 'SUMMARY', summary, flush=True)
