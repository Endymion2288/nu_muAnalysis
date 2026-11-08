"""Fixed literal component/nominal pilot; a failed implementation does not retry."""
import time
from stage168_common import inputs, read_file, write


def main():
    cpu, wall = time.process_time(), time.perf_counter()
    records, timings = [], []
    for r in inputs()['pilot']:
        try:
            record, timing = read_file(r['path'])
        except Exception as error:
            write('pilot_failure.json', dict(path=r['path'], error=repr(error), completed_files=len(records), fixed_implementation_terminated=True))
            raise
        records.append(record); timings.append(timing)
        write('pilot_partial.json', dict(records=records, timings=timings, complete=False))
    write('pilot_summary.json', dict(passed=True, records=records, timings=timings,
        CPU_s=time.process_time()-cpu, wall_s=time.perf_counter()-wall,
        actual_unique_EVNT_N=len(inputs()['unique_paths']), energy_fits=0, model_forward=0, new_G4=0))


if __name__ == '__main__':
    main()
