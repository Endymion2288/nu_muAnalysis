"""A bounded post-hoc mechanism question on the unchanged Stage188/192 cohort."""
import json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage193_energy_ml'
if __name__=='__main__':
 OUT.mkdir(exist_ok=True);assert not (OUT/'protocol.json').exists()
 p=dict(stage=193,starting_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
  question='Are retained direct-primary IFT pull sums associated with the frozen fitted-track primary-barcode support? Post-hoc mechanism diagnostic after Stage192 charm RMS, not a new gate, coverage calibration or energy optimization.',
  inputs=['ntuples/energy_ml_stage188/full_native.json.gz','ntuples/energy_ml_stage192/full_native.json.gz','ntuples/energy_ml_stage192/pilot_native.json.gz'],
  parents='Exact original160 full and16 pilot. No replacements, no role0/reserved, no native re-read, no transport/G4/fit/inference.',
  categories=['graph_unknown','no_fitted_track','no_primary_fit_barcode','primary_and_other_fit_barcodes','primary_only_stored_fit_barcodes'],
  categories_definition='Using actual unique primary pointer label from192, and only original188 unweighted fitted-cluster barcode counts. Other=any positive count for another barcode. A missing primary barcode does not certify a wrong track: fitted-cluster SDO completeness and direct pointer identity not available here.',
  statistics='Every parent retained. Conditional original matched/start-supported/geometric-inside candidates: perclass N,sum pull²,sum residual²,max abs pull,abs pull>3 N. All parents by source and fixed category; ratios of square sums are descriptive, not independent particle fractions. Report all rows; no top-k/cut/seed search. Reproduce192 totals and16 pilot exactly.',
  admission='First original16, exact identities/classes, measured complete pilot*30 plus full160 slowest scalar parent*3<=100CPU, pilot used+projection+100 audit<=300;RSS*1.25<=4000MB. Otherwise no full.',
  resources=dict(CPU_budget_s=300,phase_CPU_s=dict(pilot=100,full=100,audit=100),requested_CPUs=2,memory_MB=4000,max_live_jobs=1,cache_cap_B=1048576),
  promotion=False,overall_complete=False)
 (OUT/'protocol.json').write_text(json.dumps(p,indent=2)+'\n')
 print('FROZEN Stage193, same160 cached parents,300CPU seconds, zero new fits/native')
