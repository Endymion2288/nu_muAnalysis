#!/usr/bin/env python3
"""Study merge failures conditional on backward passing, using the paired event cache."""

import argparse
import json
from pathlib import Path
import resource
import time

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import minimize
from scipy.special import expit
from scipy.stats import fisher_exact, norm

from compare_tracking import selection
from report_tracking_comparison import figure_save, save_table


def interval(n, d):
    n, d = np.asarray(n), np.asarray(d)
    p = np.divide(n, d, out=np.full(np.broadcast(n, d).shape, np.nan), where=d != 0)
    d = np.where(d > 0, d, np.nan)
    z = 1.959963984540054
    center = (p + z*z/(2*d))/(1+z*z/d)
    half = z*np.sqrt(p*(1-p)/d+z*z/(4*d*d))/(1+z*z/d)
    return p, center-half, center+half


def logistic(pz, radius, z, run, outcome, scope):
    """Unpenalized conditional logistic model; report observed-information Wald CIs."""
    runs = np.unique(run)
    terms = ['intercept', 'truth_radius_per_20mm', 'truth_z_per_500mm',
             'truth_pz_per_doubling', 'lead_block'] + [f'run_{r}_vs_{runs[0]}' for r in runs[1:]]
    x = np.column_stack([np.ones(len(z)), (radius-60)/20, (z+2400)/500,
                         np.log2(pz/700), (z > -1900).astype(float)] +
                        [(run == r).astype(float) for r in runs[1:]])
    y = outcome.astype(float)

    def value(beta):
        eta = x @ beta
        return np.sum(np.logaddexp(0, eta)-y*eta), x.T @ (expit(eta)-y)

    initial = np.zeros(x.shape[1]); initial[0] = np.log(y.mean()/(1-y.mean()))
    fit = minimize(value, initial, jac=True, method='BFGS', options={'gtol': 1e-6, 'maxiter': 200})
    prob = expit(x @ fit.x)
    information = x.T @ (x*(prob*(1-prob))[:, None])
    se = np.sqrt(np.diag(np.linalg.inv(information)))
    gradient = float(np.max(np.abs(value(fit.x)[1])))
    assert gradient < 1e-4, (fit.message, gradient)
    return [dict(scope=scope, term=term, events=len(y), losses=int(y.sum()), beta=b,
                 standard_error=s, odds_ratio=np.exp(b), ci95_low=np.exp(b-1.959964*s),
                 ci95_high=np.exp(b+1.959964*s), wald_p=2*norm.sf(abs(b/s)),
                 maximum_absolute_gradient=gradient) for term, b, s in zip(terms, fit.x, se)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--cache', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    repo = args.repo.resolve()
    output = args.output or repo/'workbook/stage17_tracking_loss'
    output.mkdir(parents=True, exist_ok=True)
    tick, cpu = time.monotonic(), time.process_time()
    with np.load(args.cache or repo/'workbook/stage10_tracking_z/fiducial_events.npz') as source:
        data = {k: source[k] for k in source.files}
    bits = data['event_cut_bits']; full = (1 << 14)-1
    selected = bits[:, 1] == full
    loss = selected & (bits[:, 2] != full)
    gain = (bits[:, 2] == full) & ~selected
    assert (len(bits), int(selected.sum()), int(loss.sum()), int(gain.sum())) == (383670, 103985, 89, 1034)
    cuts, _ = selection(repo); names = [name for name, _ in cuts][6:]
    assert len(names) == 14
    first = np.array([int(b).bit_length() for b in bits[:, 2]])
    assert np.all(bits[:, 2] == (1 << first)-1)
    pz = data['event_truth_pz_nu']; z = data['event_truth_dec_z_nu']
    x, y = data['event_truth_dec_x_nu'], data['event_truth_dec_y_nu']
    radius = np.hypot(x, y); run = data['event_run']
    failure_rows = [dict(cut_index=j, first_failed_cut=name, events=int(np.sum(loss & (first == j))))
                    for j, name in enumerate(names)]
    save_table(output/'first_failures.tsv', list(failure_rows[0]), failure_rows)
    events = []
    for i in np.flatnonzero(loss):
        file_row = np.searchsorted(data['file_offsets'][1:], i, side='right')
        events.append(dict(run=int(run[i]), eventID=int(data['event_eventID'][i]),
                           manifest_index=int(data['manifest_indices'][file_row]),
                           truth_pz_GeV=pz[i], truth_x_mm=x[i], truth_y_mm=y[i], truth_r_mm=radius[i],
                           truth_z_mm=z[i], forward_bits=int(bits[i, 0]), backward_bits=int(bits[i, 1]),
                           merge_bits=int(bits[i, 2]), first_failed_cut=names[first[i]]))
    save_table(output/'loss_events.tsv', list(events[0]), events)
    # Include every cumulative stage, because a "tracking loss" need not mean a final loss.
    stage_rows = []
    for j, name in enumerate(names):
        b, m = [((bits[:, k] >> j) & 1).astype(bool) for k in (1, 2)]
        stage_rows.append(dict(stage=name, backward_pass=int(b.sum()), merge_pass=int(m.sum()),
                               backward_only=int((b & ~m).sum()), merge_only=int((m & ~b).sum())))
    save_table(output/'stage_losses.tsv', list(stage_rows[0]), stage_rows)
    bins = [('truth_pz_GeV', pz, np.array([100, 200, 300, 500, 1000, 2000, 5000, np.inf]),
             'Truth neutrino $p_z$ (GeV)'),
            ('truth_radius_mm', radius, np.arange(0, 101, 20), 'Truth vertex radius (mm)'),
            ('truth_z_mm', z, np.array([-3000, -2800, -2600, -2400, -2200, -2000, -1950,
                                      -1769.65, -1719.65, -1669.65, -1619.65]),
             'Truth interaction z (mm)')]
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False,
                         'svg.fonttype': 'none'})
    fig, axes = plt.subplots(2, 3, figsize=(16, 9))
    bin_rows = []
    for col, (label, variable, edges, xlabel) in enumerate(bins):
        den = np.histogram(variable[selected], edges)[0]
        num = np.histogram(variable[loss], edges)[0]
        assert den.sum() == selected.sum() and num.sum() == loss.sum()
        rate, low, high = interval(num, den)
        display_edges = edges.copy()
        if not np.isfinite(display_edges[-1]):
            display_edges[-1] = 10000
        centers = (display_edges[1:]+display_edges[:-1])/2
        if col == 0:
            centers = np.sqrt(display_edges[1:]*display_edges[:-1])
        for k in range(len(den)):
            bin_rows.append(dict(variable=label, low=edges[k], high=edges[k+1],
                                 backward_pass=int(den[k]), merge_fail=int(num[k]),
                                 loss_percent=100*rate[k], ci95_low_percent=100*low[k],
                                 ci95_high_percent=100*high[k]))
        ax = axes[0, col]
        # Show bin fractions, including the pz overflow bin, rather than unequal-width densities.
        ax.stairs(den/den.sum(), display_edges, label='All backward pass', color='#0072B2', lw=2)
        ax.stairs(num/num.sum(), display_edges, label='Backward pass, merge fail', color='#D55E00', lw=2)
        ax.set_ylabel('Fraction of each population per bin'); ax.set_xlabel(xlabel)
        axes[1, col].errorbar(centers, 100*rate, yerr=100*np.vstack([rate-low, high-rate]),
                             fmt='o', color='#D55E00', capsize=3)
        axes[1, col].axhline(100*loss.sum()/selected.sum(), color='grey', ls='--', label='Overall loss rate')
        axes[1, col].set_ylabel('Merge fail / backward pass (%)'); axes[1, col].set_xlabel(xlabel)
        for center, n, d in zip(centers, num, den):
            if d:
                axes[1, col].annotate(f'{n}/{d:,}', (center, 0), xytext=(0, 5),
                                      textcoords='offset points', rotation=90, fontsize=7)
        if col == 0:
            ax.set_xscale('log'); axes[1, col].set_xscale('log')
        if col == 2:
            for axis in axes[:, col]:
                axis.axvspan(-1950, -1769.65, color='#dddddd')
                axis.tick_params(axis='x', labelrotation=25)
        for axis in axes[:, col]:
            axis.grid(alpha=.2)
    axes[0, 0].legend(fontsize=9); axes[1, 0].legend(fontsize=8)
    fig.suptitle('89 merge losses / 103,985 backward-selected events · 342 paired RDOs\n'
                 'Unweighted MC mixture; conditional loss rates with 95% Wilson intervals; pz last bin includes overflow')
    fig.tight_layout(); figure_save(fig, output, 'population_and_loss_rates')
    save_table(output/'kinematic_bins.tsv', list(bin_rows[0]), bin_rows)

    group_rows = []
    groups = [('all', np.ones(len(z), dtype=bool)), ('nominal_without_200080', run != 200080)]
    groups += [(f'run_{r}', run == r) for r in np.unique(run)]
    groups += [('radius_lt80mm', radius < 80), ('radius_ge80mm', radius >= 80),
               ('box', z < -1950), ('lead', z > -1900),
               ('z_lt_minus2400mm', z < -2400), ('z_ge_minus2400mm', z >= -2400),
               ('pz_lt500GeV', pz < 500), ('pz_ge500GeV', pz >= 500)]
    for name, mask in groups:
        n, d = int(np.sum(loss & mask)), int(np.sum(selected & mask))
        rate, low, high = interval(n, d)
        group_rows.append(dict(group=name, losses=n, backward_pass=d, rate_percent=100*rate,
                               ci95_low_percent=100*low, ci95_high_percent=100*high))
    save_table(output/'groups.tsv', list(group_rows[0]), group_rows)
    contrasts = []
    for name, mask in [('radius_ge80mm', radius >= 80), ('z_ge_minus2400mm', z >= -2400),
                        ('pz_ge500GeV', pz >= 500)]:
        n1, d1 = int((loss & mask).sum()), int((selected & mask).sum())
        n0, d0 = int((loss & ~mask).sum()), int((selected & ~mask).sum())
        odds, p = fisher_exact([[n1, d1-n1], [n0, d0-n0]])
        contrasts.append(dict(contrast=name, loss1=n1, total1=d1, loss0=n0, total0=d0,
                              rate_ratio=(n1/d1)/(n0/d0), odds_ratio=odds, fisher_two_sided_p=p,
                              bonferroni_p=min(1., 3*p)))
    save_table(output/'exploratory_contrasts.tsv', list(contrasts[0]), contrasts)
    models = []
    for name, mask in groups[:2]:
        s = selected & mask
        models += logistic(pz[s], radius[s], z[s], run[s], loss[s], name)
    save_table(output/'adjusted_logistic.tsv', list(models[0]), models)

    fig = plt.figure(figsize=(14, 11), constrained_layout=True)
    grid = fig.add_gridspec(2, 2)
    axes = [fig.add_subplot(grid[0, 0]), fig.add_subplot(grid[1, :]), fig.add_subplot(grid[0, 1])]
    axes[0].hexbin(x[selected], y[selected], gridsize=28, mincnt=1, cmap='Blues', bins='log')
    axes[0].scatter(x[loss], y[loss], s=17, facecolors='none', edgecolors='#D55E00', label='89 merge losses')
    axes[0].add_patch(plt.Circle((0, 0), 80, fill=False, ls='--', color='grey'))
    axes[0].set(xlabel='Truth vertex x (mm)', ylabel='Truth vertex y (mm)', aspect='equal')
    axes[0].legend(fontsize=8)
    ze = bins[2][2]; re = np.array([0, 40, 60, 80, 100.])
    den = np.histogram2d(z[selected], radius[selected], (ze, re))[0]
    num = np.histogram2d(z[loss], radius[loss], (ze, re))[0]
    ratio = np.divide(num, den, out=np.full_like(num, np.nan), where=den != 0)
    mesh = axes[1].pcolormesh(ze, re, 100*ratio.T, cmap='magma', shading='flat')
    for j in range(len(ze)-1):
        for k in range(len(re)-1):
            if den[j, k]:
                axes[1].text((ze[j]+ze[j+1])/2, (re[k]+re[k+1])/2,
                             f'{int(num[j,k])}\n/{int(den[j,k])}', ha='center', va='center', fontsize=6,
                             color='white' if ratio[j,k] < np.nanmax(ratio)/2 else 'black')
    axes[1].set(xlabel='Truth interaction z (mm)', ylabel='Truth radius (mm)')
    axes[1].tick_params(axis='x', labelrotation=30)
    fig.colorbar(mesh, ax=axes[1], label='Merge loss / backward pass (%)')
    failures = [r for r in failure_rows if r['events']]
    axes[2].barh([r['first_failed_cut'] for r in failures], [r['events'] for r in failures], color='#D55E00')
    axes[2].invert_yaxis(); axes[2].set_xlabel('Number of final backward-only events')
    fig.suptitle('Conditional losses: spatial pattern and first failed cut in the original order')
    figure_save(fig, output, 'spatial_and_failures')
    joint = [dict(z_low=ze[j], z_high=ze[j+1], r_low=re[k], r_high=re[k+1],
                  losses=int(num[j,k]), backward_pass=int(den[j,k]), loss_percent=100*ratio[j,k])
             for j in range(len(ze)-1) for k in range(len(re)-1)]
    save_table(output/'joint_z_radius.tsv', list(joint[0]), joint)
    summary = dict(truth_events=len(z), backward_pass=int(selected.sum()), losses=int(loss.sum()),
                   gains=int(gain.sum()), merge_pass=int((bits[:,2] == full).sum()),
                   loss_rate_percent=100*loss.sum()/selected.sum(),
                   wall_seconds=time.monotonic()-tick, cpu_seconds=time.process_time()-cpu,
                   peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                   quantiles={key: {scope: np.quantile(variable[mask], [.25,.5,.75]).tolist()
                                    for scope, mask in [('backward', selected), ('loss', loss)]}
                              for key, variable, _, _ in bins})
    (output/'population_summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
