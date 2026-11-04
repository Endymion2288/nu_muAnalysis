"""Compact Stage96 evidence without PHYS access, prediction, or fitting."""
import json
import re
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / 'workbook/stage96_energy_ml'


def read(name):
    return json.loads((OUT / name).read_text())


def write(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def compact_schema():
    names = ['QA_schema.json', 'schema.json']
    if not any((OUT / name).exists() for name in names):
        assert read('schema_catalog.json')['lossless_source_rows_verified']
        return
    schemas = []
    snapshots = {}
    original_bytes = {}
    for name in names:
        original = read(name)
        original_bytes[name] = (OUT / name).stat().st_size
        rows = []
        for item in original:
            branches = item['branches']
            if branches not in schemas:
                schemas.append(branches)
            rows.append(dict(source=item['source'], schema_id=schemas.index(branches)))
        restored = [dict(source=r['source'], branches=schemas[r['schema_id']]) for r in rows]
        assert restored == original
        snapshots[name] = rows
    write('schema_catalog.json', dict(schemas=schemas, snapshots=snapshots,
          original_bytes=original_bytes, lossless_source_rows_verified=True))
    for name in names:
        (OUT / name).unlink()


def storage():
    files = []
    for directory in ['workbook/stage96_energy_ml', 'ntuples/energy_ml_stage96', 'ml/artifacts/stage96']:
        files.extend(p for p in (REPO / directory).rglob('*') if p.is_file())
    files += [REPO / ('ml/' + name + '.py') for name in [
        'prepare_candidate_ablation', 'train_candidate_ablation', 'report_candidate_ablation',
        'qa_candidate_report', 'validate_candidate_input', 'package_candidate_ablation',
        'collect_candidate_ablation', 'time_candidate_worker', 'summarize_candidate_ablation']]
    files += [REPO / name for name in [
        'AnalysisZipFramework/submission/ml_candidate_ablation.sub',
        'AnalysisZipFramework/submission/ml_candidate_ablation_kubeflow.json',
        'AnalysisZipFramework/submission/run_ml_candidate_ablation.sh',
        'workbook/2026-11-04_stage96_candidate-input-ablation.md', '.gitignore',
        'docs/nu_mu_energy_ml_revised_roadmap.md', 'docs/nu_mu_energy_ml_information_budget_plan.md',
        'docs/nu_mu_energy_ml_next_step_prompt.md']]
    target = OUT / 'storage.json'
    files = sorted(set(files + [target]))
    for _ in range(8):
        rows = [dict(path=str(p.relative_to(REPO)), bytes=p.stat().st_size if p.exists() else 0) for p in files]
        total = sum(r['bytes'] for r in rows)
        write('storage.json', dict(final_retention_cap_bytes=20000000, total_logical_bytes=total,
              scope='All Stage96 caches/models/workbook/code/config/report; conservatively includes full shared docs and gitignore. Previous-stage shared caches, site logs and Git object storage excluded.',
              files=rows, cleanup='cleanup.json', schema_compaction='schema_catalog.json',
              source_data_in_Git=False, no_ROOT_or_xAOD_retained=True))
        if sum(p.stat().st_size for p in files) == total:
            break
    assert total <= 20000000 and total == sum(p.stat().st_size for p in files)
    return total


def main():
    start = time.perf_counter(), time.process_time()
    assert read('validation.json')['passed'] and read('worker_completion.json')['new_fits'] == 2
    with np.load(REPO / 'ntuples/energy_ml_stage96/candidates.npz') as c, \
            np.load(REPO / 'ntuples/energy_ml_stage94/evaluation_input.npz') as d:
        np.testing.assert_array_equal(c['row'], d['row'])
        count = np.diff(c['offsets'])
        edge_count = np.diff(c['edge_offsets'])
        available = c['available']
        support = []
        for role, label in [(1, 'train'), (2, 'cal'), (3, 'test')]:
            use = d['role'] == role
            support.append(dict(role=label, requested_records=int(use.sum()),
                  available_payload_records=int((use & available).sum()),
                  unavailable_records=int((use & ~available).sum()),
                  single_records=int((use & available & (count == 1)).sum()),
                  multiple_records=int((use & available & (count > 1)).sum()),
                  empty_records=int((use & available & (count == 0)).sum()),
                  candidate_nodes=int(count[use].sum()), leading_edges=int(edge_count[use].sum())))
        nodes = c['nodes']
        features = read('protocol.json')['node_features']
        missing = {name: int((~np.isfinite(nodes[:, j])).sum()) for j, name in enumerate(features)}
        assert not np.isinf(nodes).any() and not np.isinf(c['edges']).any()
        assert np.all(nodes[np.isfinite(nodes[:, 0]), 0] > 0)
        for j in [4, 5, 6]:
            assert np.all(nodes[np.isfinite(nodes[:, j]), j] >= 0)
        for j in list(range(7, 13)) + list(range(16, 22)):
            assert not np.isin(nodes[:, j], [-999, -999999, 999999]).any()
        signed = dict(charge_minus_one=int((nodes[:, 3] == -1).sum()),
                      module_eta_minus_one=int((nodes[:, 13] == -1).sum()),
                      negative_px=int((nodes[:, 1] < 0).sum()), negative_py=int((nodes[:, 2] < 0).sum()))
    write('bookkeeping_audit.json', dict(passed=True, support=support,
          legacy_extraction_test_payload_records=read('extraction.json').get('test_payload_records'),
          legacy_field_meaning='requested test input rows including unavailable sources; not opened payloads',
          corrected_test_available_payload_records=next(r['available_payload_records'] for r in support if r['role'] == 'test'),
          correction='Only future extraction counter names changed after production; frozen caches, fits and numerical results unchanged.',
          node_missing_values=missing, preserved_signed_values=signed,
          nonphysical_positive_domain_values=0, geometry_sentinel_values=0,
          new_PHYS_reads=0, new_fits=0, new_predictions=0))
    compact_schema()
    batch = {mode: read(mode + '_job.json') for mode in ['extract', 'fit', 'report']}
    qa = {}
    for path in sorted(OUT.glob('*.time')):
        value = {}
        for label, key in [('User time', 'user_CPU_s'), ('System time', 'system_CPU_s')]:
            value[key] = float(re.search(re.escape(label) + r' \(seconds\): ([0-9.]+)', path.read_text())[1])
        value['CPU_s'] = value['user_CPU_s'] + value['system_CPU_s']
        qa[path.name] = value
    cpu = sum(r['CPU_s'] for r in batch.values()) + sum(r['CPU_s'] for r in qa.values())
    write('resources.json', dict(batch_outer_scopes=batch, separate_QA_outer_scopes=qa,
          measured_disjoint_CPU_s=cpu, CPU_cap_s=21600,
          GPU_task_outer_wall_s=batch['fit']['wall_s'], GPU_task_container_wall_s=42,
          GPU_task_wall_cap_s=7200, GPU_concurrency=1,
          extraction_child_average_cores=read('extraction.json')['child_CPU_s'] / read('extraction.json')['wall_s'],
          report_child_average_cores=read('report_completion.json')['child_CPU_s'] / read('report_completion.json')['parallel_wall_s'],
          nested_times_not_added=True, complete_single_core_speedup='未测量',
          unmetered='Initial manifest/freeze, metadata, transfers, some audit/plot/housekeeping and syntax checks; total session CPU is not exactly measured.',
          physical_EOS_network_bytes='未测量', simultaneous_total_peak_RSS='未测量',
          summarizer_wall_s=time.perf_counter()-start[0], summarizer_CPU_s=time.process_time()-start[1]))
    retained = storage()
    print(json.dumps(dict(passed=True, measured_disjoint_CPU_s=cpu,
                         retained_logical_bytes=retained, support=support)), flush=True)


if __name__ == '__main__':
    main()
