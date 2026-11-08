"""All admitted PHYS headers, four file processes, one decompression thread each."""
import csv
import json
import time
from concurrent.futures import ProcessPoolExecutor
from stage167_common import OUT, read_file, write


def main():
    cpu, wall = time.process_time(), time.perf_counter()
    assert json.loads((OUT / 'admission.json').read_text())['admitted']
    inv = json.loads((OUT / 'inventory.json').read_text())
    with ProcessPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(read_file, inv['PHYS']['matched']))
    records, timings = zip(*results)
    pilot = json.loads((OUT / 'pilot_summary.json').read_text())
    assert list(records[:3]) == pilot['records']
    write('full_summary.json', dict(passed=True, records=records, timings=timings,
        driver_CPU_s=time.process_time() - cpu, wall_s=time.perf_counter() - wall,
        file_CPU_sum_s=sum(r['CPU_s'] for r in timings), read_bytes=sum(r['read_bytes'] for r in timings),
        N_sum=sum(r['N'] for r in records), N_sum_is_unique_events=False,
        pilot3_exact=True, dataset_exposure_certified=False, dataset_luminosity_pb_inv=None,
        new_G4=0, energy_fits=0, model_forward=0, overall_complete=False, promotion=False))
    columns = ['name', 'N', 'first_event', 'last_event', 'first_time_s', 'last_time_s', 'CPU_s', 'wall_s', 'read_bytes', 'RSS_KiB']
    with (OUT / 'file_headers.tsv').open('w') as f:
        w = csv.DictWriter(f, fieldnames=columns, delimiter='\t', lineterminator='\n'); w.writeheader()
        for r, t in results:
            w.writerow(dict(name=r['name'], N=r['N'], first_event=r['first']['eventID'], last_event=r['last']['eventID'],
                first_time_s=r['first']['eventTime'], last_time_s=r['last']['eventTime'],
                **{k: t[k] for k in ['CPU_s', 'wall_s', 'read_bytes', 'RSS_KiB']}))


if __name__ == '__main__':
    main()
