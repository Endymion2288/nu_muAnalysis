"""Batch-only paired muon spatial control and prospective child-CPU admission."""
import csv
import gzip
import json
import math
import re
import resource
import time
from pathlib import Path
import numpy as np

OUT = Path('workbook/stage156_energy_ml')
CACHE = Path('ntuples/energy_ml_stage156')
cpu, tick = time.process_time(), time.perf_counter()
plan = json.loads((OUT/'protocol.json').read_text())
account = json.loads((OUT/'scheduler_accounting.json').read_text())


def load(path):
    with gzip.open(path, 'rt') as stream:
        return json.load(stream)


def exact(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(exact(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(exact(x, y) for x, y in zip(a, b))
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    return a == b


def timing(path):
    text = path.read_text()
    return sum(float(re.search(r'(?m)^\s*'+re.escape(k)+r': (\S+)', text).group(1))
               for k in ['User time (seconds)', 'System time (seconds)'])


def numbers(values):
    a = np.asarray([v for v in values if v is not None and math.isfinite(v)], dtype=float)
    return dict(N=len(a), min=float(a.min()), median=float(np.median(a)), mean=float(a.mean()),
                max=float(a.max()), RMS=float(np.sqrt(np.mean(a*a)))) if len(a) else dict(N=0)


def table(path, rows):
    with path.open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter='\t', lineterminator='\n')
        writer.writeheader()
        writer.writerows({k: 'NA' if v is None else json.dumps(v, separators=(',', ':')) if isinstance(v, dict) else v
                          for k, v in row.items()} for row in rows)


reference = load(plan['reference_current'])
ref_native = json.loads(reference['ntuples/energy_ml_stage149/full/native.json.gz'])
ref_pairs = json.loads(reference['ntuples/energy_ml_stage149/full/paired.json.gz'])
ref_seeds = json.loads(reference['workbook/stage149_energy_ml/full/seeds.json'])
phase = 'full' if (OUT/'full/summary.json').exists() else 'pilot'
native = load(CACHE/phase/'native.json.gz')
pairs = load(CACHE/phase/'paired.json.gz')
seeds = json.loads((OUT/phase/'seeds.json').read_text())
schema = json.loads((OUT/phase/'schema.json').read_text())
assert schema['verified']
assert len(native['records']) == len(pairs) == len(seeds['records']) == (64 if phase == 'full' else 4)
assert native['configured_conditions'] == dict(conditions='OFLCOND-FASER-06', geometry='FASERNU-04')
assert seeds['conditions'] == ref_seeds['conditions'] == 'OFLCOND-FASER-06'
assert seeds['geometry'] == ref_seeds['geometry'] == 'FASERNU-04'
assert native['cable_mapping'] == ref_native['cable_mapping']
paired_checks = []
for i, (record, pair, seed) in enumerate(zip(native['records'], pairs, seeds['records'])):
    previous = ref_native['records'][i]
    without_new = {k: v for k, v in record.items() if k not in ['geometry', 'geometry_QA', 'execute_end_CPU_s']}
    previous = {k: v for k, v in previous.items() if k != 'execute_end_CPU_s'}
    checks = dict(entry=i, native_state_covariance_PRD_counts_raw_exact=exact(without_new, previous),
                  paired_identity_readout_presence_exact=exact(pair, ref_pairs[i]),
                  roots_seed_RNG_before_after_exact=all(exact(seed[k], ref_seeds['records'][i][k])
                      for k in ['run', 'event', 'roots', 'seeds', 'before', 'after']))
    assert all(v for k, v in checks.items() if k != 'entry'), checks
    paired_checks.append(checks)
    g = record['geometry']
    assert (g['entry'], g['run'], g['event']) == (i, pair['run'], pair['event'])
    assert g['role'] == 'muon_control'
    assert g['leading_identity_known'] == (pair['leading_index'] is not None)
    if g['independent_dx_max_delta_mm'] is not None:
        assert g['independent_dx_max_delta_mm'] <= 1e-8
    if g['max_state_roundtrip_mm'] is not None:
        assert g['max_state_roundtrip_mm'] <= 1e-8
    assert g['anchor_counts']['valid'] == g['anchor_counts']['total']
    for s in g['stations']:
        assert s['clusters'] == s['leadingOwned']+s['nonleading']
        assert s['nonleading'] == s['onMeasuredWafer']+s['offMeasuredWafer']
        assert s['onMeasuredWafer'] == sum(s[k] for k in ['eligibleCandidates', 'candidateSurfaceMismatch',
            'unusableAnchorCandidates', 'candidateMissingElement', 'candidateInvalidRDO', 'candidateInvalidLocal', 'candidateRoundtripFailure'])
        if not s['available']:
            assert s['candidate_N'] is None
        if s['eligibleCandidates'] == 0:
            assert s['mean_abs_dx_mm'] is None
assert native['records'][0]['geometry']['same_process_native_repeat_exact']
table(OUT/'paired_checks.tsv', paired_checks)

pilot_native = load(CACHE/'pilot/native.json.gz')
pilot_seeds = json.loads((OUT/'pilot/seeds.json').read_text())
ends = dict(digi=[r['execute_end_CPU_s'] for r in pilot_seeds['records']],
            reco=json.loads((OUT/'pilot/reco_timing.json').read_text())['event_end_CPU_s'],
            native=[r['execute_end_CPU_s'] for r in pilot_native['records']])
costs = []
for name, times in ends.items():
    total = timing(OUT/f'pilot/{name}_time.txt')
    assert len(times) == 4 and times[-1] >= times[0]
    post = times[-1]-times[0]
    projected = total+60*post/3
    costs.append(dict(step=name, GNU_CPU4_s=total, first_event_end_CPU_s=times[0],
        fourth_event_end_CPU_s=times[-1], post_first3_CPU_s=post, projected64_CPU_s=projected))
extract4 = timing(OUT/'pilot/extract_time.txt')
projection = 3*(sum(r['projected64_CPU_s'] for r in costs)+16*extract4)
physical = phase == 'full' or (len(pairs) == 4 and schema['verified'] and
    any(s['eligibleWafers'] for r in native['records'] for s in r['geometry']['stations']))
if not (OUT/'full_admission.json').exists():
    admission = dict(admitted=bool(physical and projection+150 < 3000-account['total_CPU_s']),
        physical_support=bool(physical), positive_candidate_required=False, costs=costs,
        GNU_extract4_CPU_s=extract4, projected_extract64_CPU_s=16*extract4,
        full64_factor3_projected_CPU_s=projection, audit_reserve_CPU_s=150,
        already_used_scheduler_CPU_s=account['total_CPU_s'], remaining_CPU_s=3000-account['total_CPU_s'],
        pilot_parent_N=4, full_parent_cap=64, prefix_overlap_N=4,
        scope='Measured GNU child totals plus post-first event process CPU; first/lazyJIT retained. Prospective cost, not measured full throughput.')
    (OUT/'full_admission.json').write_text(json.dumps(admission, indent=2)+'\n')
else:
    admission = json.loads((OUT/'full_admission.json').read_text())
repro = None
if phase == 'full':
    pilot_pairs = load(CACHE/'pilot/paired.json.gz')
    checks = []
    for i in range(4):
        a, b = pilot_native['records'][i].copy(), native['records'][i].copy()
        a.pop('execute_end_CPU_s'); b.pop('execute_end_CPU_s')
        checks.append(dict(entry=i, native_geometry_raw_exact=exact(a, b),
            paired_exact=exact(pilot_pairs[i], pairs[i]), RNG_exact=all(exact(pilot_seeds['records'][i][k], seeds['records'][i][k])
                for k in ['run', 'event', 'roots', 'seeds', 'before', 'after'])))
    a, b = json.loads((OUT/'pilot/schema.json').read_text()), schema.copy()
    a.pop('REC'); b.pop('REC')
    assert exact(a, b)
    assert all(all(v for k, v in row.items() if k != 'entry') for row in checks)
    repro = dict(passed=True, N=4, schema_exact_except_scratch_path=True, checks=checks)
raw15 = ['VetoNu0','VetoNu1','Veto10','Veto20','Veto21','Timing0','Timing1','Timing2','Timing3','Preshower0','Preshower1']+[f'Calo{i}' for i in range(4)]
strata = dict(all=list(range(len(pairs))), current_leading=[i for i,p in enumerate(pairs) if p['leading_index'] is not None],
    pz0_50_100=[i for i,p in enumerate(pairs) if p['leading_index'] is not None and
        50 <= native['records'][i]['tracks'][p['leading_index']]['state'][5]/1000 < 100],
    any_raw15_overflow=[i for i,p in enumerate(pairs) if any(v['name'] in raw15 and v['status'] & 4 for v in p['readout'])])
station_rows, stratum_summary = [], {}
keys = ['clusters','leadingOwned','nonleading','offMeasuredWafer','onMeasuredWafer','measuredWafers','eligibleWafers',
    'duplicateAnchors','eligibleCandidates','candidateSurfaceMismatch','unusableAnchorCandidates','candidateMissingElement',
    'candidateInvalidRDO','candidateInvalidLocal','candidateRoundtripFailure']
features = ['candidate_N','mean_abs_dx_mm','min_abs_dx_mm','max_abs_dx_mm','RMS_dx_mm']
for label, indices in strata.items():
    rows = [native['records'][i]['geometry'] for i in indices]
    support = []
    for station in range(4):
        srows = [r['stations'][station] for r in rows]
        counts = dict(stratum=label, N=len(rows), station=station,
            available_parent_N=sum(s['available'] for s in srows),
            nonzero_parent_N=sum(s['eligibleCandidates'] > 0 for s in srows),
            **{k: sum(s[k] for s in srows) for k in keys})
        station_rows.append(counts)
        support.append(dict(**counts, distributions={k:numbers([s[k] for s in srows]) for k in features}))
    stratum_summary[label] = dict(N=len(rows), entries=indices, leading_parent_N=sum(r['leading_identity_known'] for r in rows),
        nonempty_candidate_parent_N=sum(any(s['eligibleCandidates'] for s in r['stations']) for r in rows), stations=support)
table(OUT/'station_support.tsv', station_rows)
geometry = [r['geometry'] for r in native['records']]
summary = dict(passed=True, phase=phase, independent_parent_N=len(pairs), repeated_parent_executions=4 if phase=='full' else 0,
    total_parent_executions=len(pairs)+(4 if phase=='full' else 0), paired_current06_exact_N=len(paired_checks),
    root_identity_exact_N=sum(p['old_roots_float32_exact'] for p in pairs),
    current_selected_N=sum(p['new_selected'] for p in pairs), no_leading_entries=[i for i,p in enumerate(pairs) if p['leading_index'] is None],
    anchors={k:sum(r['anchor_counts'][k] for r in geometry) for k in geometry[0]['anchor_counts']},
    diagnostics={k:numbers([r[k] for r in geometry]) for k in ['max_abs_normal_mm','max_state_roundtrip_mm',
        'max_PRD_roundtrip_mm','independent_dx_max_delta_mm','max_candidate_roundtrip_mm',
        'max_normal_arithmetic_margin_mm','max_normal_interval_width_mm','max_state_locX_interval_width_mm','max_candidate_dx_interval_width_mm']},
    strata=stratum_summary, prefix_reproducibility=repro,
    typed_QA=dict(nonzero_status_with_timing_N=sum(v['status'] !=0 and v['localtime'] is not None for r in native['records'] for v in r['waves']),
        negative_signed_raw_N=sum(v['raw_charge_pC'] is not None and v['raw_charge_pC'] < 0 for p in pairs for v in p['readout'])),
    native_CPU_s=native['CPU_s'], native_wall_s=native['wall_s'], ROOT_read_bytes=native['ROOT_read_bytes'],
    schema_verified=True, overall_complete=False,
    reference_native_conditions_metadata='not_stored_in_Stage149_native; reference_digi_conditions_geometry_verified_from_actual_seeds; native_state_raw_pairing_checked_separately', population_FPR_measured=False, data_transfer_certified=False,
    calibrated_covariance=False, association_posterior_measured=False, energy_fits=0, response_fits=0,
    new_G4=0, new_independent_nu=0, reserved_forward=0, promotion=False,
    audit_CPU_s=time.process_time()-cpu, audit_wall_s=time.perf_counter()-tick,
    audit_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
assert summary['typed_QA']['nonzero_status_with_timing_N']==0
(OUT/'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False)+'\n')
print('ADMISSION',admission,'SUMMARY',summary,flush=True)
