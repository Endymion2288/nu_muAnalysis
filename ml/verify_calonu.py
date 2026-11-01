#!/usr/bin/env python3
"""Compact stage35 archive QA and descriptive fit-quality counts; no new fits."""
import itertools
import json
import tarfile
import time
from pathlib import Path

import numpy as np
import xgboost as xgb

from calonu_inputs import configuration, feature_names, load, manifest
from calonu_ablation import reports, root
from frozen_evaluation import save_json
from train_bdt import write_table


def main():
    repo = Path(__file__).resolve().parents[1]
    tick = time.perf_counter()
    cfg = configuration(repo)
    validation_path = reports(repo) / 'archive_validation.json'
    previous = json.loads(validation_path.read_text()) if validation_path.exists() else {}
    parts = {p: load(repo, p) for p in cfg['partitions']}
    for a, b in itertools.combinations(parts.values(), 2):
        assert not set(a['group']) & set(b['group'])
        assert not set(zip(a['run'], a['eventID'])) & set(zip(b['run'], b['eventID']))
    names, extra = feature_names(repo)
    model_bytes = 0
    for i in range(3):
        for version in cfg['models']:
            path = repo / f'ml/artifacts/stage35/seed_{i}/{version}.ubj'
            model = xgb.Booster()
            model.load_model(path)
            ordered = names + extra + (cfg['features'] if version == 'C1' else [])
            assert model.feature_names == ordered
            model_bytes += path.stat().st_size
    for p in ['calibration', 'test']:
        with np.load(root(repo) / f'{p}_predictions.npz') as z:
            assert all(len(z[k]) == len(parts[p]['run']) and np.isfinite(z[k]).all() for k in z.files)
    quality = []
    for part, data in parts.items():
        for i in range(4):
            em = data[f'CaloNu{i}_E_EM'] / 1000
            q, raw, status = [data[f'CaloNu{i}_{k}'] for k in ['charge', 'raw_charge', 'status']]
            for label, mask in [('all', np.ones(len(em), bool))] + [(str(s), status == s) for s in np.unique(status)]:
                finite = np.isfinite(em) & mask
                quality.append(dict(partition=part, module=i, status=label, N=int(mask.sum()),
                                    nonfinite_EM=int((mask & ~np.isfinite(em)).sum()),
                                    negative_EM=int((finite & (em < 0)).sum()),
                                    abs_EM_gt_1000_GeV=int((finite & (abs(em) > 1000)).sum()),
                                    finite_charge=int((mask & np.isfinite(q)).sum()),
                                    finite_raw_charge=int((mask & np.isfinite(raw)).sum()),
                                    min_EM_GeV=float(em[finite].min()) if finite.any() else np.nan,
                                    max_EM_GeV=float(em[finite].max()) if finite.any() else np.nan))
    write_table(reports(repo) / 'fit_quality_descriptive.tsv', quality)
    # Correct diagnostic-only counts from compact caches, without another PHYS scan.
    import csv
    table = list(csv.DictReader((reports(repo) / 'extraction_files.tsv').open(), delimiter='\t'))
    for row in table:
        data = parts[row['partition']]
        v = data['CaloNu_total_E_EM'][data['manifest_index'] == int(row['index'])]
        row['calonu_nonzero'] = int((np.isfinite(v) & (v != 0)).sum())
        row['calonu_nonfinite'] = int((~np.isfinite(v)).sum())
    write_table(reports(repo) / 'extraction_files.tsv', table)
    archive = repo / 'software/energy-ml-calonu-stage35-train.tar.gz'
    payload_check = previous.get('training_payload_fit_stop_only_verified')
    if archive.exists():
        with tarfile.open(archive) as tar:
            paths = tar.getnames()
        assert not any('calibration.npz' in p or 'test.npz' in p for p in paths)
        assert all(f'ntuples/energy_ml_stage35/{p}.npz' in paths for p in ['fit', 'stop'])
        payload_check = True
    manifest_rows = manifest(repo)
    assert len(set(r['group'] for r in manifest_rows)) == len(manifest_rows) == 124
    final = [root(repo) / f'{p}.npz' for p in cfg['partitions']]
    final += [root(repo) / f'{p}_predictions.npz' for p in ['calibration', 'test']]
    disposable = list((root(repo) / 'shards').glob('*.npz'))
    disposable += list((repo / 'software').glob('energy-ml-calonu-stage35-*.tar.gz'))
    disposable_records = [dict(path=str(p.relative_to(repo)), bytes=p.stat().st_size) for p in disposable]
    if previous.get('cleanup_completed'):
        assert not disposable, 'New intermediates appeared after archival cleanup'
        disposable_records = previous['disposable_files']
    result = dict(
        source_groups_disjoint=True, selected_keys_disjoint=True, model_feature_orders_verified=6,
        finite_aligned_prediction_files=2, training_payload_fit_stop_only_verified=payload_check,
        partition_npz_field_readback='all fields checked in collect before shard cleanup',
        final_cache_files=[dict(path=str(p.relative_to(repo)), bytes=p.stat().st_size) for p in final],
        final_cache_bytes=sum(p.stat().st_size for p in final), model_bytes=model_bytes,
        disposable_files=disposable_records,
        disposable_bytes=sum(p['bytes'] for p in disposable_records),
        quality_audit='posthoc descriptive only; no cuts, refits or changed test estimates',
        diagnostic_counter_correction='finite nonzero and nonfinite separated from compact cache; no selections or predictions changed',
        wall_s=time.perf_counter() - tick)
    if previous.get('cleanup_completed'):
        result.update(cleanup_completed=True, removed_files=previous['removed_files'])
    save_json(validation_path, result)
    print(json.dumps({'final_cache_bytes': sum(p.stat().st_size for p in final), 'model_bytes': model_bytes,
                      'remaining_disposable_bytes': sum(p.stat().st_size for p in disposable)}))


if __name__ == '__main__':
    main()
