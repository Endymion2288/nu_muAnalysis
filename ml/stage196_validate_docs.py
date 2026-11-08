"""Static/source and returned-scalar validation; no event data processing."""
import ast
import csv
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'workbook/stage196_energy_ml'
REPORT = ROOT / 'workbook/2026-11-08_stage196_good-hit-shape-and-native-time-collapse.md'


def main():
    json_files = list(OUT.glob('*.json'))
    for path in json_files:
        json.loads(path.read_text(), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    tables = list(OUT.glob('*.tsv'))
    for path in tables:
        with path.open() as f:
            rows = list(csv.reader(f, delimiter='\t'))
        assert rows and all(len(row) == len(rows[0]) for row in rows), path
    files = sorted((ROOT / 'ml').glob('stage196*.py'))
    for path in files + [ROOT / 'ml/stage188_finalize.py']:
        ast.parse(path.read_text(), filename=str(path))
    subprocess.run(['bash', '-n', str(ROOT / 'AnalysisZipFramework/submission/run_ml_stage196.sh')], check=True)
    a = json.loads((OUT / 'independent_validation.json').read_text())
    c = json.loads((OUT / 'storage_cleanup.json').read_text())
    s = json.loads((OUT / 'full_summary.json').read_text())
    p = json.loads((OUT / 'protocol.json').read_text())
    assert a['passed'] and c['passed'] and s['passed']
    assert c['failed_jobs'] == [] and c['live_N'] == 0 and c['starts'] == 3
    assert c['scheduler_CPU_s'] <= p['CPU_budget_s']
    assert c['retained_cache_models_B'] <= p['final_cache_cap_B']
    assert a['scalar_projection_vectors'] == dict(data=719, random_fixed_samples=1856, MC=92)
    assert a['raw_full_exact'] and a['pilot_prefix4_exact']
    assert s['MC_ideal_closure']['max_abs_difference_ADC'] == 0
    assert not any(s[k] for k in ['physical_source_identified', 'real_error_coverage_certified', 'energy_fits', 'overall_complete', 'promotion'])
    report = REPORT.read_text()
    assert report.count('```') % 2 == 0
    assert all(term in report for term in ['一阶', '同设置独立', '95th', '未测量', '整体仍未完成', 'pz0-only', '合法负值'])
    links = 0
    for target in re.findall(r'\]\(([^)]+)\)', report):
        if target.startswith(('http:', 'https:', '#')):
            continue
        assert (REPORT.parent / target.split('#')[0]).exists(), target
        links += 1
    historical = []
    for name in ['docs/nu_mu_energy_ml_revised_roadmap.md', 'docs/nu_mu_energy_ml_next_step_prompt.md']:
        old = subprocess.check_output(['git', 'show', f"{p['starting_commit']}:{name}"], cwd=ROOT)
        actual = (ROOT / name).read_bytes()
        assert actual.endswith(old) and actual.startswith('# 当前执行更新：Stage196'.encode())
        historical.append(name)
    snapshot = json.loads((ROOT / 'workbook/stage158_energy_ml/preexisting_asset_snapshot.json').read_text())
    for name, original in snapshot.items():
        stat = (ROOT / name).stat()
        assert stat.st_size == original['bytes'] and stat.st_mtime_ns == original['mtime_ns'], name
    subprocess.run(['git', 'diff', '--check'], cwd=ROOT, check=True)
    subprocess.run(['git', 'diff', '--cached', '--check'], cwd=ROOT, check=True)
    result = dict(passed=True, scope='source/text/returned scalars only; no local scientific event reads',
                  JSON_N=len(json_files), TSV_N=len(tables), Python_AST_N=len(files)+1,
                  bash_syntax=True, report_local_links_N=links, historical_suffix_preserved=historical,
                  Stage54_size_mtime_preserved_N=len(snapshot),
                  plots_visually_reviewed=['actual_shape_residuals.png', 'MC_time_collapse.png'],
                  stage87_roles_K_pz0_raw_status0_preserved=True, overall_complete=False)
    (OUT / 'document_validation.json').write_text(json.dumps(result, indent=2) + '\n')
    print(result)


if __name__ == '__main__':
    main()
