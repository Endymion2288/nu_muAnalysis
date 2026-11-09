"""Reproducible plots of vertex acceptance and plane-to-vertex residuals."""
import argparse
import csv
import json
import tarfile
import time

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.patches import Circle, Rectangle
import numpy as np

from stage200_vertex import ROOT, OUT, CACHE, EDGES, box, masks, save

plt.rcParams.update({'font.size': 11, 'figure.dpi': 130, 'savefig.dpi': 180,
                     'axes.grid': False, 'svg.fonttype': 'none'})


def table(name, rows):
    with (OUT / name).open('w') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter='\t', lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def load(path):
    with np.load(path) as f:
        return {k: f[k] for k in f.files}


def collect():
    protocol = json.loads((OUT / 'protocol.json').read_text())
    for i in range(protocol['batches']):
        with tarfile.open(CACHE / f'batch_{i}.tar.gz') as archive:
            archive.extractall(ROOT, filter='data')
    batches = [load(CACHE / f'batch_{i}.npz') for i in range(protocol['batches'])]
    d = {k: (np.sum([b[k] for b in batches], axis=0) if k.startswith('raw_') else
             np.concatenate([b[k] for b in batches])) for k in batches[0]}
    np.savez_compressed(CACHE / 'vertices.npz', **d)
    files = sum([json.loads((OUT / f'batch_{i}.json').read_text())['files']
                 for i in range(protocol['batches'])], [])
    assert sorted(f['index'] for f in files) == sorted(s['index'] for s in protocol['sources'])
    # Exact old-event membership checks per input file, including both pz>100 cuts.
    old = load(ROOT / 'ntuples/energy_ml_stage126/predictions.npz')
    oldsel = (old['radius_mm'] < 100) & (old['reco_pz_GeV'] > 100) & (old['incoming'][:, 3] > 100000)
    oldwide = (old['reco_pz_GeV'] > 100) & (old['incoming'][:, 3] > 100000)
    for source in protocol['sources']:
        for truth, oldmask in [(100, oldsel), (np.inf, oldwide)]:
            actual = d['eventID'][(d['source'] == source['index']) & masks(d, truth=truth)]
            expected = old['eventID'][(old['source'] == source['index']) & oldmask]
            np.testing.assert_array_equal(np.sort(actual), np.sort(expected))
    assert sum(f['box_N'] for f in files) == d['raw_xy'].sum()
    save(OUT / 'validation.json', dict(passed=True, files=files, all_raw_N=sum(f['raw_N'] for f in files),
         all_box_N=sum(f['box_N'] for f in files), all_box_r100_N=sum(f['box_r100_N'] for f in files),
         standard_N=int(masks(d).sum()), no_truth_radius_N=int(masks(d, truth=np.inf).sum()),
         old_standard_and_unbounded_truth_event_sets_exact=True, candidate_N=len(d['x']),
         cache_bytes=(CACHE / 'vertices.npz').stat().st_size))
    return d


def figure(fig, name):
    for ext in ['png', 'pdf', 'svg']:
        fig.savefig(OUT / f'{name}.{ext}', bbox_inches='tight')
    plt.close(fig)


def geom(ax):
    ax.add_patch(Rectangle((-115, -171), 250, 300, fill=False, color='black', lw=1.5))
    ax.add_patch(Circle((0, 0), 100, fill=False, edgecolor='crimson', lw=1.5, ls='--'))
    ax.set(xlabel='Truth vertex x [mm]', ylabel='Truth vertex y [mm]',
           xlim=(-125, 145), ylim=(-181, 139), aspect='equal')


def density(ax, h, title, vmax=None):
    mesh = ax.pcolormesh(EDGES['x'], EDGES['y'], np.ma.masked_equal(h.T, 0),
                         norm=LogNorm(vmin=1, vmax=max(2, h.max()) if vmax is None else vmax), cmap='viridis')
    geom(ax)
    ax.set_title(title)
    return mesh


def hxy(d, m):
    return np.histogram2d(d['x'][m], d['y'][m], bins=[EDGES['x'], EDGES['y']])[0]


def policies():
    return [('Standard', {}), ('Max R < 110 mm', dict(rmax=110)),
            ('IFT R < 110 mm', dict(ift=110)), ('VetoNu R < 140 mm', dict(vetonu=140)),
            ('All: 110 / 110 / 140 mm', dict(rmax=110, ift=110, vetonu=140)),
            ('All: 120 / 120 / 150 mm', dict(rmax=120, ift=120, vetonu=150)),
            ('No max-R upper bound', dict(rmax=np.inf)), ('No IFT-R upper bound', dict(ift=np.inf)),
            ('No VetoNu-R upper bound', dict(vetonu=np.inf)),
            ('No three track-R upper bounds', dict(rmax=np.inf, ift=np.inf, vetonu=np.inf))]


def vertex_plots(d, v):
    inside = box(d['x'], d['y'], d['z'])
    fig, ax = plt.subplots(1, 3, figsize=(15, 5), constrained_layout=True)
    mesh = density(ax[0], d['raw_xy'], f'All MC in FASERnu box: N={v["all_box_N"]:,}')
    fig.colorbar(mesh, ax=ax[0], label='MC records / 5 x 5 mm bin', shrink=.8)
    for axis, uv in zip(ax[1:], [('z', 'x'), ('z', 'y')]):
        u, w = uv
        h = d['raw_' + u + w]
        mesh = axis.pcolormesh(EDGES[u], EDGES[w], np.ma.masked_equal(h.T, 0), norm=LogNorm(1, h.max()), cmap='viridis')
        axis.set(xlabel='Truth vertex z [mm]', ylabel=f'Truth vertex {w} [mm]', title='All MC; no analysis selection')
        axis.axhline(-100, color='crimson', ls='--'); axis.axhline(100, color='crimson', ls='--')
        axis.text(.03, .03, 'Dashed: projection of r < 100 mm cylinder', transform=axis.transAxes,
                  fontsize=8, bbox=dict(facecolor='white', alpha=.85, edgecolor='none'))
        fig.colorbar(mesh, ax=axis, label='MC records / bin', shrink=.8)
    fig.suptitle('Nominal MC truth vertices; red circle: truth r = 100 mm')
    figure(fig, 'all_mc_truth_vertex')

    rows = []
    comparisons = {}
    for truth in [100, np.inf]:
        base = masks(d, truth=truth) & inside
        for name, kw in policies():
            m = masks(d, truth=truth, **kw) & inside
            h = hxy(d, m)
            bh = hxy(d, base)
            p, q = h / h.sum(), bh / bh.sum()
            row = dict(truth_radius_mm='none' if np.isinf(truth) else truth, policy=name,
                       box_N=int(m.sum()), gain_N=int(m.sum()-base.sum()), gain_percent=100*(m.sum()/base.sum()-1),
                       union_box_lead_N=int(masks(d, truth=truth, **kw).sum()),
                       outer_r100_N=int((m & (d['r'] >= 100)).sum()),
                       outer_r100_percent=100*np.mean(d['r'][m] >= 100),
                       mean_x_mm=float(np.mean(d['x'][m])), mean_y_mm=float(np.mean(d['y'][m])),
                       mean_z_mm=float(np.mean(d['z'][m])), r_q95_mm=float(np.quantile(d['r'][m], .95)),
                       xy_total_variation=float(.5*np.abs(p-q).sum()))
            rows.append(row)
            comparisons[(truth, name)] = (m, h)
        names = [p[0] for p in policies()[:6]]
        fig, axes = plt.subplots(2, 3, figsize=(13, 10), constrained_layout=True)
        vmax = max(comparisons[(truth, n)][1].max() for n in names)
        for axis, name in zip(axes.flat, names):
            m, h = comparisons[(truth, name)]
            mesh = density(axis, h, name + f'\nN={m.sum():,} ({100*(m.sum()/base.sum()-1):+.2f}%)', vmax)
        fig.colorbar(mesh, ax=list(axes.flat), label='MC records / 5 x 5 mm bin', shrink=.75)
        tag = 'r100' if truth == 100 else 'no_truth_r'
        fig.suptitle('Standard analysis cuts; ' + ('truth r < 100 mm' if truth == 100 else 'truth radius upper bound removed'))
        figure(fig, 'vertex_cut_comparison_' + tag)
        # Added records expose small acceptance changes more clearly than total density.
        fig, axes = plt.subplots(1, 4, figsize=(16, 5), constrained_layout=True)
        for axis, name in zip(axes, names[1:5]):
            m, _ = comparisons[(truth, name)]
            h = hxy(d, m & ~base)
            mesh = density(axis, h, name + f'\nAdded N={(m & ~base).sum():,}')
            fig.colorbar(mesh, ax=axis, shrink=.75)
        fig.suptitle('Additional vertices relative to standard track-radius cuts; ' + tag)
        figure(fig, 'added_vertex_' + tag)
        fig, axes = plt.subplots(1, 4, figsize=(17, 4), constrained_layout=True)
        for axis, coord in zip(axes, 'xyzr'):
            h = d['raw_' + coord]
            axis.stairs(h/(h.sum()*np.diff(EDGES[coord])), EDGES[coord],
                        color='black', linestyle='--', label='All MC, no selection')
            for name in [names[0], *names[1:5], names[5]]:
                m, _ = comparisons[(truth, name)]
                axis.hist(d[coord][m], bins=EDGES[coord], histtype='step', density=True, label=name)
            axis.set(xlabel=f'Truth vertex {coord} [mm]', ylabel='Unit-normalized density [1/mm]')
        axes[0].legend(fontsize=7)
        fig.suptitle('Vertex shapes in FASERnu box; ' + tag)
        figure(fig, 'vertex_projections_' + tag)
    table('cut_comparison.tsv', rows)

    fig, axes = plt.subplots(1, 4, figsize=(16, 5), constrained_layout=True)
    choices = [(100, 'Standard'), (np.inf, 'Standard'),
               (np.inf, 'All: 110 / 110 / 140 mm'), (np.inf, 'No three track-R upper bounds')]
    ratios = [np.divide(comparisons[c][1], d['raw_xy'], out=np.full(d['raw_xy'].shape, np.nan),
                        where=d['raw_xy'] > 0) for c in choices]
    for axis, choice, ratio in zip(axes, choices, ratios):
        mesh = axis.pcolormesh(EDGES['x'], EDGES['y'], ratio.T, vmin=0,
                              vmax=max(np.nanmax(r) for r in ratios), cmap='viridis')
        geom(axis)
        axis.set_title(choice[1] + '\n' + ('truth r < 100 mm' if choice[0] == 100 else 'No truth r bound'), fontsize=10)
    fig.colorbar(mesh, ax=list(axes), label='Selected / all input MC in the same bin', shrink=.75)
    fig.suptitle('MC selection fraction across truth vertex x-y; unweighted input-record denominator')
    figure(fig, 'vertex_selection_fraction')

    scan = []
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), constrained_layout=True)
    for axis, key, start in zip(axes, ['rmax', 'ift', 'vetonu'], [95, 95, 120]):
        thresholds = sorted(set([start, 100, 105, 110, 120, 125, 130, 140, 150, 175, 200]))
        thresholds = [t for t in thresholds if t >= start] + [np.inf]
        for truth, color in [(100, 'C0'), (np.inf, 'C1')]:
            baseN = (masks(d, truth=truth) & inside).sum()
            gains = []
            for threshold in thresholds:
                m = masks(d, truth=truth, **{key: threshold}) & inside
                gain = 100*(m.sum()/baseN-1)
                gains.append(gain)
                scan.append(dict(cut=key, truth_r_mm='none' if np.isinf(truth) else truth,
                                 threshold_mm='none' if np.isinf(threshold) else threshold,
                                 N=int(m.sum()), gain_percent=gain))
            axis.plot([*thresholds[:-1], 220], gains, 'o-', color=color,
                      label='truth r<100 mm' if truth == 100 else 'No truth r bound')
        axis.set(xlabel=key + ' upper bound [mm]', ylabel='Gain in box records [%]', title='Relax only ' + key)
        axis.set_xticks([start, 150, 200, 220], [str(start), '150', '200', 'None'])
        axis.legend(fontsize=9); axis.grid(alpha=.2)
    figure(fig, 'radius_cut_scan')
    table('radius_scan.tsv', scan)
    return rows


def statistics(v):
    v = v[np.isfinite(v)]
    if len(v) == 0:
        return dict(N=0, mean=None, std=None, median=None, q16=None, q84=None, R68=None, RMSE=None, abs_q95=None)
    q = np.quantile(v, [.16, .5, .84])
    return dict(N=len(v), mean=float(v.mean()), std=float(v.std()), median=float(q[1]),
                q16=float(q[0]), q84=float(q[2]), R68=float((q[2]-q[0])/2),
                RMSE=float(np.sqrt(np.mean(v*v))), abs_q95=float(np.quantile(abs(v), .95)))


def residual_plots(d):
    nominal = masks(d)
    regions = [('box', nominal & box(d['x'], d['y'], d['z'])), ('box_or_lead', nominal)]
    residuals = {axis + '_' + label: v for axis in 'xy' for label, v in [
        ('VetoNu', d['vetonu_' + axis]-d[axis]), ('Veto1', d['veto1_' + axis]-d[axis]),
        ('average', (d['vetonu_' + axis]+d['veto1_' + axis])/2-d[axis])]}
    residuals['theta_primary'] = d['theta'] - d['truth_theta']
    residuals['theta_incoming_nu'] = d['theta'] - d['nu_theta']
    rows = []
    histrows = []
    for region, selection in regions:
        for k, vals in residuals.items():
            for group, m in [('all_selected', selection), ('primary_confirmed', selection & d['confirmed'])]:
                rows.append(dict(region=region, residual=k, group=group, unit='mrad' if k.startswith('theta') else 'mm',
                                 selected_N=int(m.sum()), invalid_N=int((~np.isfinite(vals[m])).sum()), **statistics(vals[m])))
        fig, axes = plt.subplots(2, 2, figsize=(12, 9), constrained_layout=True)
        for j, coord in enumerate('xy'):
            allvalues = np.concatenate([residuals[coord + '_' + k][selection] for k in ['VetoNu', 'Veto1', 'average']])
            limit = max(10, np.ceil(np.nanquantile(abs(allvalues), .995)/5)*5)
            for i, (left, right) in enumerate([(-limit, limit), (-250, 250)]):
                axis = axes[i, j]
                edges = np.linspace(left, right, 121)
                for k in ['VetoNu', 'Veto1', 'average']:
                    vals = residuals[coord + '_' + k][selection]
                    valid = vals[np.isfinite(vals)]
                    h, _ = np.histogram(valid, edges)
                    axis.stairs(h / (len(valid)*np.diff(edges)), edges, label=k)
                    for l, r, n in zip(edges[:-1], edges[1:], h):
                        histrows.append(dict(region=region, residual=coord+'_'+k, view='core' if i == 0 else 'wide',
                                             left=float(l), right=float(r), count=int(n), finite_N=len(valid),
                                             underflow_N=int((valid < left).sum()), overflow_N=int((valid > right).sum())))
                axis.axvline(0, color='gray', lw=1, ls='--')
                axis.set(xlabel=f'Track {coord} at plane - truth vertex {coord} [mm]', ylabel='Density / selected record [1/mm]')
                if i:
                    axis.set_yscale('log'); axis.set_ylim(bottom=1e-7)
                axis.legend(); axis.grid(alpha=.15)
        fig.suptitle(f'Standard cuts; {region}; N={selection.sum():,}\nAverage = (VetoNu + Veto1) / 2; full-sample normalization')
        figure(fig, 'position_residuals_' + region)

        vals = residuals['theta_primary']
        finite = vals[selection & np.isfinite(vals)]
        full_bounds = (min(-30, 10*np.floor(finite.min()/10)), max(30, 10*np.ceil(finite.max()/10)))
        fig, axes = plt.subplots(1, 3, figsize=(16, 4.5), constrained_layout=True)
        for view, axis, bounds in zip(['core', 'tails', 'full'], axes, [(-5, 5), (-30, 30), full_bounds]):
            for name, m in [('All selected, valid primary', selection),
                            ('Primary muon match confirmed', selection & d['confirmed'])]:
                valid = vals[m & np.isfinite(vals)]
                h, edges = np.histogram(valid, np.linspace(*bounds, 151))
                axis.stairs(h / (len(valid)*np.diff(edges)), edges, label=name)
                for l, r, n in zip(edges[:-1], edges[1:], h):
                    histrows.append(dict(region=region, residual='theta_primary_' + name, view=view,
                                         left=float(l), right=float(r), count=int(n), finite_N=len(valid),
                                         underflow_N=int((valid < bounds[0]).sum()),
                                         overflow_N=int((valid > bounds[1]).sum())))
            axis.axvline(0, color='gray', lw=1, ls='--')
            axis.set(xlabel=r'$\theta_{reco,leading} - \theta_{truth,primary\ \mu}$ [mrad]', ylabel='Density [1/mrad]')
            axis.legend(fontsize=9); axis.grid(alpha=.15)
            nout = int(((finite < bounds[0]) | (finite > bounds[1])).sum())
            axis.set_title(f'{view.capitalize()}; outside displayed range: {nout:,}')
        axes[1].set_yscale('log')
        axes[2].set_yscale('log')
        fig.suptitle(f'Standard cuts; {region}; primary direction at interaction vertex')
        figure(fig, 'theta_residual_' + region)

    # Depth dependence: direct station-plane proxies include physical displacement.
    selection = regions[0][1]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), constrained_layout=True)
    depthrows = []
    for axis, coord in zip(axes, 'xy'):
        for label in ['VetoNu', 'Veto1', 'average']:
            mids, medians, lows, highs = [], [], [], []
            for lo, hi in zip(np.linspace(-3000, -1950, 8)[:-1], np.linspace(-3000, -1950, 8)[1:]):
                m = selection & (d['z'] >= lo) & (d['z'] < hi)
                s = statistics(residuals[coord+'_'+label][m])
                depthrows.append(dict(axis=coord, proxy=label, z_min_mm=lo, z_max_mm=hi, **s))
                mids.append((lo+hi)/2); medians.append(s['median']); lows.append(s['q16']); highs.append(s['q84'])
            line, = axis.plot(mids, medians, 'o-', label=label)
            axis.fill_between(mids, lows, highs, color=line.get_color(), alpha=.12)
        axis.set(xlabel='Truth vertex z [mm]', ylabel=f'{coord} residual [mm]', title='Median and central 68% interval')
        axis.legend(); axis.axhline(0, color='gray', ls='--')
    figure(fig, 'position_residual_vs_depth')
    table('residual_statistics.tsv', rows)
    table('residual_histograms.tsv', histrows)
    table('residual_vs_depth.tsv', depthrows)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--collect', action='store_true')
    parser.add_argument('--residuals-only', action='store_true')
    args = parser.parse_args()
    start = time.perf_counter()
    d = collect() if args.collect else load(CACHE / 'vertices.npz')
    v = json.loads((OUT / 'validation.json').read_text())
    cuts = (json.loads((OUT / 'summary.json').read_text())['cut_comparison'] if args.residuals_only
            else vertex_plots(d, v))
    residuals = residual_plots(d)
    save(OUT / 'summary.json', dict(cut_comparison=cuts, residual_statistics=residuals,
         plot_wall_s=time.perf_counter()-start, plots=sorted(p.stem for p in OUT.glob('*.png'))))
    print('Plots complete:', time.perf_counter()-start)


if __name__ == '__main__':
    main()
