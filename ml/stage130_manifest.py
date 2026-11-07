"""Stdlib-only complete, compact immutable analysis input manifest."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'workbook/stage130_energy_ml'


def main():
    progress = json.loads((OUT / 'production_progress.json').read_text())
    assert progress['complete'] and not progress['failed'], 'All frozen sources must return before preparation'
    contract = json.loads((OUT / 'production_contract.json').read_text())
    files = [str(p.relative_to(ROOT)) for p in sorted((ROOT / 'ml').glob('*.py'))]
    files += ['ml/configs', 'workbook/stage87_energy_ml/protocol.json',
              'workbook/stage119_energy_ml/exposure_inputs.json',
              'ntuples/energy_ml_stage119/old_input.npz', 'ntuples/energy_ml_stage119/curve_input.npz',
              'ml/artifacts/stage87/predictions.npz']
    files += [f'ml/artifacts/stage87/direct_{seed}.ubj' for seed in [2026110255, 2026110256, 2026110257]]
    files += json.loads((ROOT / 'workbook/stage119_energy_ml/exposure_inputs.json').read_text())
    files += ['workbook/stage130_energy_ml/'+name for name in
              ['source_protocol.json', 'production_contract.json', 'production_parentmap_amendment.json',
               'production_concurrency_amendment.json',
               'parent_event_entry_validation.json']]
    for index in contract['all_source_indices']:
        phase = 'support' if index in contract['pilot_reused'] else 'production'
        files += [f'ntuples/energy_ml_stage130/{phase}_{index}/'+name
                  for name in ['selected.npz', 'exitcode.txt'] + (['parentmap.json'] if phase == 'production' else [])]
    files = list(dict.fromkeys(files))
    assert all((ROOT / name).exists() for name in files)
    destination = Path('/tmp/stage130_analysis_files.json')
    destination.write_text(json.dumps(files, indent=2)+'\n')
    print(destination, 'files', len(files), 'file bytes', sum((ROOT / p).stat().st_size for p in files if (ROOT / p).is_file()))


if __name__ == '__main__':
    main()
