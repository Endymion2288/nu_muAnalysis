"""Independent rational-arithmetic enclosures and scalar source bookkeeping."""
import csv
import gzip
import json
import math
from fractions import Fraction as F
from pathlib import Path

ROOT = Path.cwd()
OUT = ROOT / 'workbook/stage178_energy_ml'
CACHE = ROOT / 'ntuples/energy_ml_stage178'
p = json.loads((OUT / 'protocol.json').read_text())
boxes = {r['index']:r for r in json.loads((OUT / 'state_boxes.json').read_text())}
checks = []; parent_rows = []; source_rows = []

def read_gz(path):
    with gzip.open(path, 'rt') as stream:
        return json.load(stream)

def rational_bound(point, box):
    lower = F(0); upper = F(0)
    for coordinate, center, momentum in zip(point, box['xyz_mm_intervals'], box['momentum_MeV_intervals']):
        d = [F(coordinate)-F(center[1]), F(coordinate)-F(center[0])]
        products = [a * F(b) for a in d for b in momentum]
        lower += min(products); upper += max(products)
    return lower, upper

cases = {r['frame_index']:r for r in read_gz(ROOT / 'ntuples/energy_ml_stage131/production_cases.json.gz')}
for index in [p['reference_index']] + p['replay_indices']:
    original = index == p['reference_index']
    folder = ROOT / 'ntuples/energy_ml_stage176' if original else CACHE
    raw = read_gz(folder / f'parent_{index}_lineage.json.gz')
    saved = read_gz(folder / f'parent_{index}_qa_hits.json.gz')
    report = json.loads((OUT / f'parent_{index}_intervals.json').read_text())
    box = boxes[index]
    if not original:
        assert json.loads((OUT / f'parent_{index}_report.json').read_text())['legacy_fields_exact']
    groups = {0:'primary_muon_direct', -1:'other_root', -2:'unknown_root'}
    exact_bounds_checked = 0; born = {}; crossings = []; unknown_endpoints = 0
    primary = raw['muon_primaries']
    valid = box['supported'] and len(primary) == 1
    if valid:
        pmid = [sum(a)/2 for a in box['momentum_MeV_intervals']]
        valid = sum(a*b for a,b in zip(pmid, primary[0][5:8])) > 0
    assert bool(valid) == report['state_supported']
    for birth, observed in zip(raw['muon_births'], report['births']):
        tag = 'unknown_S0'
        if valid:
            lo, hi = rational_bound(birth['xyz_mm'], box)
            interval = observed['sign_interval_MeV_mm']
            assert F(interval[0]) <= lo <= hi <= F(interval[1])
            exact_bounds_checked += 1
            # If float outward arithmetic includes zero, retain unknown even if exact arithmetic could refine it.
            tag = 'before_S0' if interval[1] < 0 else 'after_S0' if interval[0] > 0 else 'unknown_S0'
        assert observed['group'] == birth['group'] and observed['side'] == tag
        groups[birth['group']] = tag
        key = tag + ':' + birth['process'] + ':' + str(birth['pdg'])
        born[key] = born.get(key, 0) + 1
    assert len(raw['muon_births']) == len(report['births'])
    assert born == report['birth_process_side_counts']
    reported_crossings = {c['ordinal']:c for c in report['robust_crossings']}
    for ordinal, segment in enumerate(raw['muon_segments']):
        if len(primary) != 1 or int(segment[0]) != int(primary[0][0]):
            continue
        sides = []
        for xyz in [segment[1:4], segment[4:7]]:
            if not valid:
                side = 0
            else:
                lo, hi = rational_bound(xyz, box)
                side = -1 if hi < 0 else 1 if lo > 0 else 0
                exact_bounds_checked += 1
            sides.append(side)
        unknown_endpoints += sum(s == 0 for s in sides)
        if sides[0]*sides[1] == -1:
            crossings.append(ordinal)
            if ordinal in reported_crossings:
                observed = reported_crossings[ordinal]
                for xyz, interval in zip([segment[1:4], segment[4:7]], observed['endpoint_intervals_MeV_mm']):
                    lo, hi = rational_bound(xyz, box)
                    assert F(interval[0]) <= lo <= hi <= F(interval[1])
                assert observed['forward'] == (sides[0] < 0)
                assert observed['pre_post_total_energy_MeV'] == segment[7:9]
    # Exact rational bounds may resolve a boundary that outward float leaves unknown; never silently add a crossing.
    assert set(reported_crossings) <= set(crossings)
    for name, hits in raw['daq_hits'].items():
        assert len(hits) == len(saved[name]) == len(raw['daq_birth_groups'][name])
        counts = {}; energies = {}
        for hit, persist, group in zip(hits, saved[name], raw['daq_birth_groups'][name]):
            assert hit[4] == persist[0] and hit[7] == persist[3]
            assert abs(hit[5]-persist[1]) <= 1.1e-5 + abs(hit[5])*2e-7
            tag = groups[group]
            counts[tag] = counts.get(tag, 0) + 1
            energies.setdefault(tag, []).append(hit[5])
        expected = report['hit_source_partition'][name]
        assert counts == expected['hit_counts']
        for tag, values in energies.items():
            energy = math.fsum(values)
            assert abs(energy-expected['corrected_SD_response_MeV'][tag]) <= 1e-10*max(1, abs(energy))
            source_rows.append(dict(index=index, detector=name, source=tag, hits_N=counts[tag], corrected_SD_MeV=energy))
    counts = {side:sum(v for k,v in born.items() if k.startswith(side+':')) for side in ['before_S0', 'after_S0', 'unknown_S0']}
    parent_rows.append(dict(index=index, state_supported=valid, births_N=len(raw['muon_births']),
        before_births_N=counts['before_S0'], after_births_N=counts['after_S0'], unknown_births_N=counts['unknown_S0'],
        robust_crossings_N=len(report['robust_crossings']), forward_N=sum(c['forward'] for c in report['robust_crossings']),
        unknown_segment_endpoints=report['unknown_segment_endpoints'], actual_primary_initial_E_GeV=primary[0][8]/1000 if len(primary)==1 else None,
        sampling_stratum=cases[index]['stratum'], truth_E_GeV=cases[index]['truth_E_GeV'],
        component=cases[index]['component'], unknown_reason=box.get('reason')))
    checks.append(dict(index=index, passed=True, rational_bounds_N=exact_bounds_checked,
        source_partition_exact=True, ordered_hits_exact=True, births_N=len(raw['muon_births'])))
for name, rows in [('parent_support.tsv', parent_rows), ('source_response.tsv', source_rows)]:
    with (OUT / name).open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter='\t', lineterminator='\n', quoting=csv.QUOTE_NONNUMERIC)
        writer.writeheader(); writer.writerows(rows)
summary = dict(passed=True, parents_N=len(parent_rows), state_supported_N=sum(r['state_supported'] for r in parent_rows),
    unknown_state_indices=[r['index'] for r in parent_rows if not r['state_supported']],
    births_N=sum(r['births_N'] for r in parent_rows), robust_before_births_N=sum(r['before_births_N'] for r in parent_rows),
    robust_after_births_N=sum(r['after_births_N'] for r in parent_rows), unknown_births_N=sum(r['unknown_births_N'] for r in parent_rows),
    robust_crossings_N=sum(r['robust_crossings_N'] for r in parent_rows),
    rational_bounds_N=sum(r['rational_bounds_N'] for r in checks), source_table_rows_N=len(source_rows),
    old_observer_and_ordered_hits_exact=True, replay_G4_N=len(p['replay_indices']), reconstruction_N=0,
    energy_fits=0, new_independent_nu=0, overall_complete=False, scope='Fixed conditional train pilot, not an unbiased physics population or same-window DAQ response.')
(OUT / 'independent_validation.json').write_text(json.dumps(dict(passed=True, parents=checks), indent=2) + '\n')
(OUT / 'physical_summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(summary, flush=True)
