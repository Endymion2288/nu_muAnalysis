#!/usr/bin/env python3
"""Summarize measured per-event worker timings, substituting the pre-submission pilot."""

import argparse
from pathlib import Path
import re

import numpy as np

from report_tracking_comparison import save_table


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--cluster', type=int, required=True)
    parser.add_argument('--pilot', type=Path, required=True)
    parser.add_argument('--override', action='append', default=[], help='proc=alternate-stdout-path')
    args = parser.parse_args(); repo = args.repo.resolve()
    overrides = {int(item.split('=',1)[0]): Path(item.split('=',1)[1]) for item in args.override}
    records = [line.split('\t') for line in (repo/'AnalysisZipFramework/submission/tracking_loss_manifest.tsv').read_text().splitlines()]
    pattern = re.compile(r'^(\w+) wall_seconds=([\d.]+) max_rss_kib=(\d+) user_seconds=([\d.]+) system_seconds=([\d.]+)$', re.M)
    rows = []
    for i, record in enumerate(records):
        path = args.pilot if i == 0 else overrides.get(i, repo/f'logs/tracking_loss_{args.cluster}.{i}.out')
        values = pattern.findall(path.read_text())
        assert len(values) == 7, (i, path)
        rows += [dict(proc=i, run=int(record[0]), eventID=int(record[1]), stage=stage,
                      wall_seconds=float(wall), max_rss_kib=int(rss), user_seconds=float(user),
                      system_seconds=float(system), source='pilot' if i == 0 else 'condor')
                 for stage, wall, rss, user, system in values]
    output = repo/'workbook/stage17_tracking_loss'
    save_table(output/'resources_by_event.tsv', list(rows[0]), rows)
    summary = []
    for stage in ['locate', 'input', 'reco', 'forward', 'backward', 'merge', 'extract']:
        selected = [row for row in rows if row['stage'] == stage]
        wall = np.array([row['wall_seconds'] for row in selected])
        summary.append(dict(stage=stage, events=len(selected), wall_min_s=wall.min(),
                            wall_median_s=np.median(wall), wall_max_s=wall.max(), wall_sum_s=wall.sum(),
                            max_rss_kib=max(row['max_rss_kib'] for row in selected),
                            cpu_sum_s=sum(row['user_seconds']+row['system_seconds'] for row in selected)))
    save_table(output/'resources_summary.tsv', list(summary[0]), summary)


if __name__ == '__main__':
    main()
