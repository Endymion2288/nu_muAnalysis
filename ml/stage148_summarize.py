"""Audit one natural mixed-source Ecal control on the original frozen support."""
import csv
import gzip
import json
import resource
import time
from pathlib import Path

OUT = Path('workbook/stage148_energy_ml')
CACHE = Path('ntuples/energy_ml_stage148')


def main():
    tick, cpu = time.perf_counter(), time.process_time()
    support = json.loads((OUT/'support.json').read_text())
    indices = support['selected_indices']
    assert len(indices) <= 1
    if not indices:
        result = dict(passed=True, eligible_mixed_Ecal=0, parents=0,
                      scope='No eligible original train support, no replacement or new response')
    else:
        index = indices[0]
        parent = json.loads((OUT/f'parent_{index}_report.json').read_text())
        source = json.loads((OUT/f'parent_{index}_source_control.json').read_text())
        ecal = json.loads((OUT/f'parent_{index}_summary.json').read_text())
        assert parent['successful'] and parent['legacy_fields_exact'] and parent['case']['role'] == 1
        assert source['passed'] and source['ADC_mismatch'] == 0 and ecal['passed'] and ecal['ADC_mismatch'] == 0
        with gzip.open(CACHE/f'parent_{index}_qa_hits.json.gz', 'rt') as stream:
            snapshot = json.load(stream)
        line = json.loads((OUT/f'parent_{index}_lineage.json').read_text())
        with gzip.open(CACHE/f'parent_{index}_ecal_control.json.gz', 'rt') as stream:
            control = json.load(stream)
        with gzip.open(CACHE/f'parent_{index}_control.json.gz', 'rt') as stream:
            scint = json.load(stream)
        tags = line['daq_hits']['EcalHits']
        assert len(tags) == len(snapshot['EcalHits']) == len(control['source_timing'])
        assert all(tag[4] == hit[0] and tag[7] == hit[3] for tag, hit in zip(tags, snapshot['EcalHits']))
        with (OUT/f'parent_{index}_charge.tsv').open() as stream:
            charges = list(csv.DictReader(stream, delimiter='\t'))
        expected_mixed = [int(row['channel']) for row in charges if float(row['mu_root_pC']) > 0 and float(row['nonmu_root_pC']) > 0]
        assert expected_mixed == ecal['mixed_finite_window_channels']
        assert ecal['geometry_PMTS_including_uncabled'] == 8 and ecal['actual_cabled_PMTS'] == 4
        assert all(float(row['window_start_ns']) == 780 and float(row['window_end_ns']) == 930 for row in charges)
        actual_original = ecal['original_selected_reference_available']
        assert actual_original == scint['original_selected_target_available']
        if actual_original:
            assert ecal['original_calo_status_exact']
        from stage148_window import diagnose
        endpoints = diagnose(index, control, charges)
        result = dict(passed=True, parents=1, train_support_parents=support['train_parents'],
                      eligible_mixed_Ecal=support['eligible_mixed_Ecal'], frame_index=index, case=parent['case'],
                      original_selected_reference_available=actual_original,
                      original_scint_raw11_status_exact=source['original_raw11_status_float32_exact'] if actual_original else None,
                      original_calo_status_exact=ecal['original_calo_status_exact'],
                      original_Calo_raw_charge_reference=ecal['original_Calo_raw_charge_reference'],
                      source_hit_N=len(tags), source_hit_counts={str(c): sum(int(tag[0]) == c for tag in tags) for c in range(3)},
                      source_corrected_hit_response_MeV={str(c): sum(float(hit[1]) for tag, hit in zip(tags, snapshot['EcalHits']) if int(tag[0]) == c) for c in range(3)},
                      Ecal_ADC_samples=ecal['ADC_samples'], Ecal_ADC_mismatch=ecal['ADC_mismatch'],
                      Ecal_clipped_samples=ecal['clipped_samples'], Ecal_clipped_channels=ecal['clipped_channels'],
                      mixed_finite_window_channels=expected_mixed,
                      Ecal_same_channel_window_mixed_certified=bool(expected_mixed),
                      fixed_window_endpoints_recomputed=endpoints['original_finite_window_charge_recomputed'],
                      max_analog_sum_delta_ADC=ecal['max_analog_sum_delta_ADC'],
                      max_window_sum_delta_pC=ecal['max_window_sum_delta_pC'],
                      original_full_private_state_available=ecal['original_full_private_state_available'],
                      original_full_private_states_exact=ecal['original_full_private_states_exact'],
                      Scint_ADC_samples=sum(len(wave['adc']) for record in scint['records'].values() for wave in record['waves']),
                      Scint_clipped_samples=sum(value == 0 for record in scint['records'].values() for wave in record['waves'] for value in wave['adc']),
                      Scint_no_ADC_detectors=[name for name, record in scint['records'].items() if not record['waves']],
                      sensitive_HITS_validation=parent['ordered_hit_validation'],
                      scope='One natural same-parent Ecal source/DAQ method control; not population radiation, data or incident-energy calibration')
    result.update(CPU_s=time.process_time()-cpu, wall_s=time.perf_counter()-tick,
                  RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  new_independent_nu=0, new_energy_fits=0, reserved_forward=0)
    (OUT/'summary.json').write_text(json.dumps(result, indent=2)+'\n')
    print(result, flush=True)


if __name__ == '__main__':
    main()
