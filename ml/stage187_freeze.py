"""Text-only freeze of the already bounded twelve-parent energy ledger."""
import json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage187_energy_ml'
if __name__=='__main__':
 OUT.mkdir(exist_ok=True);assert not (OUT/'protocol.json').exists()
 p=json.loads((ROOT/'workbook/stage186_energy_ml/next_execution_contract.json').read_text())
 assert not json.loads((ROOT/'workbook/stage186_energy_ml/decision_summary.json').read_text())['main_I_over_R_expansion_pass']
 p.update(stage=187,starting_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),phase_CPU_caps_s=dict(pilot=40,analysis=100,audit=100),muon_mass_MeV=105.6583755)
 sources=['ml/stage176_observer/NuMuS0Observer/src/Observer.cxx','ml/stage178_common.py','ml/configs/audited_features.json',
  'workbook/stage176_energy_ml/parent_50_S0.json','workbook/stage178_energy_ml/state_boxes.json',
  'workbook/stage179_energy_ml/charge_interventions.tsv','workbook/stage179_energy_ml/parent_diagnostics.tsv',
  'ntuples/energy_ml_stage131/matched_input.npz','ntuples/energy_ml_stage131/production_cases.json.gz']
 for stage in [178,179]:sources.append(f'workbook/stage{stage}_energy_ml/independent_validation.json')
 for i in p['parents']:
  sources += [f'ntuples/energy_ml_stage{176 if i==50 else 178}/parent_{i}_lineage.json.gz',f'workbook/stage178_energy_ml/parent_{i}_intervals.json']
 p['sources']=sources;p['source_semantics']='confirmed means unique primary barcode/pdg and neutrino production parent matched; see existing prepare_transfer_supervision.py and truth_diagnostics. Without confirmed, fitted-vs-primary interpretation remains unknown.'
 (OUT/'protocol.json').write_text(json.dumps(p,indent=2,ensure_ascii=False)+'\n');print('Frozen original12, 240CPU s, no new G4 or fits')
