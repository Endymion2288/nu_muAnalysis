"""Use the actual C++ time-range class and an independent scalar prefix read."""
import csv
import json
import tarfile
from pathlib import Path

import ROOT as R
import uproot
from stage166_common import ROOT, OUT, CACHE, plan, grl, load_prefix, snapshot, write, table


def main():
    p, g = plan(), grl()
    with tarfile.open(CACHE / 'official_grl_inputs.tar.gz') as archive:
        assert len(archive.getnames()) == 6
        for member in archive:
            assert archive.extractfile(member).read() == Path('/' + member.name).read_bytes()
    assert R.gInterpreter.Declare('#include "' + str(ROOT / 'AnalysisZipFramework/include/GRLUtils.h') + '"')
    stable, excluded = R.GRLUtils.TimeRanges(), R.GRLUtils.TimeRanges()
    original = json.loads(Path(g['JSON']['path']).read_text())['15838']
    for key, target in [('stable_list', stable), ('excluded_list', excluded)]:
        for r in original.get(key, []): target.add(15838, int(r['start_utime']), int(r['stop_utime']))
    rows = list(csv.DictReader((OUT / 'time_support.tsv').open(), delimiter='\t'))
    summary = json.loads((OUT / 'full_summary.json').read_text())
    totals = {}; records = []
    for row in rows:
        stamp, n = int(row['eventTime']), int(row['N'])
        a, b = bool(stable.contains(15838, stamp)), bool(excluded.contains(15838, stamp))
        for name, value in [('stable_N', a), ('excluded_N', b), ('accepted_time_N', a and not b)]:
            assert int(row[name]) == n * value
        for k, v in row.items():
            if k != 'eventTime': totals[k] = totals.get(k, 0) + int(v)
    assert totals == summary['DQ_counts'] and totals['N'] == 780874
    for name, ranges, target in [('stable', g['stable_ranges_s'], stable), ('excluded', g['excluded_ranges_s'], excluded)]:
        for lo, hi in ranges:
            for stamp in sorted({lo - 1, lo, lo + 1, hi - 1, hi, hi + 1}):
                python = any(a <= stamp <= b for a, b in ranges)
                compiled = bool(target.contains(15838, stamp))
                assert compiled == python
                records.append(dict(kind=name, timestamp_s=stamp, Cpp=compiled, independent_python=python))
    assert not stable.contains(0, int(rows[0]['eventTime']))
    prefix = load_prefix(); branches = list(prefix[0])
    with uproot.open(p['inputs']['PHYS'], array_cache=None) as source:
        # Read each branch independently, instead of the pilot's two-block batch.
        a = {b: source['nt'][b].array(entry_stop=1024, library='np') for b in branches}
        reread = snapshot(a); assert reread == prefix
        read_bytes = int(source.file.source.num_requested_bytes)
    scalar = dict(stable_N=0, excluded_N=0, accepted_time_N=0)
    for r in prefix:
        good = bool(stable.contains(r['run'], r['eventTime']))
        bad = bool(excluded.contains(r['run'], r['eventTime']))
        scalar['stable_N'] += good; scalar['excluded_N'] += bad; scalar['accepted_time_N'] += good and not bad
        if 'distanceToCollidingBCID' in r:
            scalar['colliding_N'] = scalar.get('colliding_N', 0) + (r['distanceToCollidingBCID'] == 0)
        if 'inputBits' in r:
            scalar['trigger_N'] = scalar.get('trigger_N', 0) + any(r['inputBits'] & mask for mask in [8, 16, 32, 64])
        if 'distanceToCollidingBCID' in r and 'inputBits' in r:
            colliding = r['distanceToCollidingBCID'] == 0
            trigger = any(r['inputBits'] & mask for mask in [8, 16, 32, 64])
            for k, v in [('colliding_trigger', colliding and trigger),
                         ('colliding_trigger_stable', colliding and trigger and good),
                         ('colliding_trigger_accepted', colliding and trigger and good and not bad)]:
                scalar[k + '_N'] = scalar.get(k + '_N', 0) + bool(v)
    pilot = {r['flag'] + '_N': int(r['N']) for r in csv.DictReader((OUT / 'pilot_time_support.tsv').open(), delimiter='\t')}
    assert scalar == pilot
    # Independent interval subtraction by a midpoint sweep, not full.py's splitting.
    st = g['stable_ranges_s']; ex = g['excluded_ranges_s']
    knots = sorted({v for pair in st + ex for v in pair})
    independent_run = sum(b - a for a, b in zip(knots[:-1], knots[1:])
        if any(lo <= (a + b) / 2 <= hi for lo, hi in st) and not any(lo <= (a + b) / 2 <= hi for lo, hi in ex))
    assert independent_run == summary['official_accepted_run_time_s']
    lo, hi = summary['time_min_s'], summary['time_max_s']; knots = sorted(set(knots + [lo, hi]))
    independent_overlap = sum(b - a for a, b in zip(knots[:-1], knots[1:])
        if lo <= (a + b) / 2 <= hi and any(x <= (a + b) / 2 <= y for x, y in st)
        and not any(x <= (a + b) / 2 <= y for x, y in ex))
    assert independent_overlap == summary['bounding_span_overlap_accepted_time_s']
    table('boundary_validation.tsv', records)
    result = dict(passed=True, original_official_bytes_exact=True, Cpp_repository_TimeRanges=True,
        occupied_seconds_checked=len(rows), endpoint_checks=len(records), absent_run_checked=True,
        independent_prefix_N=1024, prefix_scalar_DQ=scalar, full_aggregate_N=totals['N'],
        independent_interval_lengths_exact=True, independent_ROOT_read_bytes=read_bytes,
        shard_exposure_still_unmeasured=True, no_luminosity_fraction_extrapolation=True,
        energy_fits=0, model_forward=0, promotion=False, overall_complete=False)
    write('independent_validation.json', result); print(result)


if __name__ == '__main__':
    main()
