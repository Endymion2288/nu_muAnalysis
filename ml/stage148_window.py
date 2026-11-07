"""Fixed acquisition endpoints explain response support; never optimize a window."""
import json
from pathlib import Path

import ROOT


def diagnose(index, records, charges):
    assert ROOT.gInterpreter.Declare(Path('ml/stage141_analog.hxx').read_text())
    seed = 650000000+10000*index
    full = [value for row in records['source_timing'] for value in [row[0], row[3], row[1]]]
    samples = len(records['waves'][0]['adc'])
    total = [list(row) for row in ROOT.Stage141Analog(full, records['conditions'], records['all_geometry_PMTS'], seed, samples)]
    categories = {}
    for category in range(3):
        hits = [value for row in records['source_timing'] if int(row[5]) == category for value in [row[0], row[3], row[1]]]
        categories[category] = [list(row) for row in ROOT.Stage141Analog(hits, records['conditions'], records['all_geometry_PMTS'], seed, samples)]
    rows = []
    conversion = 2*2/16384/50*1000
    for wave in records['waves']:
        ident, channel = wave['id32'], wave['channel']
        take = [j for j, row in enumerate(total) if int(row[0]) == ident]
        reference = next(row for row in charges if int(row['channel']) == channel)
        finite = [j for j in take if float(reference['window_start_ns']) <= 2*total[j][1] <= float(reference['window_end_ns'])]
        q = conversion*sum(total[j][2] for j in finite)
        assert abs(q-float(reference['total_analog_pC'])) <= 1e-12+1e-10*abs(q)
        for category in range(3):
            hits = [row for row in records['source_timing'] if int(row[0]) == ident and int(row[5]) == category]
            weight = sum(row[1] for row in hits)
            fullq = conversion*sum(categories[category][j][2] for j in take)
            windowq = conversion*sum(categories[category][j][2] for j in finite)
            peak = max(take, key=lambda j: categories[category][j][2])
            rows.append(dict(channel=channel, category=category, hits=len(hits), corrected_hit_response_MeV=weight,
                corrected_hit_time_min_ns=min((row[3] for row in hits), default=None),
                corrected_hit_time_max_ns=max((row[3] for row in hits), default=None),
                corrected_hit_time_energy_mean_ns=sum(row[1]*row[3] for row in hits)/weight if weight > 0 else None,
                hit_response_below_digitizer_histogram_MeV=sum(row[1] for row in hits if row[3] < -20),
                hit_response_above_digitizer_histogram_MeV=sum(row[1] for row in hits if row[3] >= 1200),
                acquisition_analog_pC=fullq, raw_window_analog_pC=windowq,
                raw_window_over_acquisition=windowq/fullq if fullq > 0 else None,
                model_pulse_peak_ns=2*categories[category][peak][1] if fullq > 0 else None,
                interpretation='Internal source-response QA only; never measured Good-Hit timing or a new analysis window'))
    output = dict(frame_index=index, fixed_acquisition_sample_times_ns=[0, 2*(samples-1)],
                  fixed_digitizer_hit_histogram_ns=[-20, 2*samples], fixed_raw_window_ns=[780, 930],
                  original_finite_window_charge_recomputed=True, rows=rows,
                  timing_input_created=False, new_fits=0, window_scan=False)
    Path(f'workbook/stage148_energy_ml/parent_{index}_window_endpoints.json').write_text(json.dumps(output, indent=2)+'\n')
    return output
