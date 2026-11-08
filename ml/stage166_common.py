"""Frozen real-data GRL support, without luminosity extrapolation."""
import csv
import gzip
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'workbook/stage166_energy_ml'
CACHE = ROOT / 'ntuples/energy_ml_stage166'
REQUIRED = ['run', 'eventID', 'eventTime']
OPTIONAL = ['distanceToCollidingBCID', 'inputBits']


def plan():
    return json.loads((OUT / 'protocol.json').read_text())


def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def table(name, rows):
    columns = list(dict.fromkeys(k for r in rows for k in r))
    with (OUT / name).open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, delimiter='\t', lineterminator='\n')
        writer.writeheader()
        writer.writerows({k: 'NA' if v is None else v for k, v in r.items()} for r in rows)


def snapshot(arrays):
    for name in REQUIRED:
        a = arrays[name]
        assert np.issubdtype(a.dtype, np.integer), (name, str(a.dtype))
    return [{name: int(arrays[name][i]) for name in arrays} for i in range(len(arrays['run']))]


def save_prefix(rows):
    with gzip.open(CACHE / 'prefix1024.json.gz', 'wt') as stream:
        json.dump(rows, stream, separators=(',', ':'))


def load_prefix():
    with gzip.open(CACHE / 'prefix1024.json.gz', 'rt') as stream:
        return json.load(stream)


def time_mask(times, ranges):
    result = np.zeros(len(times), bool)
    for lo, hi in ranges:
        result |= (times >= lo) & (times <= hi)
    return result


def flags(arrays, grl):
    assert np.all(arrays['run'] == 15838)
    good = time_mask(arrays['eventTime'], grl['stable_ranges_s'])
    excluded = time_mask(arrays['eventTime'], grl['excluded_ranges_s'])
    result = dict(stable=good, excluded=excluded, accepted_time=good & ~excluded)
    if 'distanceToCollidingBCID' in arrays:
        result['colliding'] = arrays['distanceToCollidingBCID'] == 0
    if 'inputBits' in arrays:
        assert np.issubdtype(arrays['inputBits'].dtype, np.integer)
        result['trigger'] = (arrays['inputBits'] & 0x78) != 0
    if 'colliding' in result and 'trigger' in result:
        result['colliding_trigger'] = result['colliding'] & result['trigger']
        result['colliding_trigger_stable'] = result['colliding_trigger'] & good
        result['colliding_trigger_accepted'] = result['colliding_trigger'] & good & ~excluded
    return result


def grl():
    return json.loads((OUT / 'grl_input.json').read_text())
