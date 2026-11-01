#!/usr/bin/env python3
"""Read back retained native observables before removing large temporary HITS shards."""
import json
import time
from pathlib import Path

import numpy as np


def main():
    repo = Path(__file__).resolve().parents[1]
    out = repo/'workbook/stage37_energy_ml'
    destination = out/'archive.json'
    if destination.exists():
        print(destination.read_text())
        return
    tick = time.perf_counter()
    cache = repo/'ntuples/energy_ml_stage37'
    with np.load(cache/'native_response.npz') as z:
        final = {key: z[key] for key in z.files}
    lineage = json.loads(str(final['lineage_json']))
    cfg = json.loads((repo/'ml/configs/calonu_native_control.json').read_text())
    start = 0
    retained = ['adc', 'saved_wave', 'saved_time', 'integral', 'raw_integral', 'status', 'baseline_mean',
                'baseline_rms', 'localtime', 'peak', 'width', 'mean', 'alpha', 'nval']
    removed = []
    shards = [cache/f'shards/{group}.npz' for group in cfg['groups']]
    for path in shards:
        with np.load(path) as z:
            cases = json.loads(str(z['cases_json']))
            n = len(cases)
            assert cases == lineage[start:start+n]
            for key in retained:
                np.testing.assert_array_equal(z[key], final[key][start:start+n])
            assert np.all(z['saved_samples'] == 76)
            start += n
    assert start == len(lineage) == 128
    for path in shards+[repo/'software/energy-ml-calonu-native-stage37.tar.gz']:
        if path.exists():
            removed.append(dict(path=str(path.relative_to(repo)), bytes=path.stat().st_size))
    # All retained native fields and lineage passed before any deletion.
    for row in removed:
        (repo/row['path']).unlink()
    value = dict(retained_path=str((cache/'native_response.npz').relative_to(repo)),
                 retained_bytes=(cache/'native_response.npz').stat().st_size,
                 events=128, retained_native_fields_checked=retained, full_lineage_equal=True,
                 all_field_readback_equal=True, removed=removed, removed_bytes=sum(r['bytes'] for r in removed),
                 original_ROOT_files_modified=False, wall_s=time.perf_counter()-tick)
    destination.write_text(json.dumps(value, indent=2)+'\n')
    print(json.dumps(value))


if __name__ == '__main__':
    main()
