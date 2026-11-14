#!/usr/bin/env python3
"""Plot measured paired losses and covariance-control efficiencies."""
import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def read(path):
    with path.open() as stream:
        return list(csv.DictReader(stream, delimiter='\t'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output
    modes = ['forward', 'backward', 'merge']
    rows = read(out / 'loss_classification.tsv')
    categories = ['primary_raw_only', 'no_primary_raw', 'both_correct_primary_leaders',
                  'primary_leader_changed_or_low_purity', 'wrong_or_low_purity_old_leader']
    labels = ['Primary survives only as short track', 'No primary raw track',
              'Both leaders correct; later cut differs', 'Leader changes or purity falls',
              'Old leader incorrect or low purity']
    fig, ax = plt.subplots(figsize=(10, 5.5), layout='constrained')
    bottom = np.zeros(3)
    for category, label in zip(categories, labels):
        values = [sum(int(r['events']) for r in rows if r['population'] == 'accepted'
                      and r['migration'] == 'lost' and r['mode'] == mode
                      and r['category'] == category) for mode in modes]
        ax.bar(modes, values, bottom=bottom, label=label)
        bottom += values
    for i, value in enumerate(bottom):
        ax.text(i, value + 45, str(int(value)), ha='center')
    ax.set(ylabel='Events passing old final cuts but failing latest',
           title='Paired losses in 140,132 truth-accepted events', ylim=(0, 4800))
    ax.legend(fontsize=8, loc='upper right')
    fig.savefig(out / 'paired_loss_causes.png', dpi=160)
    plt.close(fig)

    rows = read(out / 'controls/control_metrics.tsv')
    controls = ['default', 'oldqop', 'oldtheta', 'oldseed', 'tightphi', 'shared']
    selected = [r for r in rows if r['index'] in ['0', '63'] and r['skip'] == '0'
                and r['job'].startswith('controls/')]
    if len({r['job'] for r in selected}) != 12:
        return
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), layout='constrained')
    for mode, color in zip(modes, ['tab:blue', 'tab:orange', 'tab:green']):
        baseline = [r for r in selected if r['control'] == 'default'
                    and r['version'] == 'old' and r['mode'] == mode]
        denom = sum(int(r['accepted']) for r in baseline)
        old = 100 * sum(int(r['final_correct']) for r in baseline) / denom
        for ax, field in zip(axes, ['primary_long', 'final_correct']):
            points = []
            for control in controls:
                data = [r for r in selected if r['version'] == 'control'
                        and r['control'] == control and r['mode'] == mode]
                points.append(100 * sum(int(r[field]) for r in data) / denom)
            ax.plot(controls, points, 'o-', color=color, label=mode)
            if field == 'final_correct':
                ax.axhline(old, color=color, linestyle=':', alpha=.5)
            ax.tick_params(axis='x', rotation=30)
            ax.set(ylabel='Efficiency in truth-accepted events (%)',
                   title='At least one primary long track' if field == 'primary_long'
                   else 'Correct primary passing final cuts')
            ax.grid(alpha=.2)
    axes[0].legend()
    axes[1].text(.02, .02, 'Dotted: old reconstruction; controls are diagnostic only',
                 transform=axes[1].transAxes, fontsize=8)
    fig.savefig(out / 'covariance_controls.png', dpi=160)


if __name__ == '__main__':
    main()
