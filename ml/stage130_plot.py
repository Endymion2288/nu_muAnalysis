"""Standalone fixed-policy quantity and augmentation comparison plots."""
import csv

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from stage130_prepare import OUT


def main():
    fig, axes = plt.subplots(2, 2, figsize=(11, 8), sharey=True)
    layers = ['E50_100', 'E100_200', 'all', 'pz50_100_trueE200', 'high_y', 'highE']
    for j, side in enumerate(['old', 'new']):
        with (OUT / f'{side}_paired.tsv').open() as stream:
            rows = list(csv.DictReader(stream, delimiter='\t'))
        for i, role in enumerate([2, 3]):
            ax = axes[i, j]
            for offset, candidate, reference, label in [(-.18, 'N2', 'N0', '2N / N (same composition)'),
                    (0, 'augmented', 'direct_cal', 'All training / original direct62'),
                    (.18, 'augmented', 'traditional', 'All training / traditional')]:
                chosen = [next((r for r in rows if int(r['role']) == role and r['stratum'] == layer and
                          r['candidate'] == candidate and r['reference'] == reference), None) for layer in layers]
                for k, row in enumerate(chosen):
                    if row is None:
                        continue
                    point, low, high = [float(row[key]) for key in ['RMSE_ratio', 'low95', 'high95']]
                    # A percentile interval need not include its central point.
                    ax.vlines(k+offset, low, high, linewidth=1.5, color=f'C{int(round((offset+.18)/.18))}')
                    ax.plot(k+offset, point, 'o', markersize=4,
                            color=f'C{int(round((offset+.18)/.18))}', label=label if k == 0 else None)
            ax.axhline(1, color='black', linewidth=.8)
            ax.set_xticks(range(len(layers)), ['50–100', '100–200', 'All', 'Low pz,\nhigh E', 'High y', 'E ≥ 1000'])
            ax.set_title(f'{side.capitalize()} development pool, '+('calibration' if role == 2 else 'test'))
            ax.set_ylabel('Paired log-RMSE ratio (conditional 95% interval)')
            ax.grid(axis='y', alpha=.25)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower center', ncol=3, fontsize=8)
    fig.suptitle('Stage130: fixed model policies; incoming/component conditional uncertainty')
    fig.tight_layout(rect=(0, .055, 1, .96))
    for extension in ['svg', 'png']:
        fig.savefig(OUT / f'energy_comparisons.{extension}', dpi=160)
    path = OUT / 'energy_comparisons.svg'
    path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')


if __name__ == '__main__':
    main()
