#!/usr/bin/env python3
"""Locate actual PHYS input entries with a unique multi-observable fingerprint."""
import argparse
import json
import time
from pathlib import Path

import awkward as ak
import numpy as np
import uproot


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--request', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--smoke', action='store_true')
    a = p.parse_args()
    row = json.loads(a.request.read_text())
    tick = time.perf_counter()
    keys = ['run', 'eventID', 'Track_p0', 'Track_pz0', 'Track_X_atVetoNu', 'Track_Y_atVetoNu', 'CaloNu0_raw_charge']
    with uproot.open(row['input_phys']) as f:
        tree = f['nt']
        values = tree.arrays(keys, entry_stop=256 if a.smoke else None)
        row['phys_entries'] = tree.num_entries
    idx = ak.argmax(values['Track_pz0'], axis=1, keepdims=True)
    d = {key: ak.to_numpy(ak.fill_none(ak.firsts(values[key][idx]), np.nan)).astype(np.float32)
         if key.startswith('Track_') else ak.to_numpy(values[key]) for key in keys}
    assert row['phys_entries'] == 50000
    if a.smoke:
        row['cases'] = row['cases'][:1]
    for case in row['cases']:
        mask = np.ones(len(d['run']), bool)
        for key, value in case['fingerprint'].items():
            mask &= d[key] == value
        entry = np.flatnonzero(mask)
        assert len(entry) == 1, (case, entry)
        case['input_entry'] = int(entry[0])
        assert d['run'][entry[0]] == row['run']
        case['hits_subfile_ordinal'] = case['input_entry']//10000
        case['hits_entry'] = case['input_entry'] % 10000
    row['locate_wall_s'] = time.perf_counter()-tick
    a.output.write_text(json.dumps(row, indent=2)+'\n')
    print(json.dumps(dict(index=row['index'], located=len(row['cases']), wall_s=row['locate_wall_s'])))


if __name__ == '__main__':
    main()
