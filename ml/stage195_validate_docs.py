"""Validate returned scalar references, local links, preserved historical documents."""
import ast
import csv
import json
import re
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'workbook/stage195_energy_ml'
REPORT=ROOT/'workbook/2026-11-08_stage195_dual-range-rectification-and-error-identifiability.md'

if __name__=='__main__':
    assert json.loads((OUT/'independent_validation.json').read_text())['passed']
    assert json.loads((OUT/'storage_cleanup.json').read_text())['passed']
    account=json.loads((OUT/'scheduler_accounting.json').read_text())
    cleanup=json.loads((OUT/'storage_cleanup.json').read_text())
    assert account['total_CPU_s']<=1200 and account['live_N']==0
    failed=[f"{j['ClusterId']}.{j['ProcId']}" for j in account['jobs'] if j['JobStatus']!=4 or j.get('ExitCode')!=0]
    assert cleanup['failed_jobs']==failed==['9678642.0']
    scalar_N=0
    for path in OUT.glob('*.json'):
        json.loads(path.read_text());scalar_N+=1
    with (OUT/'goal_requirements.tsv').open() as f:
        rows=list(csv.DictReader(f,delimiter='\t'))
        assert len(rows)==8 and rows[-1]['route']=='dual_range' and all(None not in r for r in rows)
    paths=[REPORT,ROOT/'docs/nu_mu_energy_ml_revised_roadmap.md',ROOT/'docs/nu_mu_energy_ml_next_step_prompt.md']
    historical={}
    for path in paths[1:]:
        rel=str(path.relative_to(ROOT))
        before=subprocess.check_output(['git','show',f'HEAD:{rel}'],cwd=ROOT,text=True)
        assert path.read_text().endswith(before)
        historical[rel]=True
    links=0
    for dest in re.findall(r'\]\(([^)]+)\)',REPORT.read_text()):
        if dest.startswith(('http:','https:','#')):continue
        target=REPORT.parent/dest.split('#')[0]
        assert target.exists(),str(target)
        links+=1
    sources=list((ROOT/'ml').glob('stage195*.py'))+[ROOT/'ml/stage188_finalize.py']
    for path in sources:ast.parse(path.read_text())
    subprocess.run(['bash','-n',str(ROOT/'AnalysisZipFramework/submission/run_ml_stage195.sh')],check=True)
    subprocess.run(['git','diff','--check'],cwd=ROOT,check=True)
    subprocess.run(['git','diff','--cached','--check'],cwd=ROOT,check=True)
    baseline=json.loads((ROOT/'workbook/stage158_energy_ml/preexisting_asset_snapshot.json').read_text())
    assert all((ROOT/k).stat().st_size==v['bytes'] and (ROOT/k).stat().st_mtime_ns==v['mtime_ns'] for k,v in baseline.items())
    report=dict(passed=True,scalar_JSON_N=scalar_N,requirements_N=len(rows),report_local_links_N=links,
        historical_suffixes_preserved=historical,source_AST_N=len(sources),worker_bash_syntax=True,
        git_diff_check=True,Stage54_preserved_N=len(baseline),overall_complete=False)
    (OUT/'document_validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(report)
