"""Summarize saved stage89 outputs; no posterior integration or model execution."""
import json

import numpy as np

from accurate_posterior import CACHE, OUT, REPO
from report_accurate_posterior import read
from support_augmentation import arrays, begin, resources, save, table


def main():
    start = begin()
    summaries = []
    selected = []
    combined = {}
    for role, expected in [('cal', 11612), ('test', 13189)]:
        d = arrays(CACHE / f'input_{role}.npz')
        v = arrays(CACHE / f'predictions_{role}.npz')
        np.testing.assert_array_equal(d['row'], v['row'])
        assert len(d['row']) == expected
        check = json.loads((OUT / role / 'independent_validation.json').read_text())
        assert check['passed'] and check['identity_N'] == expected
        diagnostics = read(OUT / role / 'numerical_checks.tsv')
        assert len(diagnostics) == expected
        np.testing.assert_array_equal([int(r['row']) for r in diagnostics], d['row'])
        q32 = np.column_stack([d['posterior_nominal_' + k] for k in ['q05', 'q16', 'median', 'q84', 'q95']])
        qdiff = np.max(abs(q32 - v['accurate_quantiles']), axis=1)
        pdiff = abs(d['posterior_nominal_pit'] - v['accurate_PIT'])
        ldiff = abs(d['posterior_nominal_logscore'] - v['accurate_logscore'])
        cost = json.loads((OUT / role / 'inference_resources.json').read_text())
        summary = dict(role=role, N=expected, certified_N=int(v['numerical_certified'].sum()),
                       missing_N=int(d['input_missing'].sum()),
                       missing_certified_N=int(v['numerical_certified'][d['input_missing']].sum()),
                       exception_N=sum(bool(r['error']) for r in diagnostics),
                       precision_flag_sum=sum(int(r['quad_precision_flags']) for r in diagnostics),
                       GH32_PIT_error_gt_0p0001_N=int((pdiff > 1e-4).sum()),
                       GH32_quantile_logE_error_gt_0p001_N=int((qdiff > 1e-3).sum()),
                       GH32_logdensity_error_gt_0p001_N=int((ldiff > 1e-3).sum()),
                       max_GH32_PIT_error=float(pdiff.max()), max_GH32_quantile_logE_error=float(qdiff.max()),
                       max_GH32_logdensity_error=float(ldiff.max()),
                       CDF_calls=sum(int(r['CDF_calls']) for r in diagnostics),
                       integrand_evaluations=sum(int(r['integrand_evaluations']) for r in diagnostics),
                       inference_CPU_s=cost['CPU_s'], inference_wall_s=cost['wall_s'],
                       inference_events_per_CPU_s=expected / cost['CPU_s'])
        for field in ['quad_error', 'tail_bound', 'root_residual']:
            summary['max_' + field] = max(float(r[field]) for r in diagnostics)
        summary['max_endpoint_error'] = max(max(abs(float(r['global_CDF_lower'])), abs(float(r['global_CDF_upper']) - 1)) for r in diagnostics)
        summary['min_CDF_increment'] = min(float(r['minimum_CDF_increment']) for r in diagnostics)
        summaries.append(summary)
        m = read(OUT / role / 'metrics.tsv')
        combined[role] = m
        for r in m:
            if r['weighting'] == 'incoming' and r['stratum'] in ['all', 'E50_100', 'E100_200', 'pz50_100', 'pz50_100_trueE200', 'high_y', 'unconfirmed', 'E3200_6400', 'input_missing', 'fit_failure']:
                selected.append(r)
    table(OUT / 'numerical_summary.tsv', summaries)
    table(OUT / 'selected_metrics.tsv', selected)
    cal = read(OUT / 'cal/scores.tsv')
    nll = next(float(r['training_prior_logE_NLL']) for r in cal if r['stratum'] == 'all' and r['method'] == 'GH32')
    old = json.loads((REPO / 'workbook/stage87_energy_ml/posterior_calibration.json').read_text())
    # The optimizer's stored full-cal objective is an independent prior-removal check.
    assert abs(nll - old['cal_logE_NLL']) < 1e-8, (nll, old)
    save(OUT / 'closeout_validation.json', dict(passed=True, complete_rows=24801,
        certified_rows=sum(r['certified_N'] for r in summaries),
        GH32_fullcal_training_NLL=nll, stage87_calibration_NLL=old['cal_logE_NLL'],
        calibration_NLL_difference=abs(nll - old['cal_logE_NLL']),
        new_integrals=0, new_fits=0, independent_confirmation=False))
    plot(combined['test'])
    save(OUT / 'closeout_resources.json', resources(start))


def plot(rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    colors = ['#777777', '#0072b2', '#d55e00', '#009e73']
    policies = ['traditional', 'direct_cal', 'posterior_GH32', 'posterior_accurate']
    labels = ['Traditional', 'Direct', 'Posterior GH32', 'Posterior accurate']
    fig, axes = plt.subplots(1, 3, figsize=(12, 4), layout='constrained')
    for ax, layers, ticklabels in [
        (axes[0], ['E50_100', 'E100_200', 'all'], ['50–100', '100–200', 'All']),
        (axes[1], ['pz50_100_trueE200', 'high_y', 'unconfirmed'], ['Low pz, high E', 'High y', 'Unconfirmed'])]:
        x = np.arange(len(layers))
        for j, (name, label, color) in enumerate(zip(policies, labels, colors)):
            y = [float(next(r['log_RMSE'] for r in rows if r['stratum'] == s and r['policy'] == name and r['weighting'] == 'incoming')) for s in layers]
            ax.plot(x + (j - 1.5) * .07, y, 'o', color=color, label=label, markersize=5)
        ax.set_xticks(x, ticklabels, rotation=12)
        ax.set_ylabel('log(E) RMSE')
        ax.set_ylim(bottom=0)
        ax.grid(axis='y', alpha=.25)
    axes[0].set_title('Truth energy [GeV]')
    axes[0].legend(fontsize=8)
    axes[1].set_title('Difficult sides retained')
    coverage = read(OUT / 'test/coverage.tsv')
    layers = ['E50_100', 'E100_200', 'E200_400', 'E400_800', 'E800_1600', 'E1600_3200', 'E3200_6400']
    x = np.arange(len(layers))
    ax = axes[2]
    for method, color in [('GH32', colors[2]), ('accurate', colors[3])]:
        for level, style in [('68', '-o'), ('90', '--s')]:
            y = [float(next(r['coverage_pct'] for r in coverage if r['stratum'] == s and r['method'] == method and r['level'] == level)) for s in layers]
            ax.plot(x, y, style, color=color, markersize=3, label=f'{method} {level}%')
    for level in [68, 90]:
        ax.axhline(level, color='grey', lw=.6, alpha=.6)
    ax.set_xticks(x, ['50', '100', '200', '400', '800', '1600', '3200'], rotation=45)
    ax.set_xlabel('Lower edge of truth-energy bin [GeV]')
    ax.set_ylabel('Coverage [%]')
    ax.set_ylim(0, 102)
    ax.legend(fontsize=7)
    ax.set_title('Central posterior intervals')
    fig.suptitle('Stage89: fixed model, calibration and nominal prior; incoming weighted\nPreviously studied test pool; conditional diagnostics, no model promotion', fontsize=10)
    svg = OUT / 'accurate_posterior.svg'
    fig.savefig(svg)
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines()) + '\n')
    fig.savefig('/tmp/stage89_accurate_posterior.png', dpi=140)
    plt.close(fig)


if __name__ == '__main__':
    main()
