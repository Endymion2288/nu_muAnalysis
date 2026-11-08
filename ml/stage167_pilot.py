"""The frozen first three PHYS files after one listing per known directory."""
import time
from stage167_common import inventory, coverage, read_file, write, plan


def main():
    cpu, wall = time.process_time(), time.perf_counter()
    inv = inventory(); write('inventory.json', inv); write('range_coverage.json', coverage(inv))
    files = inv['PHYS']['matched'][:3]
    assert len(files) == 3 and plan()['inputs']['reference_PHYS'] in [r['path'] for r in files]
    records, timings = [], []
    for f in files:
        r, t = read_file(f); records.append(r); timings.append(t)
    write('pilot_summary.json', dict(passed=True, records=records, timings=timings,
        CPU_s=time.process_time() - cpu, wall_s=time.perf_counter() - wall,
        actual_PHYS_N=len(inv['PHYS']['matched']), new_G4=0, energy_fits=0,
        model_forward=0, dataset_luminosity_pb_inv=None))


if __name__ == '__main__':
    main()
