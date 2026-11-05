#!/usr/bin/env python3
"""Validate collected text summaries and document provenance with stdlib only."""
import ast
import csv
import json
import re
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
BASE = 'fa63c4a'
REPORT = 'workbook/2026-11-05_stage113_selection-response-measurement.md'


def load(name):
    return json.loads((OUT/name).read_text())


def rows(name):
    with (OUT/name).open() as stream:
        return list(csv.DictReader(stream, delimiter='\t'))


def main():
    complete, validation, costs = [load(n) for n in ['complete.json', 'measurement_validation.json', 'source_audit.json']]
    assert complete['status'] == 'measurement_complete' and complete['parent_entries'] == 60000
    assert complete['source_count'] == len(costs) == 6
    assert complete['new_fits'] == complete['new_forwards'] == 0 and not complete['promotion']
    assert not complete['original_QA_repeated'] and validation['passed']
    manifest = json.loads((ROOT/'workbook/stage111_energy_ml/source_manifest.json').read_text())
    assert [c['source'] for c in costs] == [s['source'] for s in manifest['files']]
    assert sum(c['read_entries'] for c in costs) == 60000
    for c in costs:
        assert c['read_entries'] == c['full_parent_entries'] == 10000 and c['branch_count'] == 67
        assert c['native_mask_differences'] == c['native_pz_max_difference_GeV'] == 0
        assert len(c['cuts']) == 20
        cumulative = 10000
        for cut in c['cuts']:
            assert cut['passed']+cut['failed'] == 10000
            assert 0 <= cut['unknown_native_pass'] <= cut['unknown'] <= 10000
            assert 0 <= cut['cumulative_pass'] <= cumulative
            cumulative = cut['cumulative_pass']
        assert cumulative == c['native_selected_N']
        assert c['native']['requested_bytes'] <= c['native']['pre_reserved_input_bytes']
    temporary_upper = sum(c['native']['temporary_bytes'] for c in costs)
    assert temporary_upper < 128*1024**2
    assert validation['max_event_identity_error'] <= 1e-12
    assert validation['max_aggregate_closure_error'] <= 1e-10
    assert validation['independent_key_aggregation_bootstrap_max_abs'] <= 1e-10
    primary = {r['stratum']: r for r in rows('primary.tsv')}
    low, second = primary['E50_100'], primary['E100_200']
    assert low['estimable'] == 'False' and low['missing_sources'] == '55:116,55:118'
    assert low['delta_MSE'] == low['low95'] == low['high95'] == 'NA' and low['valid_draws'] == '0'
    assert second['delta_MSE'] == '-0.09447554689537985' and second['estimable'] == 'True'
    assert second['valid_draws'] == '309' and second['low95'] == second['high95'] == 'NA'
    assert len(rows('source_primary.tsv')) == 12 and len(rows('invalid_native_pass_examples.tsv')) == 40
    identity = load('identity_audit.json')
    assert identity['passed'] and identity['no_test_only_sources_features_predictions_or_risks']
    assert identity['read_fields'] == ['incoming','role','initial_role','origin','source','group','run','eventID']
    assert all(s['invalid_key'] == 0 and s['all_parent_views_weighted_before_selection'] for s in identity['sources'])
    history = load('condor_history.json')[0]
    assert history['ClusterId'] == 9668067 and history['ExitCode'] == 0 and history['JobStatus'] == 4
    assert history['NumJobStarts'] == 1 and history['RequestCpus'] == 6 and history['RequestMemory'] == 18000
    assert load('watchdog.json')['passed'] and load('watchdog.json')['stop'] is None
    r = load('resources.json')
    assert r['source_requested_bytes'] == sum(c['requested_source_bytes'] for c in costs) == 23299485
    assert r['native_local_requested_bytes'] == sum(c['native']['requested_bytes'] for c in costs) == 17636087
    assert r['new_interface_requested_bytes'] == r['source_requested_bytes']+r['native_local_requested_bytes'] == 40935572
    assert r['interface_requested_bytes_including_prior_bound'] == 94323758 < 2*1024**3
    times = (OUT/'time.txt').read_text()
    assert 'User time (seconds): 57.83' in times and 'System time (seconds): 9.20' in times
    assert '0:25.91' in times and 'Exit status: 0' in times
    assert 69.33+67.03 < 3600 and 24.8+25.91 < 900
    transport = load('transport_validation.json')
    assert transport['passed'] and transport['byte_exact_input_files'] == 20
    package = ROOT/'software/energy-ml-stage113.tar.gz'
    if package.exists():
        with tarfile.open(package) as tar:
            for name in load('package.json')['files']:
                assert tar.extractfile(name).read() == (ROOT/name).read_bytes(), name
    for name in ['docs/nu_mu_energy_ml_revised_roadmap.md','docs/nu_mu_energy_ml_information_budget_plan.md']:
        old = subprocess.check_output(['git','show',f'{BASE}:{name}'],cwd=ROOT)
        assert (ROOT/name).read_bytes().startswith(old)
    prompt = 'docs/nu_mu_energy_ml_next_step_prompt.md'
    old = subprocess.check_output(['git','show',f'{BASE}:{prompt}'],cwd=ROOT)
    current = (ROOT/prompt).read_bytes()
    marker = '## 保留的stage54 data占据支线'.encode()
    assert old[old.index(marker):] == current[current.index(marker):]
    assets = ['AnalysisZipFramework/submission/ml_tracker_occupancy_prepare.sub',
              'AnalysisZipFramework/submission/run_ml_tracker_occupancy_prepare.sh',
              'ml/prepare_tracker_occupancy.py','ntuples/energy_ml_stage54','workbook/stage54_energy_ml']
    assert all((ROOT/name).exists() for name in assets)
    checked = 0
    for name in [REPORT,prompt]:
        for target in re.findall(r'\]\(([^)]+)\)',(ROOT/name).read_text()):
            if target.startswith(('http://','https://','#')):
                continue
            path = (ROOT/name).parent/target.split('#',1)[0]
            if path.parent == OUT and path.name in ['storage.json','document_validation.json']:
                continue
            assert path.exists(), (name,target)
            checked += 1
    for path in ROOT.glob('ml/*stage113*.py'):
        ast.parse(path.read_text())
    subprocess.run(['bash','-n','AnalysisZipFramework/submission/run_ml_stage113.sh'],cwd=ROOT,check=True)
    subprocess.run(['git','diff','--check'],cwd=ROOT,check=True)
    result = dict(passed=True, parent_entries=60000, source_count=6,
                  original_QA_repeated=False, native_mask_differences=0,
                  scientific_measurement_complete=True, lowest_primary_not_estimable=True,
                  second_primary_valid_draws=309, second_primary_interval_withheld=True,
                  no_model_improvement_measured=True, original_caps_preserved=True,
                  total_CPU_s=136.36,total_task_wall_s=50.71,
                  interface_requested_upper_bound_bytes=94323758,
                  native_temporary_files_sum_upper_bound_bytes=temporary_upper,
                  byte_exact_transport_inputs=20, local_links_checked=checked,
                  historical_doc_prefixes_preserved=True,stage54_suffix_preserved=True,
                  stage54_assets_present=True,local_event_or_model_payloads_opened=False)
    (OUT/'document_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
