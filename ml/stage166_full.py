"""One admitted header-only PHYS scan, retaining compact time support."""
import concurrent.futures
import json
import resource
import time
from collections import defaultdict

import numpy as np
import uproot
from stage166_common import OUT, plan, grl, flags, snapshot, load_prefix, write, table


def union(ranges):
    result = []
    for lo, hi in sorted(ranges):
        if result and lo <= result[-1][1]:
            result[-1][1] = max(hi, result[-1][1])
        else:
            result.append([lo, hi])
    return result


def duration(ranges, excluded):
    parts = union(ranges)
    for a, b in union(excluded):
        out = []
        for lo, hi in parts:
            if hi <= a or lo >= b:
                out.append([lo, hi])
            else:
                if lo < a: out.append([lo, a])
                if hi > b: out.append([b, hi])
        parts = out
    return sum(hi - lo for lo, hi in parts)


def main():
    assert json.loads((OUT / 'admission.json').read_text())['admitted']
    cpu, tick = time.process_time(), time.perf_counter(); p = plan(); g = grl()
    branches = json.loads((OUT / 'pilot_summary.json').read_text())['branches']
    bins = defaultdict(lambda: defaultdict(int)); cursor = 0
    with concurrent.futures.ThreadPoolExecutor(4) as workers:
        with uproot.open(p['inputs']['PHYS'], array_cache=None, decompression_executor=workers,
                         interpretation_executor=workers, num_workers=4) as source:
            tree = source['nt']; assert tree.num_entries == 780874
            for a in tree.iterate(branches, step_size=65536, library='np'):
                if cursor == 0:
                    assert snapshot({k: v[:1024] for k, v in a.items()}) == load_prefix()
                f = flags(a, g); times, inverse = np.unique(a['eventTime'], return_inverse=True)
                counts = np.bincount(inverse)
                counted = {k: np.bincount(inverse, weights=v.astype(int), minlength=len(times)).astype(int) for k, v in f.items()}
                for j, stamp in enumerate(times):
                    b = bins[int(stamp)]; b['N'] += int(counts[j])
                    for k, values in counted.items(): b[k + '_N'] += int(values[j])
                cursor += len(a['run'])
            requested = int(source.file.source.num_requested_bytes)
    assert cursor == 780874
    rows = [dict(eventTime=t, **dict(v)) for t, v in sorted(bins.items())]
    table('time_support.tsv', rows)
    totals = {k: sum(r[k] for r in rows) for k in rows[0] if k != 'eventTime'}
    lo, hi = rows[0]['eventTime'], rows[-1]['eventTime']
    clipped = [[max(a, lo), min(b, hi)] for a, b in g['stable_ranges_s'] if max(a, lo) <= min(b, hi)]
    support_s = duration(clipped, g['excluded_ranges_s'])
    run_s = duration(g['stable_ranges_s'], g['excluded_ranges_s'])
    result = dict(passed=True, source_N=cursor, original1024_prefix_exact=True, run=15838,
        time_min_s=lo, time_max_s=hi, bounding_time_span_s=hi - lo,
        occupied_integer_seconds=len(rows), unoccupied_integer_seconds_within_bounds=hi - lo + 1 - len(rows),
        official_accepted_run_time_s=run_s, bounding_span_overlap_accepted_time_s=support_s,
        official_run_recorded_lumi_pb_inv=g['CSV']['recorded_lumi_pb_inv'],
        dataset_luminosity_pb_inv=None, dataset_exposure_certified=False,
        full_run_processing_coverage_certified=False,
        interpretation='Bounding and occupied time support are not luminosity or livetime; no fraction-based extrapolation',
        DQ_counts=totals, DQ_scope='descriptive within original PHYS; not trigger efficiencies or full nu selection',
        read_bytes=requested, CPU_s=time.process_time() - cpu, wall_s=time.perf_counter() - tick,
        RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        new_G4=0, energy_fits=0, model_forward=0, promotion=False, overall_complete=False)
    write('full_summary.json', result); print(result)


if __name__ == '__main__':
    main()
