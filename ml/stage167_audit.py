"""Independent original names, range sets, and scalar identity-header re-reads."""
import csv
import gzip
import json
import os
import re
from collections import Counter
from pathlib import Path

import uproot
from stage167_common import ROOT, OUT, plan, write


def main():
    p = plan(); inv = json.loads((OUT / 'inventory.json').read_text())
    full = json.loads((OUT / 'full_summary.json').read_text())
    # Independent directory listings and regular expressions; no use of inventory().
    raw_indices, claims = set(), Counter()
    for kind in ['PHYS', 'RAW']:
        names = sorted(os.listdir(p['inputs'][kind + '_directory']))
        prior = sorted([r['name'] for r in inv[kind]['matched']] + inv[kind]['nonmatching'])
        assert names == prior
        matched = []
        for name in names:
            tokens = name.split('-')
            regex = (r'^Faser-Physics-015838-[0-9]{5}-[0-9]{5}-r0022-PHYS[.]root$' if kind == 'PHYS'
                     else r'^Faser-Physics-015838-[0-9]{5}[.]raw$')
            if re.fullmatch(regex, name):
                matched.append(name)
                if kind == 'PHYS':
                    claims.update(range(int(tokens[3]), int(tokens[4]) + 1))
                else:
                    raw_indices.add(int(tokens[3].split('.')[0]))
        assert matched == [r['name'] for r in inv[kind]['matched']]
    coverage = json.loads((OUT / 'range_coverage.json').read_text())
    declared = set(claims)
    assert coverage['claimed_indices'] == len(declared)
    assert coverage['RAW_without_PHYS_claim'] == sorted(raw_indices - declared)
    assert coverage['claimed_without_actual_RAW'] == sorted(declared - raw_indices)
    assert coverage['internal_claim_gaps'] == [i for i in range(min(declared), max(declared)+1) if i not in claims]
    assert set(map(int, coverage['overlapping_claims'])) == {k for k, n in claims.items() if n > 1}
    for i, names in coverage['overlapping_claims'].items():
        assert names == [r['name'] for r in inv['PHYS']['matched'] if r['first_index'] <= int(i) <= r['last_index']]
    with gzip.open(ROOT / p['inputs']['reference_prefix'], 'rt') as f:
        reference = json.load(f)[:64]
    reads = []
    for expected in full['records'][:3]:
        with uproot.open(expected['path'], array_cache=None, num_workers=1) as f:
            t = f['nt']; n = t.num_entries
            assert n == expected['N']
            assert f.classnames(cycle=False, recursive=False) == expected['top_level_keys']
            for b in ['run', 'eventID', 'eventTime']:
                assert t[b].typename == expected['branch_types'][b]
                for index, label in [(0, 'first'), (n-1, 'last')]:
                    value = int(t[b].array(entry_start=index, entry_stop=index+1, library='np')[0])
                    assert value == expected[label][b]
                if expected['path'] == p['inputs']['reference_PHYS']:
                    assert t[b].array(entry_stop=64, library='np').tolist() == [r[b] for r in reference]
            reads.append(dict(path=expected['path'], read_bytes=int(f.file.source.num_requested_bytes)))
    with (OUT / 'file_headers.tsv').open() as f:
        rows = list(csv.DictReader(f, delimiter='\t'))
    assert len(rows) == len(full['records'])
    for row, r, timing in zip(rows, full['records'], full['timings']):
        assert row['name'] == r['name'] and int(row['N']) == r['N']
        for field, label, branch in [('first_event','first','eventID'),('last_event','last','eventID'),
                                      ('first_time_s','first','eventTime'),('last_time_s','last','eventTime')]:
            assert int(row[field]) == r[label][branch]
        for field in ['CPU_s','wall_s','read_bytes','RSS_KiB']:
            assert float(row[field]) == timing[field]
    assert full['N_sum'] == sum(r['N'] for r in full['records'])
    grl = json.loads((ROOT / 'workbook/stage166_energy_ml/grl_input.json').read_text())
    times = [r[label]['eventTime'] for r in full['records'] for label in ['first','last']]
    write('exposure_evidence.json', dict(run=15838,
        actual_PHYS_files=len(full['records']), actual_RAW_files=len(raw_indices),
        PHYS_records_sum=full['N_sum'], sum_is_unique_events=False,
        PHYS_nonmatching_names=inv['PHYS']['nonmatching'], RAW_nonmatching_names=inv['RAW']['nonmatching'],
        observed_endpoint_min_unix_s=min(times), observed_endpoint_max_unix_s=max(times),
        endpoint_envelope_s=max(times)-min(times),
        official_stable_ranges_s=grl['stable_ranges_s'],
        official_run_recorded_lumi_pb_inv=grl['CSV']['recorded_lumi_pb_inv'],
        files_with_allowed_producer_metadata=sum(bool(r['metadata']) for r in full['records']),
        all_endpoint_runs15838=all(r[label]['run']==15838 for r in full['records'] for label in ['first','last']),
        read_scope='First/last actual rows only; full interior time/identity/DQ and complete nu selection unmeasured',
        all_RAW_indices_have_exactly_one_filename_claim=all(claims[i]==1 for i in raw_indices),
        actual_consumed_RAW_inputs_proven=False, complete_processing_proven=False,
        DAQ_livetime_proven=False, dataset_exposure_certified=False, dataset_luminosity_pb_inv=None,
        missing=['producer RAW-to-PHYS success/selection accounting for each actual input',
                 'DAQ accepted/live-time and official luminosity correspondence under the same selection',
                 'background and full-generation acceptance, real correlated auxiliaries and independent confirmation'],
        decision='Finite catalogue complete; do not probe alternative directories or assign luminosity from names/endpoints. No physics fit or deployment promotion.'))
    write('independent_validation.json', dict(passed=True, directory_listings_exact=2,
        independent_range_sets_exact=True, original3_scalar_headers_exact=True,
        reference64_exact=True, per_file_table_exact=len(rows), reads=reads,
        exposure_certified=False, dataset_luminosity_pb_inv=None,
        limitation='No complete interiors, RAW payload, producer input-vector contents or DAQ/luminosity-by-time proof tested.'))


if __name__ == '__main__':
    main()
