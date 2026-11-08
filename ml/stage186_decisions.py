"""Report frozen content and deployment gates without selecting a new policy."""
import csv,json
from stage186_common import OUT,table,write
p=list(csv.DictReader((OUT/'energy_paired.tsv').open(),delimiter='\t'))
validation=json.loads((OUT/'independent_validation.json').read_text());joint=json.loads((OUT/'energy_summary.json').read_text())['joint']
rows=[r for r in p if r['role'] in ['2','3'] and r['stratum'] in ['E50_100','E100_200'] and (r['candidate'],r['reference']) in [('I','R'),('I','A'),('R','A'),('A','traditional'),('R','traditional'),('I','traditional'),('I','direct_cal'),('R','direct_cal')]]
table('low_energy_decisions.tsv',rows)
if validation['expansion_gate']['I/R']:next_step='Conditional ideal-information support: quantify same-window error/clip support and identify independently calibratable response before any new estimator/hybrid training; ideal is not deployable.'
else:next_step='Fixed ideal-information contrast does not meet both-low Stage137 expansion gate. End this three-arm representation, no window/model/seed grid or waveform estimator expansion on these results; prioritize existing geometry/radiation mechanism support and actual external anchors.'
write('decision_summary.json',dict(passed=True,main_I_over_R_expansion_pass=validation['expansion_gate']['I/R'],content_expansion_gates=validation['expansion_gate'],original_joint_gates=joint,new_actual_R_joint_cal_test=bool(joint['2_R'] and joint['3_R']),Stage87_unchanged=True,promotion=False,independent_confirmation=False,overall_complete=False,next=next_step,limits='Current developed original selected cohort; conditional incoming intervals; no certified real-data error model, weighted physical spectrum/efficiency/background or independent confirmation.'))
