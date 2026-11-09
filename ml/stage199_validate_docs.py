"""Check returned scalar evidence, source syntax and report links; no event I/O."""
import ast
import csv
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'workbook/stage199_energy_ml'
REPORT = ROOT / 'workbook/2026-11-09_stage199_all-flux-energy-flat-direct62.md'


def main():
    read = lambda name: json.loads((OUT / name).read_text())
    paths = [p for p in OUT.glob('*.json') if p.name != 'document_validation.json']
    for path in paths:
        json.loads(path.read_text())
    tables = list(OUT.glob('*.tsv'))
    for path in tables:
        with path.open() as stream:
            rows = list(csv.reader(stream, delimiter='\t'))
        assert rows and all(len(row) == len(rows[0]) for row in rows), path
    sources = list((ROOT / 'ml').glob('stage199*.py'))
    for path in sources:
        ast.parse(path.read_text(), str(path))
    workers = list((ROOT / 'AnalysisZipFramework/submission').glob('run_ml_stage199*.sh'))
    for path in workers:
        subprocess.run(['bash', '-n', str(path)], check=True)
    p, prep, fit, audit, status, storage = [read(name) for name in
        ['protocol.json', 'prepare.json', 'fit.json', 'independent_validation.json', 'scheduler_accounting.json', 'storage.json']]
    assert prep['passed'] and audit['passed'] and storage['passed'] and fit['passed']
    assert prep['sources_N'] == audit['sources_N'] == len(p['sources']) == 1134
    assert prep['records_N'] == audit['records_N'] == sum(r['N'] for r in prep['split'])
    assert fit['formal_fits_N'] == 6 and len(fit['models']) == 6
    assert fit['device']=='cuda' and all(v['actual_device'].startswith('cuda') and v['model_reload_exact'] for v in fit['models'])
    assert not status['failed'] and status['live_N'] == 0 and not status['unmaterialized_or_unobserved']
    assert p['weights']['edges_GeV'] == [50, 100, 200, 400, 800, 1600, 3200, 6400]
    assert prep['parent_and_incoming_disjoint'] and not prep['source_disjoint']
    assert audit['flat_weights_train_only'] and audit['base_weights_exact']
    assert audit['independent_rowspace_low_bin_interval_endpoints_N'] == 32
    assert audit['source_array_roundtrip_checks_N']==13608 and audit['scalar_risk_tail_checks_N']==3360
    assert all(v['all_rows_within_float32_forward_error_bound'] for v in audit['model_checks'])
    assert all(s['all_rows_within_forward_error_bound'] for v in audit['model_checks'] for s in v['seed_checks'])
    assert not read('decisions.json')['automatic_promotion']
    assert storage['source_return_archives_N'] == 471 and storage['no_persistent_ROOT']
    assert read('kubeflow_accounting.json')['exitCode'] == 0
    assert len(read('kubeflow_accounting.json')['phases'])==4 and len(read('execution_failures.json'))==3
    assert status['intentionally_cancelled_unstarted']==['9679884.0'] and status['starts']==60
    text = REPORT.read_text()
    for token in ['Stage87没有能量flat训练权重', str(prep['records_N']), 'source-level并不独立', '未测量', 'train-only', '保持暂停']:
        assert token in text, token
    assert text.count('```') % 2 == 0
    links = 0
    for target in re.findall(r'\]\(([^)]+)\)', text):
        if target.startswith(('http:', 'https:', '#')):
            continue
        assert (REPORT.parent / target.split('#')[0]).exists(), target
        links += 1
    for name in ['docs/nu_mu_energy_ml_revised_roadmap.md', 'docs/nu_mu_energy_ml_next_step_prompt.md']:
        old = subprocess.check_output(['git', 'show', f"{p['starting_commit']}:{name}"], cwd=ROOT)
        actual = (ROOT / name).read_bytes()
        assert actual.endswith(old) and actual.startswith('# 当前执行更新：Stage199'.encode())
    snapshot = json.loads((ROOT / 'workbook/stage158_energy_ml/preexisting_asset_snapshot.json').read_text())
    for name, expected in snapshot.items():
        st = (ROOT / name).stat()
        assert st.st_size == expected['bytes'] and st.st_mtime_ns == expected['mtime_ns']
    subprocess.run(['git', 'diff', '--check'], cwd=ROOT, check=True)
    subprocess.run(['git', 'diff', '--cached', '--check'], cwd=ROOT, check=True)
    result = dict(passed=True, scope='Source/text/returned scalars only; no local scientific event I/O',
                  JSON_N=len(paths), TSV_N=len(tables), Python_AST_N=len(sources), bash_syntax_N=len(workers),
                  report_local_links_N=links, historical_suffix_preserved=True,
                  Stage54_assets_size_mtime_preserved_N=len(snapshot), all_1134_sources_and_six_fits_verified=True)
    (OUT / 'document_validation.json').write_text(json.dumps(result, indent=2) + '\n')
    print(result)


if __name__ == '__main__':
    main()
