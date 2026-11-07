"""Audit four cached Ecal controls; no response extrapolation or energy fit."""
import csv
import json
import resource
import time
from pathlib import Path

OUT = Path('workbook/stage144_energy_ml')


def main():
    tick, cpu = time.perf_counter(), time.process_time()
    plan = json.loads((OUT/'protocol.json').read_text())
    parents, charges = [], []
    for index in plan['indices']:
        row = json.loads((OUT/f'parent_{index}_summary.json').read_text())
        assert row['passed'] and row['ADC_mismatch'] == 0
        assert row['original_calo_status_exact'] is True or row['original_selected_reference_available'] is False
        parents.append(row)
        with (OUT/f'parent_{index}_charge.tsv').open() as stream:
            charges.extend(csv.DictReader(stream, delimiter='\t'))
    for name, rows in [('parent_summary.tsv', parents), ('source_charge_summary.tsv', charges)]:
        with (OUT/name).open('w') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter='\t', lineterminator='\n')
            writer.writeheader()
            writer.writerows(rows)
    result = dict(passed=True, controls=len(parents), indices=plan['indices'],
                  ADC_samples=sum(r['ADC_samples'] for r in parents), ADC_mismatch=0,
                  clipped_samples=sum(r['clipped_samples'] for r in parents),
                  original_calo_status_exact_parents=[r['frame_index'] for r in parents if r['original_calo_status_exact']],
                  original_selected_reference_missing_parents=[r['frame_index'] for r in parents if not r['original_selected_reference_available']],
                  original_full_private_states_exact_parents=[r['frame_index'] for r in parents if r['original_full_private_states_exact']],
                  max_analog_sum_delta_ADC=max(r['max_analog_sum_delta_ADC'] for r in parents),
                  max_window_sum_delta_pC=max(r['max_window_sum_delta_pC'] for r in parents),
                  scope='Actual Ecal/source method only; original Calo raw charge reference not retained; no energy risk or population/data certification',
                  CPU_s=time.process_time()-cpu, wall_s=time.perf_counter()-tick,
                  RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  new_G4=0, new_independent_nu=0, new_energy_fits=0, reserved_forward=0, promotion=False)
    (OUT/'summary.json').write_text(json.dumps(result, indent=2)+'\n')
    print(result)


if __name__ == '__main__':
    main()
