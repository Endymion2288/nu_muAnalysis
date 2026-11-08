"""Static and exact-byte documentation checks; no event/scientific array access."""
import argparse
import ast
import json
import re
import subprocess
import tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--stage',type=int,default=170);args=parser.parse_args();stage=args.stage
out=ROOT/f'workbook/stage{stage}_energy_ml';checks={}
files=list((ROOT/'ml').glob(f'stage{stage}*.py'))
for p in files:ast.parse(p.read_text())
checks['Python_AST_N']=len(files)
subprocess.run(['bash','-n',str(ROOT/f'AnalysisZipFramework/submission/run_ml_stage{stage}.sh')],check=True)
checks['worker_syntax']=True
with tarfile.open(ROOT/f'software/stage{stage}/source_snapshots.tar.gz') as t:
 idx=json.load(t.extractfile('source_versions.json'))
 phases=sorted({k.split('/')[0] for k in idx if k.endswith('/protocol.json')})
 for phase in phases:
  for name in ['protocol.json','header_sources.json']:
   key=f'{phase}/workbook/stage{stage}_energy_ml/{name}'
   assert t.extractfile(idx[key]).read()==(out/name).read_bytes()
checks['frozen_phase_protocol_and_headers_exact']=phases
for name in ['docs/nu_mu_energy_ml_revised_roadmap.md','docs/nu_mu_energy_ml_next_step_prompt.md']:
 old=subprocess.check_output(['git','show','HEAD:'+name],cwd=ROOT).decode();assert old in (ROOT/name).read_text()
checks['prior_documents_retained_full']=True
report=next((ROOT/'workbook').glob(f'2026-11-08_stage{stage}_*.md'));text=report.read_text()
assert len(re.findall(r'^```',text,re.M))%2==0
for link in re.findall(r'\]\(([^)]+)\)',text):
 if '://' not in link:assert (report.parent/link).exists(),link
checks['report_fences_links']=True
baseline=json.loads((ROOT/'workbook/stage158_energy_ml/preexisting_asset_snapshot.json').read_text())
for name,v in baseline.items():s=(ROOT/name).stat();assert s.st_size==v['bytes'] and s.st_mtime_ns==v['mtime_ns']
checks['Stage54_preserved_N']=len(baseline)
subprocess.run(['git','diff','--check'],cwd=ROOT,check=True)
checks['passed']=True;(out/'document_validation.json').write_text(json.dumps(checks,indent=2)+'\n');print(checks)
