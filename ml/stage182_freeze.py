"""Freeze bounded upstream timing/source support before accessing event payloads."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage182_energy_ml'
OUT.mkdir(parents=True,exist_ok=True);(ROOT/'ntuples/energy_ml_stage182').mkdir(exist_ok=True)
assert not (OUT/'protocol.json').exists()
old=json.loads((ROOT/'workbook/stage179_energy_ml/protocol.json').read_text())
assert json.loads((ROOT/'workbook/stage179_energy_ml/independent_validation.json').read_text())['passed']
p=dict(stage=182,question='Do the fixed12 upstream readouts have strict joint timing and necessary charge-calibration support, and which same-window source categories contribute?',
 indices=old['indices'],pilot_indices=[50],response_stage=179,
 calibration='workbook/stage129_energy_ml/timing_calibration.json',charge_table='workbook/stage179_energy_ml/charge_interventions.tsv',
 pairs=[dict(name='VN0_VN1',i=4,j=5,calibration='0-1'),dict(name='V20_V21',i=6,j=7,calibration='3-4'),dict(name='VN0_V20',i=4,j=6,calibration='0-3'),dict(name='VN1_V20',i=5,j=6,calibration='1-3')],
 status='Only actual wave present, status==0 and finite localtime>0 supplies time; all other rows have null physical time. Legal signed Q retained.',
 calibration_scope='Use original MC calibration usable flags and qi/qj ranges unchanged, as necessary charge support only. Actual track positions are not in these readout records; no full-range certificate, calibrated delta, spatial extrapolation or energy input is produced.',
 sources='Reuse Stage179 same-window six-source analog charges; independent sum from retained split samples. Direct muon/before/after/other/unknown remain source labels, not direction or backscatter truth.',
 time_scope='No extra TOF/phase subtraction. Original digitized 2ns samples and official stored780-980ns window remain fixed. Report source analog charge inside/whole retained ADC range, not global physics integration or extrapolated late tails.',
 summary='All12 parents, all five original VetoNu/Veto channels including absent ones. Pair counts for total/present/status0/strict/strict+necessary Qrange; source totals. Individual raw delta only if strict, no calibration/extrapolation/new fit.',
 acceptance=['Stage179 authoritative raw/source/status exact','pilot/full first parent exact','all12 denominators preserved','independent scalar pair counts and split-integral checks','no finite timing from bad or absent wave'],
 CPU_budget_s=300,phase_CPU_allowance_s=dict(pilot=50,full=150,audit=100),request_CPUs=2,request_memory_MB=4000,max_jobs=1,MaxRuntime_s=86400,
 admission='Threefold complete pilot GNU CPU*12<=150 and used+projection+100audit<=300; no changed selection or budget.',
 stop='If necessary charge support or actual direction/weak-signal calibration is absent, end this fixed candidate with explicit missing inputs; no larger replay/time-window/calibration/model grid.',
 no=['ROOT/G4/reconstruction','new neutrinos','energy fit or forward','time recovery from bad hits','new calibration','backscatter direction inferred from local coordinates','vertex inversion','automatic full4032 replay'],
 preserve=old['preserve'],overall_complete=False,promotion=False)
(OUT/'protocol.json').write_text(json.dumps(p,indent=2)+'\n');print('FROZEN Stage182; no event payload accessed')
