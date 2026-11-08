"""New ordinary-Ecal control question after Stage179; historical CaloNu contract untouched."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage183_energy_ml';OUT.mkdir(exist_ok=True)
(ROOT/'ntuples/energy_ml_stage183').mkdir(exist_ok=True)
assert not (OUT/'protocol.json').exists()
old=json.loads((ROOT/'workbook/stage171_energy_ml/next_execution_contract.json').read_text())
assert json.loads((ROOT/'workbook/stage179_energy_ml/independent_validation.json').read_text())['passed']
p=dict(stage=183,question='Do ordinary Ecal Lo0-3 and Hi16-19 have reproducible joint signed-integral correlations in actual strict random controls, sufficient to motivate any new joint estimator?',
 motivation='Stage179 matched MC12 ordinary Ecal charge error is dominated by noise/baseline with zero clipping loss; Stage173 identifies actual ordinary Ecal and excludes normal CaloNu migration. This new bounded ordinary-Ecal descriptive measurement is not execution of historical Stage172 CaloNu variance/25-channel contract.',
 source_contract='workbook/stage171_energy_ml/next_execution_contract.json',paths=old['paths'],catalog=old['catalog'],run=15838,
 reference='ntuples/energy_ml_stage171/pilot_rows.jsonl.gz',GRL=old['GRL'],mapping='workbook/stage173_energy_ml/condition_records.json',
 pilot_files=[400,401],full_files=list(range(402,432)),audit_RAW_files=[400,401],limits=old['limits'],windows=old['windows'],
 active_groups=dict(ordinary_Ecal_Lo=[0,1,2,3],ordinary_Ecal_Hi=[16,17,18,19]),
 ADC='Keep all actual hardware ADC for strict controls only, no amplitude/status/GRL veto. Valid unique decoded nonfailed boards and finite sufficient sample length are required per channel measurement; missing/bad support stays null, all triggers remain denominators.',
 strict_selection=old['strict_selection'],measurement=old['measurement'],units='ADC-code*samples only; no pC/gain/PMT calibration or matching MC/data window claim.',
 statistics=['For signal_diagnostic/offpulse: eight-channel pairwise N/covariance/correlation; complete8 covariance rank/eigenvalues, no inverse.',
 'Per ordinary-Ecal group and fixed window: variance of four-channel sum / sum of four variances on exactly same complete4 events.',
 '1000 fixedseed20261108183 file-block bootstrap conditional95 intervals for four fixed ratios, no discovery scan.',
 'First16 and last16 fileblocks same four ratios, retain empty files/unknowns.',
 'All actual channel lengths/status/input bits/GRL/timestamps/rail counts, no amplitude cleaning; no pure-noise assertion.'],
 applicability='Only actual run15838 prefix conditions/ordinary Ecal hardware and fixed raw windows. CaloNu20-23 and clock31 may be retained as audit bytes but supply no response inference. Exact DAQ config, signal purity and target MC migration remain uncertified.',
 acceptance=['Original400 full8192 metadata/all retained ADC exact vs Stage171','401 framing and at least1 actual strict control','all32 literal paths in existing actual catalog','independent RAW400/401 reread','scalar integrals and scalar ratio/covariance checks','all32 denominators and fileblocks preserved'],
 admission='Threefold complete pilot GNU CPU*32/2 <=1400 and used+projection+600audit<=2400; valid401 control required. No path replacement or budget growth.',
 CPU_budget_s=2400,phase_CPU_allowance_s=dict(pilot=400,full=1400,audit=600),request_CPUs=4,request_memory_MB=8000,worker_processes=4,max_jobs=1,MaxRuntime_s=86400,
 stop='Descriptive evidence only. Unknown purity, weak support or file instability prevents estimator certification; no inverse/shrinkage/prior/automatic injection or energy refit. A future estimator requires separate signal-fidelity, charge-error/coverage and matched-regime support.',
 no=old['no']+['CaloNu migration certification','timing from bad hits','claiming measured improvement of E_nu from covariance'],preserve=old['preserve'],overall_complete=False,promotion=False)
(OUT/'protocol.json').write_text(json.dumps(p,indent=2)+'\n');print('FROZEN Stage183 ordinary Ecal controls; historical Stage172 untouched')
