"""Worker-only compact-state/native-plane feasibility before any replay."""
import json
import time
import numpy as np
from stage178_common import ROOT, OUT, CACHE, boxes, bounds, signs, classify, read_gz

start = time.perf_counter()
records = boxes()
box = next(r for r in records if r['index'] == 50)
native = json.loads((ROOT / 'workbook/stage176_energy_ml/parent_50_S0.json').read_text())
assert native['native_S0_supported'] and box['supported']
surface = native['surface']
assert surface['center_mm'] == surface['xyz_mm']
for key, values in [('xyz_mm_intervals', surface['xyz_mm']), ('momentum_MeV_intervals', surface['px_py_pz_MeV']), ('normal_intervals', surface['normal'])]:
    interval = np.asarray(box[key]); values = np.asarray(values)
    assert np.all(interval[:,0] <= values) and np.all(values <= interval[:,1]), (key, values, interval)
raw = read_gz(ROOT / 'ntuples/energy_ml_stage176/parent_50_lineage.json.gz')
report = classify(50, raw, box)
points = [b['xyz_mm'] for b in raw['muon_births']] + [s[a:a+3] for s in raw['muon_segments'] for a in [1,4]]
intervals = bounds(points, box); robust = signs(intervals)
native_side = np.sign((np.asarray(points)-surface['center_mm']) @ np.asarray(surface['normal']))
assert np.array_equal(robust[robust != 0], native_side[robust != 0])
birth_sides = [r['side'] for r in report['births']]
assert 'before_S0' in birth_sides and 'after_S0' in birth_sides
assert [r['ordinal'] for r in report['robust_crossings']] == [r['ordinal'] for r in native['crossings']]
for name, part in report['hit_source_partition'].items():
    assert part['hit_counts'] == native['hit_source_partition'][name]['hit_counts']
    assert part['corrected_SD_response_MeV'] == native['hit_source_partition'][name]['corrected_SD_response_MeV']
(OUT / 'state_boxes.json').write_text(json.dumps(records, indent=2) + '\n')
(OUT / 'parent_50_intervals.json').write_text(json.dumps(report, separators=(',',':')) + '\n')
summary = dict(passed=True, original_parents_N=len(records), state_supported_N=sum(r['supported'] for r in records),
    unknown_state_indices=[r['index'] for r in records if not r['supported']], native_state_and_normal_enclosed=True,
    native_points_checked=len(points), robust_native_points_N=int(np.sum(robust != 0)), unknown_native_points_N=int(np.sum(robust == 0)),
    robust_birth_counts={k:birth_sides.count(k) for k in sorted(set(birth_sides))}, robust_crossings_N=len(report['robust_crossings']),
    source_partition_exact=True, wall_s=time.perf_counter()-start, new_G4=0, energy_fits=0, overall_complete=False)
(OUT / 'feasibility_summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(summary, flush=True)
