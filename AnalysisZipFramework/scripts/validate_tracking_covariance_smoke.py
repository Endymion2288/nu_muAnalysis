#!/usr/bin/env python3
"""Validate pure production-runtime replays against the previous covariance controls."""
import argparse
import json
from pathlib import Path
import time

import numpy as np
from report_tracking_station import EVENT_KEYS, TRACK_KEYS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); start = time.monotonic(); rows = {}
    references = dict(large='000_0_735_default_a1.npz', small='003_0_735_oldseed_a1.npz')
    for variant, filename in references.items():
        actual = args.repo / f'ntuples/tracking_covariance_stage210/smoke/{variant}_000_00735.npz'
        previous = args.repo / 'ntuples/tracking_causes_stage209/loss_targets' / filename
        with np.load(actual) as a, np.load(previous) as b:
            checks = {k: bool(np.array_equal(a[k], b[k], equal_nan=a[k].dtype.kind in 'fc'))
                      for k in EVENT_KEYS + TRACK_KEYS + ['all_run', 'all_eventID']}
            assert all(checks.values()), (variant, checks)
            config = json.loads(str(a['effective_reco_json']))
            assert config['variance'] == variant and config['exact_strict_map']
            assert len(config['algorithms']) == 4 and all(x['isolated_smoothing'] for x in config['algorithms'].values())
            rows[variant] = dict(science_arrays_exact=True, checks=checks,
                input_events=int(a['counts'][0, 0]), fiducial=len(a['run']),
                final_FBM=a['counts'][:, -1].tolist(), configuration=config,
                performance=json.loads(str(a['performance_json'])))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = dict(variants=rows, production_runtime_only=True, wall_s=time.monotonic()-start)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({v: {k: r[k] for k in ['science_arrays_exact', 'input_events', 'fiducial', 'final_FBM']}
                      for v, r in rows.items()}))


if __name__ == '__main__':
    main()
