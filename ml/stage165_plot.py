"""Draw the predeclared component/source marginals from tabular results only."""
import csv

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from stage165_common import OUT

rows = list(csv.DictReader((OUT / 'paired.tsv').open(), delimiter='\t'))
groups = ['inclusive', 'component:pi', 'component:k', 'component:charm', 'flux_context:nominal', 'flux_context:alternative']
fig, axes = plt.subplots(2, 3, figsize=(13, 8), constrained_layout=True)
for ax, group in zip(axes.flat, groups):
    counts = {}
    for role, offset, colour, label in [(2, -.08, 'C0', 'cal'), (3, .08, 'C1', 'development test')]:
        for i, layer in enumerate(['E50_100', 'E100_200']):
            r = next(r for r in rows if r['candidate'] == 'AZH' and r['reference'] == 'AZ' and
                     int(r['role']) == role and r['group'] == group and r['stratum'] == layer)
            counts[role, i] = int(r['N'])
            if r['RMSE_ratio'] == 'NA':
                continue
            value = float(r['RMSE_ratio'])
            if r['high95'] != 'NA':
                ax.errorbar(i + offset, value,
                    yerr=[[max(0, value - float(r['low95']))], [max(0, float(r['high95']) - value)]],
                    fmt='o', color=colour, capsize=3, label=label if i == 0 else None)
            else:
                ax.scatter(i + offset, value, marker='x', color=colour, label=label if i == 0 else None)
    ax.axhline(1, color='gray', lw=1); ax.axhline(.95, color='gray', lw=.7, ls='--')
    ax.set_xticks([0, 1])
    ax.set_xticklabels([f'{label}\ncal N={counts[2, i]}; test N={counts[3, i]}'
                       for i, label in enumerate(['50–100 GeV', '100–200 GeV'])])
    ax.set_title(group)
    ax.set_ylabel('H given depth: paired log-RMSE ratio')
    ax.grid(axis='y', alpha=.2)
    if not any(counts.values()):
        ax.text(.5, .5, 'No events in the frozen cohort', ha='center', va='center', transform=ax.transAxes)
        ax.set_axis_off()
    elif any(n == 1 for n in counts.values()):
        ax.text(.5, .45, 'N=1: degenerate empirical interval\ndoes not measure population uncertainty',
                fontsize=8, ha='center', va='center', transform=ax.transAxes)
axes.flat[0].legend(fontsize=8)
fig.suptitle('Fixed predictions; marginal source diagnostics, conditional 95% intervals\nSparse groups and missing intervals retained; no deployment or production trigger', fontsize=11)
fig.savefig(OUT / 'source_marginals.png', dpi=150); fig.savefig(OUT / 'source_marginals.svg'); plt.close(fig)
p = OUT / 'source_marginals.svg'; p.write_text('\n'.join(line.rstrip() for line in p.read_text().splitlines()) + '\n')
