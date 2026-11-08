"""Fixed native pilot accounting and physical basis audit; batch only."""
import csv
import gzip
import json
import resource
import time
from pathlib import Path

OUT = Path('workbook/stage153_energy_ml')
CACHE = Path('ntuples/energy_ml_stage153')
cpu, tick = time.process_time(), time.perf_counter()
plan = json.loads((OUT/'protocol.json').read_text())
native = json.loads((OUT/'native_summary.json').read_text())
request = json.loads(Path(plan['input_native_request']).read_text())['requests'][0]
expected = sorted((r for r in request['cases'] if r['role'] == 1), key=lambda r: r['entry'])[:40]
with gzip.open(CACHE/'native.json.gz', 'rt') as stream:
    payload = json.load(stream)
records = payload['records']
assert len(records) == len(expected) == native['N']
assert len(payload['QA']) <= 4
assert native['passed'] and native['same_process_first_parent_repeat']
for actual, original in zip(records, expected):
    assert all(actual[k] == original[k] for k in ['row', 'entry', 'run', 'event', 'role'])
    assert actual['old_counts_exact']
    for s in actual['stations']:
        assert s['clusters'] == s['leadingOwned']+s['nonleading']
        assert s['nonleading'] == s['offMeasuredWafer']+s['onMeasuredWafer']
        if not s['available']:
            assert all(s[k] is None for k in ['candidate_N', 'mean_exp_minus_half_r2', 'mean_log1p_r2', 'max_log1p_r2'])

def extent(values):
    v = [x for x in values if x is not None]
    return dict(N=len(v), min=min(v) if v else None, max=max(v) if v else None,
                distinct_N=len(set(v)))

stations = []
for station in range(4):
    rows = [r['stations'][station] for r in records]
    keys = ['clusters', 'leadingOwned', 'nonleading', 'offMeasuredWafer', 'onMeasuredWafer',
            'measuredWafers', 'eligibleWafers', 'duplicateAnchors', 'eligibleCandidates',
            'candidateSurfaceMismatch', 'candidateInvalidVariance', 'unusableAnchorCandidates',
            'candidateMissingElement', 'candidateInvalidRDO']
    stations.append(dict(station=station, available_parent_N=sum(s['available'] for s in rows),
        nonzero_candidate_parent_N=sum(s['eligibleCandidates'] > 0 for s in rows),
        **{k: sum(s[k] for s in rows) for k in keys},
        feature_ranges={k: extent([s[k] for s in rows]) for k in
            ['candidate_N', 'mean_exp_minus_half_r2', 'mean_log1p_r2', 'max_log1p_r2']}))
with (OUT/'station_support.tsv').open('w') as stream:
    flat = [{k: v for k, v in s.items() if k != 'feature_ranges'} for s in stations]
    writer = csv.DictWriter(stream, fieldnames=list(flat[0]), delimiter='\t', lineterminator='\n')
    writer.writeheader()
    writer.writerows(flat)
anchor_totals = {k: sum(r['anchor_counts'][k] for r in records) for k in records[0]['anchor_counts']}
invalid = {k: sum(r['anchor_invalid_reasons'][k] for r in records) for k in records[0]['anchor_invalid_reasons']}
support = any(s['eligibleCandidates'] for s in stations[1:])
summary = dict(passed=True, N=len(records), original_identities_exact=True,
    leading_identity_known_N=sum(r['leading_identity_known'] for r in records),
    first_parent_repeat_exact=True, anchors=anchor_totals, overlapping_invalid_reasons=invalid,
    anchor_surface_types=sorted(set(tuple(t) for r in records for t in r['anchor_surface_types'])),
    max_anchor_transform_difference=extent([r['max_anchor_transform_difference'] for r in records]),
    state_roundtrip_mm=extent([r['max_state_roundtrip_mm'] for r in records]),
    candidate_roundtrip_mm=extent([r['max_candidate_roundtrip_mm'] for r in records]),
    independent_r2_max_delta=max(r['independent_scaled_separation_max_delta'] for r in records),
    stations=stations, new_spatial_measurement_support=support,
    result='same-surface candidate support exists; separate control contract required' if support else
        'fixed same-surface implementation has no supported candidates; no expansion or energy fit',
    native_resources=native, CPU_s=time.process_time()-cpu, wall_s=time.perf_counter()-tick,
    RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    new_G4=0, fits=0, calibrated_association=False, calibrated_pull=False,
    population_muon_FPR_measured=False, promotion=False, overall_complete=False)
(OUT/'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False)+'\n')
print('SUMMARY', summary, flush=True)
