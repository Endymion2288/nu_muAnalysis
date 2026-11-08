"""One fixed timing diagnostic for the observed ordinary-Ecal ratio dependence."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage181_energy_ml'
OUT.mkdir(parents=True,exist_ok=True);(ROOT/'ntuples/energy_ml_stage181').mkdir(parents=True,exist_ok=True)
assert not (OUT/'protocol.json').exists()
old=json.loads((ROOT/'workbook/stage180_energy_ml/protocol.json').read_text())
assert json.loads((ROOT/'workbook/stage180_energy_ml/independent_validation.json').read_text())['passed']
p=dict(stage=181,question='Are the measured dual-range charge-ratio tails and amplitude trends associated with inconsistent stored pulse times?',
    PHYS=old['PHYS'],condition_input=old['condition_input'],control_input=old['control_input'],relative_input='workbook/stage180_energy_ml/full_summary.json',
    pilot_N=8192,bins_raw_peak_mV=old['bins_raw_peak_mV'],selection=old['selection'],
    timing='Read actual localtime and bcidtime for original8 PMTs. Existence only when both status0, finite localtime>0 and finite bcidtime not explicit-999; no time fallback or extra phase subtraction. Keep raw-local and stored-bcid differences separate; do not assume cross-board clock calibration.',
    fit='Per module one median Hi-Lo time offset on even highSNR original controls, separately local/bcid. Q scale stays exactly Stage180, no Q refit. Odd-only fixed amplitude-bin comparison, no window/timing model grid.',
    diagnostic='Fixed abs(time residual)<=2ns band is descriptive, not a signal-purity or calibrated-resolution gate. Compare charge-ratio residual distributions in/out/all. All original denominators retained; no cut applied to any energy model.',
    acceptance=['original128 native scalar readout comparisons','strict-only native localtime comparisons where actually present',
        'pilot/full8192 exact','independent full reread plus scalar support/time-median/old-Q-scale checks','unsupported time branches or empty controls explicit'],
    CPU_budget_s=900,phase_CPU_allowance_s=dict(pilot=150,full=600,audit=150),request_CPUs=4,request_memory_MB=8000,max_jobs=1,MaxRuntime_s=86400,
    admission='Same startup/two4096-chunk timing model; threefold full projection<=600 and used+projection+150audit<=900, otherwise finite stop.',
    no=['waveform/ADC reconstruction','new calibration or PMT-nonlinearity claim','new energy fit/forward','changed Q/timing selection','discarding inconsistent pulses','additional sources or scanned timing bands'],
    preserve=old['preserve'],overall_complete=False,promotion=False)
(OUT/'protocol.json').write_text(json.dumps(p,indent=2)+'\n');print('FROZEN Stage181; no event access')
