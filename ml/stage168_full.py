"""All exact EVNT headers and retained logged-range evidence, no event scan."""
import csv
import json
import time
from concurrent.futures import ProcessPoolExecutor
from stage168_common import OUT, inputs, read_file, write, logged_ranges


def main():
    cpu, wall = time.process_time(), time.perf_counter()
    assert json.loads((OUT/'admission.json').read_text())['admitted']
    with ProcessPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(read_file, inputs()['unique_paths']))
    records, timings = zip(*results)
    lookup = {r['path']: r for r in records}
    pilot = json.loads((OUT/'pilot_summary.json').read_text())
    assert all(lookup[r['path']] == r for r in pilot['records'])
    ranges = logged_ranges(records); write('logged_ranges.json', ranges)
    write('full_summary.json', dict(passed=True, records=records, timings=timings, pilot_exact=True,
        N_sum=sum(r['N'] for r in records), N_sum_is_independent_interactions=False,
        driver_CPU_s=time.process_time()-cpu, wall_s=time.perf_counter()-wall,
        file_CPU_sum_s=sum(r['CPU_s'] for r in timings), read_bytes=sum(r['read_bytes'] for r in timings),
        logged_ranges_within_actual_N=all(r['within_actual_N'] for r in ranges),
        weight_normalization_certified=False, complete_acceptance_certified=False,
        energy_fits=0, model_forward=0, new_G4=0, promotion=False, overall_complete=False))
    with (OUT/'EVNT_headers.tsv').open('w') as f:
        w = csv.DictWriter(f, fieldnames=['run','nominal','component','path','N','CPU_s','wall_s','read_bytes','RSS_KiB'],
                           delimiter='\t', lineterminator='\n'); w.writeheader()
        timing = {r['path']: r for r in timings}
        for r in inputs()['run_mapping']:
            w.writerow(dict(**r, N=lookup[r['path']]['N'], **{k: timing[r['path']][k]
                for k in ['CPU_s','wall_s','read_bytes','RSS_KiB']}))


if __name__ == '__main__':
    main()
