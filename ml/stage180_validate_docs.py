"""Static stage closure and frozen protocol checks, no scientific array access."""
import ast,json,re,subprocess,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage180_energy_ml';checks={}
files=list((ROOT/'ml').glob('stage180*.py'))
for p in files:ast.parse(p.read_text())
subprocess.run(['bash','-n',str(ROOT/'AnalysisZipFramework/submission/run_ml_stage180.sh')],check=True)
with tarfile.open(ROOT/'software/stage180/source_snapshots.tar.gz') as t:
 idx=json.load(t.extractfile('source_versions.json'))
 for phase in ['pilot','full','audit']:
  key=phase+'/workbook/stage180_energy_ml/protocol.json';assert t.extractfile(idx[key]).read()==(OUT/'protocol.json').read_bytes()
for name in ['docs/nu_mu_energy_ml_revised_roadmap.md','docs/nu_mu_energy_ml_next_step_prompt.md']:
 old=subprocess.check_output(['git','show','HEAD:'+name],cwd=ROOT).decode();assert old in (ROOT/name).read_text()
for name in ['workbook/2026-11-08_stage172_readout-regimes-and-observability-research.md','workbook/2026-11-08_stage172_retraining-and-detector-readout-supplement.md']:
 assert subprocess.check_output(['git','show','HEAD:'+name],cwd=ROOT)==(ROOT/name).read_bytes()
report=ROOT/'workbook/2026-11-08_stage180_ordinary-Ecal-dual-range-support.md';text=report.read_text();assert len(re.findall('^```',text,re.M))%2==0
for link in re.findall(r'\]\(([^)]+)\)',text):
 if '://' not in link and not link.endswith('/document_validation.json'):assert (report.parent/link).exists(),link
baseline=json.loads((ROOT/'workbook/stage158_energy_ml/preexisting_asset_snapshot.json').read_text())
for p,v in baseline.items():s=(ROOT/p).stat();assert s.st_size==v['bytes'] and s.st_mtime_ns==v['mtime_ns']
subprocess.run(['git','diff','--check'],cwd=ROOT,check=True)
subprocess.run(['git','diff','--cached','--check'],cwd=ROOT,check=True)
checks=dict(passed=True,python_AST_N=len(files),worker_bash=True,frozen_phase_protocols_exact=3,
 prior_entries_preserved_full=True,user_stage172_documents_unchanged=True,Stage54_preserved_N=len(baseline),report_links_fences=True,diff_check=True)
(OUT/'document_validation.json').write_text(json.dumps(checks,indent=2)+'\n');print(checks)
