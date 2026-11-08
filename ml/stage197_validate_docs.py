"""Validate returned scalars, scope and source documents without event I/O."""
import ast
import csv
import json
import re
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'workbook/stage197_energy_ml'
REPORT=ROOT/'workbook/2026-11-08_stage197_real-low-pz-candidate-support-and-aux-gap.md'


def main():
    paths=[p for p in OUT.glob('*.json') if p.name!='document_validation.json']
    for p in paths:json.loads(p.read_text())
    tables=list(OUT.glob('*.tsv'))
    for p in tables:
        with p.open() as f:rows=list(csv.reader(f,delimiter='\t'))
        assert rows and all(len(r)==len(rows[0]) for r in rows),p
    files=list((ROOT/'ml').glob('stage197*.py'))+[ROOT/'ml/stage188_finalize.py']
    for p in files:ast.parse(p.read_text(),str(p))
    subprocess.run(['bash','-n',str(ROOT/'AnalysisZipFramework/submission/run_ml_stage197.sh')],check=True)
    read=lambda name:json.loads((OUT/name).read_text())
    s,a,c,ad,user,p=[read(name) for name in ['pilot_summary.json','independent_validation.json','storage_cleanup.json','admission.json','input_status.json','protocol.json']]
    assert s['passed'] and a['passed'] and c['passed'] and not ad['admitted']
    assert not (OUT/'full_submission.json').exists() and not (OUT/'full_summary.json').exists()
    assert ad['threefold_full_projection_CPU_s']>p['resources']['phase_CPU_s']['full']
    assert a['actual_processed_records_N']==8192 and a['scalar_prefix8192_cumulative_counts_exact']
    assert s['pre_veto_N']==a['unknown_final_selection_N']==2647
    assert s['pre_veto_pz_counts']['50_100']==a['pre_veto_pz50_100_N']==351
    assert not a['final_candidate_yield_measured'] and a['MC_read_N']==0
    assert c['starts']==2 and c['live_N']==0 and not c['failed_jobs']
    assert c['scheduler_CPU_s']<=p['resources']['CPU_budget_s'] and c['retained_cache_models_B']<=8388608
    assert user['status']=='deferred_by_user_pending_future_input' and user['accessible_aux_manifest'] is None
    assert not user['overall_complete'] and not user['whole_goal_paused']
    inv=read('aux_inventory.json');assert inv['listing_exit']==54 and 'Operation not permitted' in inv['listing_error']
    text=REPORT.read_text()
    assert all(t in text for t in ['不是ν候选','最终选择状态未知','未测量','目前没有，可以暂时空置','整体低真E优于传统','仍未完成'])
    assert text.count('```')%2==0
    links=0
    for target in re.findall(r'\]\(([^)]+)\)',text):
        if target.startswith(('http:','https:','#')):continue
        destination=REPORT.parent/target.split('#')[0]
        if destination!=OUT/'document_validation.json':
            assert destination.exists(),target
        links+=1
    with (OUT/'completion_audit.tsv').open() as f:
        audit=list(csv.DictReader(f,delimiter='\t'))
    for row in audit:
        for target in row['evidence'].split(';'):assert (ROOT/target).exists(),target
    # Inspect authoritative decisions, not just verifier filenames.
    for stage in [189,191]:
        d=json.loads((ROOT/f'workbook/stage{stage}_energy_ml/content_decision.json').read_text())
        assert d['fixed_package_ended'] and not d['expand'] and not d['promotion']
    shape=json.loads((ROOT/'workbook/stage196_energy_ml/full_summary.json').read_text())
    assert shape['passed'] and not shape['physical_source_identified'] and shape['energy_fits']==0
    for name in ['docs/nu_mu_energy_ml_revised_roadmap.md','docs/nu_mu_energy_ml_next_step_prompt.md']:
        old=subprocess.check_output(['git','show',f"{p['starting_commit']}:{name}"],cwd=ROOT)
        actual=(ROOT/name).read_bytes();assert actual.endswith(old) and actual.startswith('# 当前执行更新：Stage197'.encode())
    snapshot=json.loads((ROOT/'workbook/stage158_energy_ml/preexisting_asset_snapshot.json').read_text())
    for name,v in snapshot.items():
        st=(ROOT/name).stat();assert st.st_size==v['bytes'] and st.st_mtime_ns==v['mtime_ns']
    subprocess.run(['git','diff','--check'],cwd=ROOT,check=True)
    subprocess.run(['git','diff','--cached','--check'],cwd=ROOT,check=True)
    result=dict(passed=True,scope='Source/text/returned scalar validation; no local scientific event I/O',JSON_N=len(paths),TSV_N=len(tables),Python_AST_N=len(files),
        bash_syntax=True,report_local_links_N=links,historical_suffix_preserved=True,Stage54_size_mtime_preserved_N=len(snapshot),
        actual_prior_negative_decisions_and_shape_limits_inspected=True,user_input_deferral_preserved=True,final_yield_unmeasured=True,overall_complete=False)
    (OUT/'document_validation.json').write_text(json.dumps(result,indent=2)+'\n');print(result)


if __name__=='__main__':main()
