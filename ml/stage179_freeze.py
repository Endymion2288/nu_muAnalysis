"""Matched-window response intervention, fixed original12 and explicit limits."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'workbook/stage179_energy_ml'
OUT.mkdir(parents=True, exist_ok=True)
(ROOT / 'ntuples/energy_ml_stage179').mkdir(parents=True, exist_ok=True)
assert not (OUT / 'protocol.json').exists()
old = json.loads((ROOT / 'workbook/stage178_energy_ml/protocol.json').read_text())
assert json.loads((ROOT / 'workbook/stage178_energy_ml/independent_validation.json').read_text())['passed']
p = dict(stage=179, parent_stage=178, question='On the fixed natural12, how much matched-window charge error comes from clipping, noise/baseline and quantization, and which S0 birth sources contribute?',
    indices=[old['reference_index']] + old['replay_indices'], preflight_index=50, remaining_indices=old['replay_indices'],
    selection=old['selection'], runtime='Pinned d32/FASERNU04/tag06, original private seeds; inject exact retained persistent HITS, no G4/reconstruction/Calypso rebuild.',
    sources=['ntuples/energy_ml_stage131/production_cases.json.gz', 'ntuples/energy_ml_stage131/matched_input.npz',
        'ntuples/energy_ml_stage131/pilot_private_rng_states.json.gz', 'ml/artifacts/stage131/energy_predictions.npz'],
    snapshots='Stage176 parent50 and Stage178 remaining11 lineage+ordered HITS; conservative Stage178 interval source labels; no nominal-z or imputed plane.',
    readouts='All original11 scintillator channels and ordinary single-readout Ecal4 only. Preserve all8 geometry PMT noise draws before Ecal cable selection. No imagined dual-range/CaloNu.',
    window='Use each actual official raw window, including endpoints: scint780-980ns and Ecal780-930ns if actual matches. No window scan. Missing ADC remains distinct from measured zero.',
    statistic='Original official signed raw plus exact-algebra decomposition at the same actual window/baseline: analog signal, float-amplitude rounding, actual Gaussian noise draw, ADC integer rounding, clipping, estimated-pedestal error. Ideal analog uses known simulation pedestal and no noise/quantization/clip. No-clip uses same noise and original fitted pedestal; not a hypothetical re-fit or deployable estimator.',
    sources_split='primary muon direct, before-S0 descendants, after-S0 descendants, other root, unknown root, unknown S0. Convolve each source before common noise/ADC; verify additivity with original32float32eps bound. All-time SD is not used as charge.',
    error_diagnostic='Read existing Stage131 cached direct_cal/traditional only on fixed train12 where originally reselected; report individual relative E error with source charges/actual crossing bracket. No new inference/fit or correlation/power/population claim on9 selected parents.',
    acceptance=['actual ADC every sample exact', 'original selected raw11/status/pz0 exact where available',
        'original Calo status exact where available; old raw4 reference absent explicitly', 'parent50 full private RNG initial/final exact',
        'source analog additivity', 'official raw manual float arithmetic closure', 'all12 denominator retained, unknown/missing signed retained'],
    CPU_budget_s=8000, phase_CPU_allowance_s=dict(preflight=1000, full=6000, audit=1000),
    admission='Complete actual preflight GNU CPU*3*11 <=6000 and used schedulerCPU+projection+1000audit <=8000. No full if scientific closure fails. Three separate parent processes on4cores.',
    request_CPUs=4, request_memory_MB=12000, worker_processes=3, max_jobs=1, MaxRuntime_s=86400,
    preserve=old['preserve'], no=['new G4', 'new independent nu', 'new fits/forward', 'actual data calibration claim',
        'extra parents or high-amplitude selection', 'non0status timing', 'charge correction deployment', 'same-source independent energy validation'],
    overall_complete=False, promotion=False)
(OUT / 'protocol.json').write_text(json.dumps(p, indent=2)+'\n')
print('FROZEN Stage179, no scientific array access')
