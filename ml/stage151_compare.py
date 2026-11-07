"""Paired conditions contrasts on real observed channels/states, without fits."""
import csv
import gzip
import json
from collections import Counter
from pathlib import Path

import numpy as np

OUT = Path('workbook/stage151_energy_ml')
CACHE = Path('ntuples/energy_ml_stage151')


def load(path):
    with gzip.open(path, 'rt') as stream:
        return json.load(stream)


def numbers(values):
    a = np.asarray([v for v in values if v is not None and np.isfinite(v)], dtype=float)
    return dict(N=len(a), min=float(a.min()), median=float(np.median(a)), mean=float(a.mean()),
                max=float(a.max()), RMS=float(np.sqrt(np.mean(a*a)))) if len(a) else dict(N=0)


def table(path, rows):
    if not rows:
        return
    with path.open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(dict.fromkeys(k for row in rows for k in row)),
                                delimiter='\t', lineterminator='\n', restval='NA')
        writer.writeheader()
        writer.writerows({k: 'NA' if v is None else v for k, v in row.items()} for row in rows)


def compare(phase):
    plan = json.loads((OUT/'protocol.json').read_text())
    nominal = load(plan['nominal_current_records'])
    native06 = json.loads(nominal['ntuples/energy_ml_stage149/full/native.json.gz'])
    pairs06 = json.loads(nominal['ntuples/energy_ml_stage149/full/paired.json.gz'])
    seeds06 = json.loads(nominal['workbook/stage149_energy_ml/full/seeds.json'])
    native04, pairs04 = load(CACHE/phase/'native.json.gz'), load(CACHE/phase/'paired.json.gz')
    legacy = load(CACHE/phase/'legacy.json.gz')
    seeds04 = json.loads((OUT/phase/'seeds.json').read_text())
    assert native04['configured_conditions'] == dict(conditions='OFLCOND-FASER-04', geometry='FASERNU-04')
    assert seeds04['conditions'] == 'OFLCOND-FASER-04' and seeds06['conditions'] == 'OFLCOND-FASER-06'
    assert len(pairs04) <= len(pairs06)
    n = len(pairs04)
    by_channel = {tag: {int(row[0]): (str(row[1]), str(row[2])) for row in native['cable_mapping']}
                  for tag, native in [('04', native04), ('06', native06)]}
    maps = {}
    for tag, native, pairs in [('04', native04, pairs04), ('06', native06, pairs06)]:
        maps[tag] = {by_channel[tag][v['channel']]: dict(channel=v['channel'], name=v['name']) for v in pairs[0]['readout']}
    common = sorted(set(maps['04']) & set(maps['06']))
    mapping_rows = []
    for key in sorted(set(maps['04']) | set(maps['06'])):
        a, b = maps['04'].get(key, {}), maps['06'].get(key, {})
        mapping_rows.append(dict(kind=key[0], physical_identifier=key[1], tag04_channel=a.get('channel'),
            tag04_name=a.get('name'), tag06_channel=b.get('channel'), tag06_name=b.get('name'), common=key in common))
    table(OUT/'channel_mapping.tsv', mapping_rows)
    raw_rows, events, field_differences = [], [], []
    rng_post = Counter()
    for i in range(n):
        a, b, old = pairs04[i], pairs06[i], legacy['records'][i]
        identity = (a['entry'], a['run'], a['event'])
        assert identity == (b['entry'], b['run'], b['event']) == (old['entry'], old['run'], old['event'])
        s4, s6 = seeds04['records'][i], seeds06['records'][i]
        assert all(s4[k] == s6[k] for k in ['run', 'event', 'roots', 'seeds', 'before'])
        for detector in s4['seeds']:
            rng_post[detector] += s4['after'][detector] == s6['after'][detector]
        r4 = {v['name']: v for v in a['readout']}
        r6 = {v['name']: v for v in b['readout']}
        for key in common:
            name4, name6 = maps['04'][key]['name'], maps['06'][key]['name']
            v4, v6 = r4[name4], r6[name6]
            v_old = old['readout'].get(name4)
            oldq = v_old['raw_charge_pC'] if v_old else None
            q4, q6 = v4['raw_charge_pC'], v6['raw_charge_pC']
            for field in v4['stored']:
                value4, value6 = v4['stored'][field], v6['stored'][field]
                if value4 != value6:
                    field_differences.append(dict(entry=i, name04=name4, name06=name6, field=field,
                        value04=value4, value06=value6, delta04_minus06=value4-value6))
            raw_rows.append(dict(entry=i, name04=name4, name06=name6, physical_identifier=key[1],
                channel04=maps['04'][key]['channel'], channel06=maps['06'][key]['channel'],
                present04=v4['present'], present06=v6['present'], status04=v4['status'], status06=v6['status'],
                legacy_same_branch_present=v_old['present'] if v_old else None,
                legacy_same_branch_status=v_old['stored']['status'] if v_old else None,
                baseline04_mV=v4['stored']['baseline'], baseline06_mV=v6['stored']['baseline'],
                baseline_rms04_mV=v4['stored']['baseline_rms'], baseline_rms06_mV=v6['stored']['baseline_rms'],
                raw_status_baseline_exact=v4['stored'] == v6['stored'],
                raw04_pC=q4, raw06_pC=q6, delta04_minus06_pC=q4-q6 if q4 is not None and q6 is not None else None,
                legacy_same_branch_raw_pC=oldq,
                delta04_minus_legacy_pC=q4-oldq if q4 is not None and oldq is not None else None,
                delta06_minus_legacy_pC=q6-oldq if name4 == name6 and q6 is not None and oldq is not None else None))
        k4, k6 = a['leading_index'], b['leading_index']
        t4 = native04['records'][i]['tracks'][k4] if k4 is not None else None
        t6 = native06['records'][i]['tracks'][k6] if k6 is not None else None
        p4, p6 = (t4['state'][5]/1000 if t4 else None), (t6['state'][5]/1000 if t6 else None)
        oldpz = old['leading'].get('Track_pz0')
        oldpz = oldpz/1000 if oldpz is not None else None
        surface_exact = t4['transform'] == t6['transform'] and t4['parameter_type'] == t6['parameter_type'] if t4 and t6 else None
        events.append(dict(entry=i, run=a['run'], event=a['event'], selected04=a['new_selected'],
            selected06=b['new_selected'], selected_legacy=old['selected'], pz04_GeV=p4, pz06_GeV=p6, legacy_pz0_GeV=oldpz,
            delta_pz04_minus06_GeV=p4-p6 if p4 is not None and p6 is not None else None,
            relative_pz04_over06_minus1=p4/p6-1 if p4 is not None and p6 is not None and p6 > 0 else None,
            delta_pz04_minus_legacy_GeV=p4-oldpz if p4 is not None and oldpz is not None else None,
            delta_pz06_minus_legacy_GeV=p6-oldpz if p6 is not None and oldpz is not None else None,
            same_leading_PRD_set=sorted(t4['prds']) == sorted(t6['prds']) if t4 and t6 else None,
            same_reference_surface=surface_exact,
            native_track_state_exact=t4['state'] == t6['state'] if t4 and t6 else None,
            full_covariance_exact=t4['covariance'] == t6['covariance'] if surface_exact else None,
            leading_covariance04_finite=a['covariance_QA']['finite'], leading_covariance06_finite=b['covariance_QA']['finite']))
    table(OUT/'paired_raw.tsv', raw_rows)
    table(OUT/'paired_states.tsv', events)
    channels = []
    for key in common:
        name4, name6 = maps['04'][key]['name'], maps['06'][key]['name']
        rows = [row for row in raw_rows if row['physical_identifier'] == key[1] and row['name04'] == name4]
        channels.append(dict(name04=name4, name06=name6, physical_identifier=key[1],
            status04=dict(Counter(str(r['status04']) for r in rows)), status06=dict(Counter(str(r['status06']) for r in rows)),
            status_disagreement_N=sum(r['status04'] != r['status06'] for r in rows),
            presence_disagreement_N=sum(r['present04'] != r['present06'] for r in rows),
            raw_status_baseline_exact_N=sum(r['raw_status_baseline_exact'] for r in rows),
            legacy_status_disagreement_N=sum(r['legacy_same_branch_status'] is not None and
                r['status04'] != r['legacy_same_branch_status'] for r in rows),
            legacy_status_comparison_N=sum(r['legacy_same_branch_status'] is not None for r in rows),
            raw04_pC=numbers([r['raw04_pC'] for r in rows]), raw06_pC=numbers([r['raw06_pC'] for r in rows]),
            delta04_minus06_pC=numbers([r['delta04_minus06_pC'] for r in rows]),
            delta04_minus_legacy_pC=numbers([r['delta04_minus_legacy_pC'] for r in rows]),
            delta06_minus_legacy_pC=numbers([r['delta06_minus_legacy_pC'] for r in rows])))
    result = dict(passed=True, N=n, tag04_mapped_channels=len(maps['04']), tag06_mapped_channels=len(maps['06']),
        common_physical_channels=len(common), only04=[r for r in mapping_rows if r['tag06_channel'] is None],
        only06=[r for r in mapping_rows if r['tag04_channel'] is None], channels=channels,
        root_event_seed_initial_RNG_exact_N=n, waveform_final_RNG_equal_N_by_detector=dict(rng_post),
        common_channel_views_N=len(raw_rows),
        common_raw_status_baseline_exact_N=sum(r['raw_status_baseline_exact'] for r in raw_rows),
        common_presence_disagreement_N=sum(r['present04'] != r['present06'] for r in raw_rows),
        differing_stored_fields=field_differences,
        common_status_disagreement_N=sum(r['status04'] != r['status06'] for r in raw_rows),
        selected04_N=sum(r['selected04'] for r in events), selected06_N=sum(r['selected06'] for r in events),
        legacy_selected_N=sum(r['selected_legacy'] for r in events),
        selection_migration={f'tag04{a}_tag06{b}': sum(r['selected04'] == bool(a) and r['selected06'] == bool(b) for r in events)
                             for a in [0, 1] for b in [0, 1]},
        paired_leading_N=sum(r['pz04_GeV'] is not None and r['pz06_GeV'] is not None for r in events),
        same_leading_PRD_set_N=sum(r['same_leading_PRD_set'] is True for r in events),
        same_reference_surface_N=sum(r['same_reference_surface'] is True for r in events),
        native_track_state_exact_N=sum(r['native_track_state_exact'] is True for r in events),
        full_covariance_exact_N=sum(r['full_covariance_exact'] is True for r in events),
        delta_pz04_minus06_GeV=numbers([r['delta_pz04_minus06_GeV'] for r in events]),
        relative_pz04_over06_minus1=numbers([r['relative_pz04_over06_minus1'] for r in events]),
        delta_pz04_minus_legacy_GeV=numbers([r['delta_pz04_minus_legacy_GeV'] for r in events]),
        delta_pz06_minus_legacy_GeV=numbers([r['delta_pz06_minus_legacy_GeV'] for r in events]),
        legacy_missing_branches=legacy['missing_branches'],
        legacy_physical_cable_map_certified=False, legacy_random_streams='unknown',
        calibrated_covariance_pull=False, assigned_nuisance_probability=False, new_G4=0, fits=0, overall_complete=False)
    (OUT/'comparison.json').write_text(json.dumps(result, indent=2)+'\n')
    return result
