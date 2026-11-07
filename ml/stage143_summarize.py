"""Summarize every admitted VetoNu control on the original denominators."""
import csv
import gzip
import json
import resource
import time
from pathlib import Path

OUT = Path('workbook/stage143_energy_ml')
CACHE = Path('ntuples/energy_ml_stage143')


def table(name, rows):
    if not rows:
        return
    with (OUT/name).open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter='\t', lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def main():
    tick, cpu = time.perf_counter(), time.process_time()
    support = json.loads((OUT/'support.json').read_text())
    indices = support['selected_indices']
    parents, hits, adc, charges = [], [], [], []
    for index in indices:
        admission = json.loads((OUT/f'parent_{index}_admission.json').read_text())
        assert admission['admitted']
        report = json.loads((OUT/f'parent_{index}_report.json').read_text())
        assert report['successful'] and report['legacy_fields_exact']
        case = report['case']
        assert case['role'] == 1
        line = json.loads((OUT/f'parent_{index}_lineage.json').read_text())
        with gzip.open(CACHE/f'parent_{index}_qa_hits.json.gz', 'rt') as stream:
            snapshot = json.load(stream)
        with gzip.open(CACHE/f'parent_{index}_control.json.gz', 'rt') as stream:
            control = json.load(stream)
        source = json.loads((OUT/f'parent_{index}_source_control.json').read_text())
        assert source['passed'] and source['ADC_mismatch'] == 0
        assert snapshot['VetoNuHits'] and control['records']['VetoNu']['waves']
        original = control['original_selected_target_available']
        assert source['original_raw11_status_float32_exact'] == original
        parents.append(dict(index=index, component=case['component'], stratum=case['stratum'],
                            truth_E_GeV=case['truth_E_GeV'], original_selected_target_available=original,
                            original_raw_status_exact=source['original_raw11_status_float32_exact'],
                            source_sum_max_delta_pC=source['max_window_sum_delta_pC'],
                            source_sum_max_delta_ADC=source['max_analog_sum_delta_ADC'], wall_s=report['wall_s']))
        for collection in ['VetoNuHits', 'VetoHits', 'TriggerHits', 'PreshowerHits', 'EcalHits']:
            tags, saved = line['daq_hits'].get(collection, []), snapshot[collection]
            assert len(tags) == len(saved)
            for category in [0, 1, 2]:
                selected = [row for tag, row in zip(tags, saved) if int(tag[0]) == category]
                hits.append(dict(index=index, collection=collection, root_category=category,
                                 hits=len(selected), persistent_response_MeV=sum(r[1] for r in selected)))
        for detector, record in control['records'].items():
            waves = record['waves']
            adc.append(dict(index=index, detector=detector, ADC_present=bool(waves),
                            samples=sum(len(w['adc']) for w in waves),
                            clipped_samples=sum(v == 0 for w in waves for v in w['adc']),
                            nonzero_status_channels=sum(int(w['result'][0]) != 0 for w in waves)))
        with (OUT/f'parent_{index}_source_analog_charge.tsv').open() as stream:
            for row in csv.DictReader(stream, delimiter='\t'):
                total = float(row['total_analog_pC'])
                charges.append(dict(index=index, **row,
                                    nonmu_analog_fraction=float(row['nonmu_root_pC'])/total if total > 0 else 'NA'))
    table('parent_summary.tsv', parents)
    table('source_hit_response.tsv', hits)
    table('ADC_summary.tsv', adc)
    table('source_charge_summary.tsv', charges)
    result = dict(passed=True, train_support_parents=support['train_parents'],
                  positive_VetoNu_parents=support['positive_VetoNu'], controls=len(indices), indices=indices,
                  ADC_samples=sum(r['samples'] for r in adc), ADC_mismatch=0,
                  clipped_samples=sum(r['clipped_samples'] for r in adc),
                  original_raw11_status_exact_parents=[r['index'] for r in parents if r['original_raw_status_exact']],
                  original_selected_reference_missing_parents=[r['index'] for r in parents if not r['original_selected_target_available']],
                  original_full_private_state_comparison='unavailable for these parents; original seed rule reproduced',
                  max_window_sum_delta_pC=max((r['source_sum_max_delta_pC'] for r in parents), default=None),
                  CPU_s=time.process_time()-cpu, wall_s=time.perf_counter()-tick,
                  RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  new_independent_nu=0, new_energy_fits=0, reserved_forward=0, promotion=False,
                  scope='VetoNu signal method coverage only; no low-energy performance, EcalDAQ, population radiation-tail or actual-data certification')
    (OUT/'summary.json').write_text(json.dumps(result, indent=2)+'\n')
    print(result)


if __name__ == '__main__':
    main()
