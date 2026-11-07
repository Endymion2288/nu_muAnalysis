"""Freeze exact text manifests and pilot before reading new observables."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage129_energy_ml'


def main():
    OUT.mkdir(exist_ok=True)
    (ROOT/'ntuples/energy_ml_stage129').mkdir(exist_ok=True)
    p = json.loads((ROOT/'workbook/stage124_energy_ml/native_contract.json').read_text())
    manifests = {55:list(csv.DictReader((ROOT/'ml/configs/low_energy_files.tsv').open(), delimiter='\t'))}
    for stage, path in [(70,'ml/configs/alternative_support_pilot.json'), (81,'workbook/stage81_energy_ml/source_plan.json'), (82,'workbook/stage82_energy_ml/production_protocol.json'), (83,'workbook/stage83_energy_ml/protocol.json')]:
        manifests[stage] = json.loads((ROOT/path).read_text())['sources']
    for source in p['requests']:
        source['phys'] = manifests[source['origin']][source['source_index']].get('input')
    pilot = [next(s['index'] for s in p['requests'] if s['origin']==55 and s['component']==c and any(x['role']==1 for x in s['cases'])) for c in ['pi','k','charm']]
    contract = dict(stage=129, starting_commit='6b9d101', requests=p['requests'], pilot_indices=pilot, pilot_per_source=32)
    assert not (OUT/'extraction_contract.json').exists()
    (OUT/'extraction_contract.json').write_text(json.dumps(contract, separators=(',',':'))+'\n')
    protocol = dict(stage=129, starting_commit='6b9d101',
        scope='Stage128 section9: saturation, strict timing, current depth oracle; independent support and response systems retain their conditional gates',
        pilot=dict(source_indices=pilot, per_source_train=32, selection='first32 original train entries in first nominal pi/k/charm source; no risk selection', cpus=2, memory_MB=4000, wall_limit_s=7200),
        invariants='original89033 roles/K/pz0/raw11/signed/typedNaN/Calo missing/formal cuts; quarantine and reserved zero prediction',
        waveform_validation=dict(artificial_rail_peak_fractions=[.75,.5,.25], target='same finite W original uncut waveform integral; ADC recovery only', comparison=['clipped raw','official CB','constrained template censored recovery'], control_holdout='source-disjoint templates and validation; repeated artificial views stay within parent role'),
        timing=dict(pair_candidates=['VetoNu0-VetoNu1','Veto20-Veto21','VetoNu0-Veto20','VetoNu1-Veto20'], strict='both status exactly0, present finite nonnegative acquisition times; invalid delta NaN, all rows retained', calibration='mu control/reference required; no E/z/test-label tuning; uncalibrated times not input'),
        depth='full current X62 vs truthz/material oracle first; deployment track compatibility conditional on benefit and actual covariances',
        learning='Stage87 fixed3seeds400round hist tree, matched train/cal; no outcome-based seed/window/pair grid',
        final_gates='original8 strata: two-low/traditional upper95<=1.05 noninferiority only; all/f0<=1.01; five others/f0<=1.03; three tail50 upper95<=+2pp',
        before_new_risk='freeze scale/features/template complexity/uncertainty policy after measured schema/cost pilot',
        pending=['ADC pilot','formal scale freeze','artificial clipping validation','matched energy A controls','strict timing coverage/calibration and B if valid','depth oracle and C if justified','response variation and real-control closure','independent full-chain pilot and N0~2N0 feasibility','validation/resources/storage/report/commit'])
    (OUT/'protocol.json').write_text(json.dumps(protocol, ensure_ascii=False, indent=2)+'\n')
    files=['ml/stage129_extract.py','ml/stage122_saved.py','setup_env.sh','workbook/stage129_energy_ml/extraction_contract.json']
    Path('/tmp/stage129_pilot_files.json').write_text(json.dumps(files))
    print('pilot_indices', *pilot)


if __name__ == '__main__':
    main()
