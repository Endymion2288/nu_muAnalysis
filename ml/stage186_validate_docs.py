"""Static source/package/protocol/report and preserved-asset closure."""
import ast,json,re,subprocess,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage186_energy_ml';files=list((ROOT/'ml').glob('stage186*.py'))
for p in files:ast.parse(p.read_text())
subprocess.run(['bash','-n',str(ROOT/'AnalysisZipFramework/submission/run_ml_stage186.sh')],check=True)
features=json.loads((ROOT/'ml/configs/audited_features.json').read_text());names=features['features']
assert not set(names)&{'ML_mu_p_GeV','ML_track_p0_GeV','ML_track_p1_GeV','ML_track_pz1_GeV','ML_track_log_p0_over_p1'}
assert features['rules']['ML_mu_pz0_GeV']['domain']=='positive'
scint=['VetoNu0','VetoNu1','Veto10','Veto20','Veto21']+[f'Timing{i}' for i in range(4)]+['Preshower0','Preshower1']
for detector in scint:
 assert detector+'_raw_charge' in names and detector+'_charge' not in names
 assert features['rules'][detector+'_raw_charge']==dict(domain='signed',sentinels=[])
phases=[json.loads(p.read_text())['phase'] for p in OUT.glob('*_submission.json')]
with tarfile.open(ROOT/'software/stage186/source_snapshots.tar.gz') as archive:
 idx=json.load(archive.extractfile('source_versions.json'))
 for phase in phases:
  for name in ['protocol.json','source_producers.json']:
   key=phase+'/workbook/stage186_energy_ml/'+name;assert archive.extractfile(idx[key]).read()==(OUT/name).read_bytes()
for name in ['docs/nu_mu_energy_ml_revised_roadmap.md','docs/nu_mu_energy_ml_next_step_prompt.md']:
 old=subprocess.check_output(['git','show','645757f:'+name],cwd=ROOT).decode();assert old in (ROOT/name).read_text()
for name in ['workbook/stage171_energy_ml/next_execution_contract.json','workbook/2026-11-08_stage172_readout-regimes-and-observability-research.md','workbook/2026-11-08_stage172_retraining-and-detector-readout-supplement.md']:
 assert subprocess.check_output(['git','show','645757f:'+name],cwd=ROOT)==(ROOT/name).read_bytes()
report=ROOT/'workbook/2026-11-08_stage186_original-cohort-actual-ideal-energy.md';text=report.read_text();assert len(re.findall('^```',text,re.M))%2==0
for link in re.findall(r'\]\(([^)]+)\)',text):
 if '://' not in link and not link.endswith('/document_validation.json'):assert (report.parent/link).exists(),link
baseline=json.loads((ROOT/'workbook/stage158_energy_ml/preexisting_asset_snapshot.json').read_text())
for name,v in baseline.items():s=(ROOT/name).stat();assert s.st_size==v['bytes'] and s.st_mtime_ns==v['mtime_ns']
subprocess.run(['git','diff','--check'],cwd=ROOT,check=True);subprocess.run(['git','diff','--cached','--check'],cwd=ROOT,check=True)
result=dict(passed=True,python_AST_N=len(files),worker_bash=True,pz0_only_first_power_momentum=True,scint_raw11_signed_policy=True,all_submitted_protocols_and_producer_proofs_exact_N=len(phases),prior_entries_preserved_full=True,user_stage172_documents_unchanged=True,historical_stage172_CaloNu_contract_unchanged=True,Stage54_preserved_N=len(baseline),report_links_fences=True,diff_check=True)
(OUT/'document_validation.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
