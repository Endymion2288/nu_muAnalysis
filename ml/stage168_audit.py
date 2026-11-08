"""Independent C++ ROOT counts, Uproot schemas, frozen paths and command bounds."""
import csv
import json
import shlex
from pathlib import Path

import ROOT as R
import uproot
from stage168_common import ROOT, OUT, write


def main():
    frozen = json.loads((OUT/'inputs.json').read_text())
    old = json.loads((ROOT/'workbook/stage130_energy_ml/source_protocol.json').read_text())
    full = json.loads((OUT/'full_summary.json').read_text())
    records = {r['path']: r for r in full['records']}
    sources = {r['index']: r for r in old['sources']}
    actual = []
    for item in sorted(old['inventory'], key=lambda r: r['run']):
        component = {sources[i]['component'] for i in item['source_indices']}
        assert len(component) == 1
        actual.append(dict(run=item['run'], nominal=item['nominal'], component=component.pop(), path=item['EVNT']))
    assert actual == frozen['run_mapping']
    assert list(dict.fromkeys(r['path'] for r in actual)) == frozen['unique_paths']
    assert list(records) == frozen['unique_paths']
    selected = []
    for component, nominal in [('pi',False),('pi',True),('k',None),('charm',None)]:
        row = next(r for r in actual if r['component'] == component and (nominal is None or r['nominal'] == nominal))
        if row['path'] not in selected:selected.append(row['path'])
    assert selected == [r['path'] for r in frozen['pilot']]
    reads = []
    for path in selected:
        expected = records[path]
        before = int(R.TFile.GetFileBytesRead())
        f = R.TFile.Open(path, 'READ'); assert f and not f.IsZombie()
        assert int(f.Get('CollectionTree').GetEntries()) == expected['N']
        assert {str(k.GetName()):str(k.GetClassName()) for k in f.GetListOfKeys()} == expected['top_level_keys']
        for name, meta in expected['metadata'].items():
            if meta['classname'] == 'TTree':assert int(f.Get(name).GetEntries()) == meta['N']
        f.Close()
        cpp_bytes = int(R.TFile.GetFileBytesRead()) - before
        with uproot.open(path, array_cache=None, num_workers=1) as directory:
            tree = directory['CollectionTree']
            assert {b: tree[b].typename for b in tree.keys()} == expected['CollectionTree_schema']
            for name, meta in expected['metadata'].items():
                if meta['classname'] == 'TTree':
                    t = directory[name]
                    assert {b:t[b].typename for b in t.keys()} == meta['schema']
                    for b, rows in meta['scalar_rows'].items():
                        values = t[b].array(entry_stop=4, library='np').tolist()
                        assert [v if isinstance(v,(int,bool)) or __import__('math').isfinite(v) else str(v) for v in values] == rows
            reads.append(dict(path=path, Cpp_ROOT_read_bytes=cpp_bytes,
                              Uproot_read_bytes=int(directory.file.source.num_requested_bytes)))
    ranges = json.loads((OUT/'logged_ranges.json').read_text())
    proof = json.loads((ROOT/'workbook/stage130_energy_ml/parent_range_proof.json').read_text())
    assert len(ranges) == len(proof['sources'])
    for row, prior in zip(ranges, proof['sources']):
        s = sources[prior['index']]; commands = [shlex.split(v['command']) for v in prior['boundary_logs']]
        assert all(c[1] == s['EVNT'] for c in commands)
        first = int(commands[0][commands[0].index('--skip')+1])
        stop = int(commands[-1][commands[-1].index('--skip')+1])+int(commands[-1][commands[-1].index('-n')+1])
        assert row['skip'] == first == prior['skip'] and row['count'] == stop-first == prior['count']
        assert row['generated_N'] == records[s['EVNT']]['N']
        assert row['within_actual_N'] == (0 <= first < stop <= row['generated_N'])
    with (OUT/'EVNT_headers.tsv').open() as f:table = list(csv.DictReader(f,delimiter='\t'))
    assert len(table) == len(actual)
    for row, mapped in zip(table,actual):
        assert row['path'] == mapped['path'] and int(row['run']) == mapped['run']
        assert row['component'] == mapped['component'] and row['nominal'] == str(mapped['nominal'])
        assert int(row['N']) == records[row['path']]['N']
        timing = next(t for t in full['timings'] if t['path'] == row['path'])
        assert all(float(row[k]) == timing[k] for k in ['CPU_s','wall_s','read_bytes','RSS_KiB'])
    assert full['N_sum'] == sum(r['N'] for r in full['records'])
    write('independent_validation.json', dict(passed=True, Cpp_ROOT_pilot_counts_exact=len(selected),
        Uproot_pilot_schemas_scalar_metadata_exact=len(selected), reads=reads,
        literal_run_path_mapping_exact=len(actual), logged_bounds_independent_exact=len(ranges),
        per_run_table_exact=len(table), weight_normalization_certified=False, acceptance_certified=False,
        CollectionTree_payload_read=False))
    completed = json.loads((ROOT/'workbook/stage130_energy_ml/production_contract.json').read_text())['all_source_indices']
    write('denominator_evidence.json', dict(
        actual_unique_EVNT_files=len(records), generated_record_sum=full['N_sum'],
        counts_by_run=[dict(**r,N=records[r['path']]['N']) for r in actual],
        nominal_record_sum=sum(records[r['path']]['N'] for r in actual if r['nominal']),
        alternative_record_sum=sum(records[r['path']]['N'] for r in actual if not r['nominal']),
        logged_ranges_within_N=sum(r['within_actual_N'] for r in ranges), logged_ranges_checked=len(ranges),
        source_inventory_N=len(old['sources']), stage130_completed_source_N=len(completed),
        logged_proof_among_completed_source_N=sum(r['index'] in completed for r in ranges),
        source_ranges_without_this_logproof=len(old['sources'])-len(ranges),
        completed_sources_without_this_logproof=len(set(completed)-{r['index'] for r in ranges}),
        scalar_metadata_branch_names=sorted({b for r in full['records'] for m in r['metadata'].values() for b in m.get('scalar_rows',{})}),
        actual_scalar_metadata_fields=[dict(path=r['path'],tree=name,branch=b,values=values)
            for r in full['records'] for name,m in r['metadata'].items() for b,values in m.get('scalar_rows',{}).items()],
        unweighted_entry_counts_only=True, independent_interactions_certified=False,
        weighted_generator_normalization_certified=False, physical_flux_exposure_certified=False,
        complete_per_generated_event_processing_selection_accounting=False,
        full_generation_acceptance_certified=False, physics_precision_measured=False,
        decision='Finite EVNT header acquisition complete. Do not divide selected by header totals as acceptance, invent weights/prior, expand directories or launch native full event scans automatically.',
        missing=['named generator weights and normalization/exposure with producer definitions',
                 'actual per-generated-event processing outcomes and common-selection acceptance',
                 'matched data exposure, backgrounds, real correlated auxiliary constraints and independent confirmation']))


if __name__ == '__main__':
    main()
