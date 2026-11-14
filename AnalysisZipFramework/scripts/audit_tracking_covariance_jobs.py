#!/usr/bin/env python3
"""Audit Condor termination records against the frozen covariance manifest."""
import argparse
import json
from pathlib import Path
import re


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--submission', type=Path, required=True)
    parser.add_argument('--cluster', type=int, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--require-complete', action='store_true')
    args = parser.parse_args()
    records = [row.split('\t') for row in (args.submission / 'manifest.tsv').read_text().splitlines()]
    exits = {}
    for block in (args.submission / 'events.log').read_text().split('\n...'):
        header = re.search(r'005 \((\d+)\.(\d+)\.\d+\)', block)
        if header and int(header[1]) == args.cluster:
            code = re.search(r'Normal termination \(return value (\d+)\)', block)
            exits[int(header[2])] = int(code[1]) if code else 'abnormal termination'
    missing = [i for i, row in enumerate(records) if not Path(row[5]).is_file()]
    result = dict(cluster=args.cluster, submission=str(args.submission), expected_jobs=len(records),
        terminated_jobs=len(exits), exit_zero_jobs=sum(code == 0 for code in exits.values()),
        failed={str(i): code for i, code in exits.items() if code != 0},
        pending_procs=[i for i in range(len(records)) if i not in exits],
        missing_output_procs=missing, output_files=len(records) - len(missing),
        output_bytes=sum(Path(row[5]).stat().st_size for i, row in enumerate(records) if i not in missing))
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    if args.require_complete:
        assert len(exits) == len(records) and not result['failed'] and not missing


if __name__ == '__main__':
    main()
