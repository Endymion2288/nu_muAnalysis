#!/usr/bin/env python3
"""Standard-library audit of collected summaries; never open ROOT/NPZ arrays."""
import ast
import csv
import json
import re
import subprocess
import tarfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
BASE = '1cf3ade'


def load(name):
    return json.loads((OUT/name).read_text())


def main():
    qa, admission, complete = [load(n) for n in ['QA.json', 'admission.json', 'complete.json']]
    manifest = json.loads((REPO/'workbook/stage111_energy_ml/source_manifest.json').read_text())
    assert qa['passed'] and qa['synthetic']['passed']
    assert qa['real_entries'] == sum(s['read_entries'] for s in qa['sources']) == 36
    assert qa['real_entries'] <= 40
    assert [s['source'] for s in qa['sources']] == [s['source'] for s in manifest['files']]
    assert load('qa_manifest.json')['entries'] == 36
    assert sum(s['full_parent_entries'] for s in qa['sources']) == 60000
    invalid_pass = 0
    for s in qa['sources']:
        assert s['branch_count'] == 67 and s['full_parent_entries'] == 10000
        assert len(s['cuts']) == 20
        assert s['native_mask_differences'] == 0 and s['native_pz_max_difference_GeV'] == 0
        cumulative = s['read_entries']
        for cut in s['cuts']:
            assert cut['passed']+cut['failed'] == s['read_entries']
            assert 0 <= cut['unknown_native_pass'] <= cut['unknown'] <= s['read_entries']
            assert 0 <= cut['cumulative_pass'] <= cumulative
            cumulative = cut['cumulative_pass']
            invalid_pass += cut['unknown_native_pass']
        assert cumulative == s['native_selected_N']
    assert invalid_pass == 4
    assert admission['admitted'] is False and complete['status'] == 'resource_stop'
    assert complete['physics_endpoints'] == 'unmeasured'
    assert admission['CPU_s'] > 3600 and admission['wall_s'] > 900
    assert admission['requested_bytes'] < 2*1024**3
    assert load('attempt1_condor.json')['ExitCode'] == 1
    history = load('condor_history.json')
    assert history['ExitCode'] == 0 and history['NumJobStarts'] == 1 and history['NumRestarts'] == 0
    assert load('launch_amendment.json')['maximum_jobs_revised_to'] == 2
    assert load('attempt1_transport_validation.json')['byte_exact_input_files'] == 16
    assert load('transport_validation.json')['byte_exact_input_files'] == 17
    r = load('resources.json')
    assert abs(sum(a['CPU_s'] for a in r['attempts'])-r['total_CPU_s']) < 1e-10
    assert abs(sum(a['wall_s'] for a in r['attempts'])-r['total_task_wall_s']) < 1e-10
    assert r['total_CPU_s'] == 69.33 and r['total_task_wall_s'] == 24.8
    bound = sum(s['requested_source_bytes'] for s in qa['sources'])
    assert r['first_source_interface_upper_bound_bytes'] == bound == 25344369
    inferred = admission['requested_bytes']-3*sum(s['bytes'] for s in admission['per_source'])-128*1024**2
    assert inferred == r['combined_source_and_native_requested_upper_bound_bytes'] == 53388186
    assert r['second_task_source_and_native_interface_requested_bytes']+bound == inferred
    assert r['source_and_native_cap_bytes'] == 2*1024**3
    assert r['first_source_interface_actual'] == 'unmeasured'
    future = load('next_execution_contract.json')
    assert future['stage'] == 113 and future['maximum_new_jobs'] == 1
    limits = future['limits_including_stage112']
    assert limits['remaining_CPU_s']+r['total_CPU_s'] == limits['total_CPU_s'] == 3600
    assert limits['remaining_task_wall_s']+r['total_task_wall_s'] == limits['total_task_wall_s'] == 900
    assert limits['remaining_interface_requested_bytes']+inferred == limits['total_interface_requested_bytes'] == 2*1024**3
    for path in REPO.glob('ml/*stage112*.py'):
        ast.parse(path.read_text())
    subprocess.run(['bash', '-n', 'AnalysisZipFramework/submission/run_ml_stage112.sh'], cwd=REPO, check=True)
    for path in ['docs/nu_mu_energy_ml_revised_roadmap.md', 'docs/nu_mu_energy_ml_information_budget_plan.md']:
        old = subprocess.check_output(['git', 'show', f'{BASE}:{path}'], cwd=REPO)
        assert (REPO/path).read_bytes().startswith(old)
    handoff = 'docs/nu_mu_energy_ml_next_step_prompt.md'
    old = subprocess.check_output(['git', 'show', f'{BASE}:{handoff}'], cwd=REPO)
    new = (REPO/handoff).read_bytes()
    marker = '## 保留的stage54 data占据支线'.encode()
    assert old[old.index(marker):] == new[new.index(marker):]
    report = 'workbook/2026-11-05_stage112_selection-response-audit.md'
    links = 0
    for name in [report, handoff]:
        for target in re.findall(r'\]\(([^)]+)\)', (REPO/name).read_text()):
            if target.startswith(('http://', 'https://', '#')):
                continue
            path = (REPO/name).parent/target.split('#', 1)[0]
            if path.name in ['document_validation.json', 'storage.json'] and path.parent == OUT:
                continue  # Generated below / immediately after this validation.
            assert path.exists(), (name, target)
            links += 1
    package = REPO/'software/energy-ml-stage112.tar.gz'
    if package.exists():
        with tarfile.open(package) as tar:
            for member in tar.getmembers():
                if member.isfile():
                    assert tar.extractfile(member).read() == (REPO/member.name).read_bytes(), member.name
    old_assets = ['AnalysisZipFramework/submission/ml_tracker_occupancy_prepare.sub',
                  'AnalysisZipFramework/submission/run_ml_tracker_occupancy_prepare.sh',
                  'ml/prepare_tracker_occupancy.py', 'ntuples/energy_ml_stage54', 'workbook/stage54_energy_ml']
    assert all((REPO/p).exists() for p in old_assets)
    subprocess.run(['git', 'diff', '--check'], cwd=REPO, check=True)
    output = dict(passed=True, real_QA_entries=36, original_limit=40, sources=6,
                  parent_entries_metadata=60000, branches=67, cuts_per_source=20,
                  native_independent_mask_differences=0, pz_difference_GeV=0,
                  invalid_native_pass_source_cut_counts=4, synthetic_checks_passed=True,
                  resource_stop_preserved=True, complete_physics_measurement=False,
                  full_statistics_not_run=True, first_API_failure_not_hidden=True,
                  submissions=2, automatic_retries=0, cumulative_CPU_s=69.33,
                  cumulative_task_wall_s=24.8, conditional_interface_upper_bound_bytes=53388186,
                  first_actual_IO_and_physical_network_unmeasured=True,
                  roadmap_information_historical_prefixes_preserved=True,
                  stage54_suffix_preserved=True, stage54_assets_present=True,
                  local_links_checked=links, future_stage113_executed=False,
                  event_or_model_payloads_opened_by_validator=False)
    (OUT/'document_validation.json').write_text(json.dumps(output, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
