"""Static final report and unchanged protocol/prior-source verification."""
import ast,json,re,subprocess,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage187_energy_ml';files=list((ROOT/'ml').glob('stage187*.py'))
for f in files:ast.parse(f.read_text())
subprocess.run(['bash','-n',str(ROOT/'AnalysisZipFramework/submission/run_ml_stage187.sh')],check=True)
with tarfile.open(ROOT/'software/stage187/source_snapshots.tar.gz') as t:
 for phase in ['pilot','analysis','audit']:assert t.extractfile(phase+'/workbook/stage187_energy_ml/protocol.json').read()==(OUT/'protocol.json').read_bytes()
for name in ['docs/nu_mu_energy_ml_revised_roadmap.md','docs/nu_mu_energy_ml_next_step_prompt.md']:
 assert subprocess.check_output(['git','show','35b38e3:'+name],cwd=ROOT).decode() in (ROOT/name).read_text()
for name in ['workbook/stage186_energy_ml/next_execution_contract.json','workbook/stage171_energy_ml/next_execution_contract.json','workbook/2026-11-08_stage172_readout-regimes-and-observability-research.md','workbook/2026-11-08_stage172_retraining-and-detector-readout-supplement.md']:
 assert subprocess.check_output(['git','show','35b38e3:'+name],cwd=ROOT)==(ROOT/name).read_bytes()
report=ROOT/'workbook/2026-11-08_stage187_S0-primary-energy-and-window-ledger.md';text=report.read_text();assert len(re.findall('^```',text,re.M))%2==0
for link in re.findall(r'\]\(([^)]+)\)',text):
 if '://' not in link and not link.endswith('/document_validation.json'):assert (report.parent/link).exists(),link
before=json.loads((ROOT/'workbook/stage158_energy_ml/preexisting_asset_snapshot.json').read_text())
for name,v in before.items():s=(ROOT/name).stat();assert s.st_size==v['bytes'] and s.st_mtime_ns==v['mtime_ns']
subprocess.run(['git','diff','--check'],cwd=ROOT,check=True);subprocess.run(['git','diff','--cached','--check'],cwd=ROOT,check=True)
result=dict(passed=True,python_AST_N=len(files),bash=True,three_submitted_protocols_exact=True,prior_roadmap_full_preserved=True,stage172_and_historical_contracts_unchanged=True,Stage54_preserved_N=len(before),links_fences=True,diff_check=True)
(OUT/'document_validation.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
