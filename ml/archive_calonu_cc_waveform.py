#!/usr/bin/env python3
"""Verify frozen support and rejoin every native field before removing duplicate shards."""
import csv
import json
import resource
import time
from pathlib import Path

import numpy as np


def main():
    tick, cpu = time.perf_counter(), time.process_time()
    repo = Path(__file__).resolve().parents[1]
    out = repo / 'workbook/stage39_energy_ml'
    cache = repo / 'ntuples/energy_ml_stage39/cc_waveform.npz'
    cfg = json.loads((repo / 'ml/configs/calonu_cc_waveform.json').read_text())
    summary = json.loads((out / 'summary.json').read_text())
    schemas = {r['class_name']: r for r in json.loads((out / 'native_schema_checks.json').read_text())}
    with np.load(cache) as saved:
        data = {k: saved[k] for k in saved.files}
    cases = json.loads(str(data['cases_json']))
    offset = 0
    removed = []
    field_counts = []
    for position, index in enumerate(cfg['indices']):
        path = cache.parent / f'shards/{index}.npz'
        request = json.loads((out / f'request_{index}.json').read_text())
        with np.load(path) as shard:
            records = json.loads(str(shard['cases_json']))
            end = offset + len(records)
            assert records == cases[offset:end]
            for wanted, actual in zip(request['cases'], records):
                assert all(actual[k] == value for k, value in wanted.items())
                assert actual['index'] == index
                assert actual['hits_RDO_beam_momentum_equal']
                assert actual['beam_barcode_generated_mass_equal']
                assert actual['beam_mass_shell_max_bound_ratio'] < 1
                assert actual['hits_entry'] == actual['input_entry'] % 1000
                assert actual['hits_subfile_ordinal'] == actual['input_entry'] // 1000
            assert len(records) == len(request['cases'])
            assert json.loads(str(shard['metadata_json'])) == summary['extraction_resources'][position]
            for schema in json.loads(str(shard['schemas_json'])):
                reference = schemas[schema['class_name']]
                assert reference['loaded_checksum'] == schema['loaded_checksum']
                assert reference['saved_checksums'] == schema['saved_checksums']
                assert dict(file=schema['file'], branch=schema['branch']) in reference['checked_branches']
            fields = [k for k in shard.files if k not in ['cases_json', 'metadata_json', 'schemas_json']]
            for key in fields:
                assert shard[key].dtype == data[key].dtype
                np.testing.assert_array_equal(shard[key], data[key][offset:end])
            field_counts.append(dict(index=index, events=len(records), native_array_fields=len(fields)))
        offset = end
        removed.append(dict(path=str(path.relative_to(repo)), bytes=path.stat().st_size))
    assert offset == len(cases) == 190
    assert len({(c['index'], c['input_entry']) for c in cases}) == len(cases)
    present = data['channel_present']
    common = data['common_waveform']
    regular = np.array([c['role'] == 'regular' for c in cases])
    empty = data['hit_count'].sum(axis=1) == 0
    np.testing.assert_array_equal(empty, ~present.any(axis=1))
    np.testing.assert_array_equal(common, present.all(axis=1))
    assert common.sum() == 147 and (common & regular).sum() == 112
    assert regular.sum() == 142 and empty.sum() == 43
    for key, values in data.items():
        if key.startswith('readout_') or key == 'nominal_window_charge_pC':
            assert np.isnan(values[~common]).all()
            assert np.isfinite(values[common]).all()
    with (out / 'readout_metrics.tsv').open() as handle:
        metrics = list(csv.DictReader(handle, delimiter='\t'))
    support = common & regular
    target = data['nominal_window_charge_pC'][support]
    for name in ['signed_saved', 'template_plus_constant']:
        reference = next(r for r in metrics if r['subset'] == 'regular' and r['method'] == name)
        error = data[f'readout_{name}_pC'][support] - target
        measured = dict(rmse_pC=np.sqrt(np.mean(error**2)), bias_pC=error.mean(),
                        R68_pC=(np.quantile(error, .84)-np.quantile(error, .16))/2,
                        tail_abs_gt025=np.mean(abs(error) > .25), tail_abs_gt1=np.mean(abs(error) > 1))
        for key, value in measured.items():
            np.testing.assert_allclose(value, float(reference[key]), rtol=1e-12, atol=1e-14)
    payload = repo / 'software/energy-ml-calonu-cc-waveform-stage39.tar.gz'
    removed.append(dict(path=str(payload.relative_to(repo)), bytes=payload.stat().st_size))
    # All comparisons above finish before any duplicate is removed.
    for record in removed:
        (repo / record['path']).unlink()
    (cache.parent / 'shards').rmdir()
    result = dict(final_cache=str(cache.relative_to(repo)), final_bytes=cache.stat().st_size,
                  native_all_fields_rejoined_equal=True, frozen_support_equal=True,
                  metadata_and_schema_preserved=True, group_checks=field_counts,
                  missing_readouts_remain_NaN=True, regular_metrics_independently_recomputed=True,
                  removed=removed, removed_bytes=sum(r['bytes'] for r in removed),
                  source_experiment_files_modified=False,
                  wall_s=time.perf_counter()-tick, cpu_s=time.process_time()-cpu,
                  peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    (out / 'archive.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
