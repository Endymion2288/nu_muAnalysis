"""Frozen source-standardized estimands, paired incoming bootstrap and summaries."""
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from audited_features import FIT_INVALID, WAVE_INVALID

OUT = Path(__file__).resolve().parents[1]/'workbook/stage112_energy_ml'


def clean(x):
    if isinstance(x, (np.floating, float)) and not np.isfinite(x):
        return None
    return x.item() if isinstance(x, np.generic) else x


def table(name, rows):
    if not rows:
        return
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with (OUT/name).open('w') as f:
        w = csv.DictWriter(f, fields, delimiter='\t', lineterminator='\n')
        w.writeheader()
        for row in rows:
            w.writerow({k: 'NA' if clean(v) is None else clean(v) for k, v in row.items()})


def avg(x, w):
    return float(np.average(x, weights=w)) if len(x) and w.sum() > 0 else np.nan


def quantile(x, w, q):
    if not len(x) or w.sum() <= 0:
        return np.full(len(q), np.nan)
    order = np.argsort(x, kind='stable')
    x, w = x[order], w[order]
    return np.interp(q, (np.cumsum(w)-.5*w)/w.sum(), x)


def strata(d):
    e, p, y = d['E'], d['pz'], d['y']
    z = {'all': np.ones(len(e), bool), 'E50_100': (e >= 50) & (e < 100),
         'E100_200': (e >= 100) & (e < 200), 'E200_inf': e >= 200,
         'pz50_100': (p > 50) & (p < 100),
         'pz50_100_trueE200': (p > 50) & (p < 100) & (e >= 200),
         'high_y': d['primary_valid'] & np.isfinite(y) & (y >= .8),
         'unconfirmed': ~d['confirmed'], 'primary_unknown': ~d['primary_valid'],
         'confirmed_low_transfer': d['confirmed'] & np.isfinite(y) & (y < .2),
         'pz0_50': (p > 0) & (p <= 50), 'pz50_100_closed': (p > 50) & (p <= 100),
         'pz100_200': (p > 100) & (p <= 200), 'pz200_inf': p > 200}
    for lo, hi in zip([200, 400, 800, 1600, 3200], [400, 800, 1600, 3200, np.inf]):
        z[f'E{lo}_{hi if np.isfinite(hi) else "inf"}'] = (e >= lo) & (e < hi)
    return z


def report(data, sources, source_audits):
    # Draw once over global keys, including cross-source duplicates.
    sizes = [len(d['E']) for d in data]
    incoming = np.concatenate([d['incoming'] for d in data])
    _, inverse = np.unique(incoming, axis=0, return_inverse=True)
    nkeys = inverse.max()+1
    draws = np.random.default_rng(2026110512).poisson(1, size=(500, nkeys)).astype('uint8')
    offset = 0
    for d, n in zip(data, sizes):
        d['key_id'] = inverse[offset:offset+n]
        offset += n
    risk, support, decomposition, cutrows, validity, variables, charge = [], [], [], [], [], [], []
    event_closure = aggregate_closure = 0.
    for d, source, audit in zip(data, sources, source_audits):
        sid = source['source']
        for row in audit['cuts']:
            cutrows.append(dict(source=sid, parent_N=len(d['E']), **row))
        populations = dict(PHYS=np.ones(len(d['E']), bool), G0=d['G0'], Gplus=d['Gplus'], S50=d['S50'], S100=d['S100'])
        for name, pop in populations.items():
            for key in ['no_track', 'primary_valid', 'confirmed'] + [k for k in d if k.startswith('invalid_')]:
                validity.append(dict(source=sid, population=name, state=key, denominator=int(pop.sum()), N=int((pop & d[key]).sum())))
            validity.append(dict(source=sid, population=name, state='truth_y_outside_0_1', denominator=int(pop.sum()),
                                 N=int((pop & np.isfinite(d['y']) & ((d['y'] < 0) | (d['y'] > 1))).sum())))
            support.append(dict(source=sid, population=name, parent_N=int(pop.sum()),
                                eligible_N=int((pop & d['eligible']).sum()),
                                excluded_test_N=int((pop & (d['known_priority'] == 3)).sum()),
                                excluded_known_quarantine_N=int((pop & (d['known_row_role'] == 0)).sum()),
                                defined_error_N=int((pop & d['eligible'] & np.isfinite(d['error'])).sum())))
            for s in ['Veto20', 'Veto21', 'Timing0', 'Timing1', 'Timing2', 'Timing3', 'Preshower0', 'Preshower1', 'VetoNu0', 'VetoNu1', 'Veto10']:
                status = d[s+'_status'].astype('int64')
                fit, raw = d[s+'_charge'], d[s+'_raw_charge']
                # Original audited flags: low status bits are read literally;
                # no signed raw value is classified invalid just for its sign.
                fit_invalid = (status & FIT_INVALID) != 0
                charge.append(dict(source=sid, population=name, detector=s, denominator=int(pop.sum()),
                                   nonfinite_fit=int((pop & ~np.isfinite(fit)).sum()),
                                   nonfinite_raw=int((pop & ~np.isfinite(raw)).sum()),
                                   status_fit_invalid=int((pop & fit_invalid).sum()),
                                   status_wave_invalid=int((pop & ((status & WAVE_INVALID) != 0)).sum()),
                                   status_values=','.join(map(str, np.unique(status[pop]))),
                                   raw_negative_finite=int((pop & np.isfinite(raw) & (raw < 0)).sum()),
                                   fit_mean=avg(fit[pop & np.isfinite(fit)], np.ones((pop & np.isfinite(fit)).sum())),
                                   raw_mean=avg(raw[pop & np.isfinite(raw)], np.ones((pop & np.isfinite(raw)).sum())),
                                   note='no cut substitution; original audited FIT_INVALID/WAVE_INVALID masks'))
            if name == 'PHYS':
                continue
            for layer, mask in strata(d).items():
                use = pop & mask & d['eligible']
                valid = use & np.isfinite(d['error'])
                w = d['weight'][valid]
                err = d['error'][valid]
                rel = np.expm1(err)
                qs = quantile(rel, w, [.16, .5, .84])
                risk.append(dict(source=sid, component=source['component'], population=name, stratum=layer,
                                 N=int(use.sum()), defined_N=int(valid.sum()), undefined_error_N=int((use & ~valid).sum()),
                                 incoming=len(np.unique(d['key_id'][use])), weight_sum=float(w.sum()),
                                 ESS=float(w.sum()**2/(w@w)) if len(w) else 0.,
                                 log_MSE=avg(err**2, w), log_RMSE=np.sqrt(avg(err**2, w)),
                                 median_bias_pct=100*qs[1], mean_bias_pct=100*avg(rel, w),
                                 R68_pct=50*(qs[2]-qs[0]), tail50_pct=100*avg(abs(rel) > .5, w),
                                 positive_tail50_pct=100*avg(rel > .5, w), negative_tail50_pct=100*avg(rel < -.5, w)))
                dp = valid & d['primary_valid'] & np.isfinite(d['r']) & np.isfinite(d['u'])
                ww = d['weight'][dp]
                r, u, e = [d[k][dp] for k in ['r', 'u', 'error']]
                c = np.log(.8)
                terms = [r*r, u*u, np.full(len(r), c*c), 2*r*u, -2*c*r, -2*c*u]
                identity = float(np.max(abs(e-r-u+c))) if len(e) else 0.
                closure = float(abs(avg(e*e, ww)-sum(avg(t, ww) for t in terms))) if len(e) else 0.
                event_closure = max(event_closure, identity)
                aggregate_closure = max(aggregate_closure, closure)
                values = dict(zip(['r2', 'u2', 'c2', 'two_ru', 'minus_two_cr', 'minus_two_cu'], [avg(t, ww) for t in terms]))
                decomposition.append(dict(source=sid, population=name, stratum=layer, primary_N=int(dp.sum()),
                                          excluded_from_decomposition_N=int((valid & ~dp).sum()),
                                          MSE=avg(e*e, ww), **values, identity_max_abs=identity, aggregate_closure_abs=closure))
                for key in ['y', 'r', 'u', 'vertex_z', 'vertex_r', 'pz']:
                    vv = use & np.isfinite(d[key])
                    weights = d['weight'][vv]
                    q = quantile(d[key][vv], weights, [.16, .5, .84])
                    variables.append(dict(source=sid, population=name, stratum=layer, variable=key,
                                          finite_N=int(vv.sum()), undefined_N=int((use & ~vv).sum()),
                                          mean=avg(d[key][vv], weights), q16=q[0], median=q[1], q84=q[2],
                                          fraction_y_lt_0p2=avg(d[key][vv] < .2, weights) if key == 'y' else np.nan,
                                          units='mm' if key.startswith('vertex') else 'GeV' if key == 'pz' else 'dimensionless'))
    # Equal source mixture is a diagnostic distribution, not a flux estimate.
    for population in ['G0', 'Gplus', 'S50', 'S100']:
        for layer in strata(data[0]):
            cells = [r for r in risk if r['population'] == population and r['stratum'] == layer]
            estimable = len(cells) == 6 and all(r['weight_sum'] > 0 for r in cells)
            row = dict(source='equal_six', component='fixed source mixture', population=population, stratum=layer,
                       N=sum(r['N'] for r in cells), defined_N=sum(r['defined_N'] for r in cells),
                       undefined_error_N=sum(r['undefined_error_N'] for r in cells), estimable=estimable)
            for metric in ['log_MSE', 'mean_bias_pct', 'tail50_pct', 'positive_tail50_pct', 'negative_tail50_pct']:
                row[metric] = np.mean([r[metric] for r in cells]) if estimable else np.nan
            row['log_RMSE'] = np.sqrt(row['log_MSE'])
            if estimable:
                rels, weights = [], []
                for d in data:
                    use = d[population] & d['eligible'] & strata(d)[layer] & np.isfinite(d['error'])
                    ww = d['weight'][use]
                    weights.append(ww/(6*ww.sum()))
                    rels.append(np.expm1(d['error'][use]))
                qs = quantile(np.concatenate(rels), np.concatenate(weights), [.16, .5, .84])
                row.update(median_bias_pct=100*qs[1], R68_pct=50*(qs[2]-qs[0]))
            else:
                row.update(median_bias_pct=np.nan, R68_pct=np.nan)
            risk.append(row)
    table('cutflow.tsv', cutrows)
    table('support.tsv', support)
    table('risk.tsv', risk)
    table('decomposition.tsv', decomposition)
    table('validity.tsv', validity)
    table('variables.tsv', variables)
    table('scintillator_audit.tsv', charge)
    assert event_closure <= 1e-12 and aggregate_closure <= 1e-10
    # Primary estimator and the independent implementation use record dot
    # products and incoming-aggregated sufficient statistics respectively.
    endpoint_rows, source_rows = [], []
    max_bootstrap_difference = 0.
    primary = {}
    for name in ['E50_100', 'E100_200']:
        points, samples = [], []
        missing = []
        for d, source in zip(data, sources):
            layer = strata(d)[name]
            arm_values, arm_draws = [], []
            counts = {}
            for pop in ['Gplus', 'S50']:
                use = d[pop] & d['Gplus'] & d['eligible'] & layer
                w, x, keys = d['weight'][use], d['error'][use]**2, d['key_id'][use]
                counts[pop+'_N'] = int(use.sum())
                point = avg(x, w)
                b = draws[:, keys].astype(float)*w
                den = b.sum(1)
                boot = np.divide(b@x, den, out=np.full(500, np.nan), where=den > 0)
                numerator = np.bincount(keys, weights=w*x, minlength=nkeys)
                denominator = np.bincount(keys, weights=w, minlength=nkeys)
                # Restrict the check to the union of keys, not a 500*N dense
                # floating array for every cell.
                unique = np.unique(keys)
                bd = draws[:, unique]@denominator[unique]
                independent = np.divide(draws[:, unique]@numerator[unique], bd, out=np.full(500, np.nan), where=bd > 0)
                assert np.array_equal(np.isfinite(boot), np.isfinite(independent))
                ok = np.isfinite(boot)
                if ok.any():
                    max_bootstrap_difference = max(max_bootstrap_difference, float(np.max(abs(boot[ok]-independent[ok]))))
                arm_values.append(point)
                arm_draws.append(boot)
            delta = arm_values[1]-arm_values[0]
            bs = arm_draws[1]-arm_draws[0]
            good = np.isfinite(bs)
            bounds = np.percentile(bs[good], [2.5, 97.5]) if good.sum() >= 475 else [np.nan, np.nan]
            source_rows.append(dict(source=source['source'], stratum=name, **counts,
                                    Gplus_MSE=arm_values[0], S50_MSE=arm_values[1], delta_MSE=delta,
                                    low95=bounds[0], high95=bounds[1], valid_draws=int(good.sum())))
            if not np.isfinite(delta):
                missing.append(source['source'])
            points.append(delta)
            samples.append(bs)
        point = float(np.mean(points))
        bs = np.mean(samples, axis=0)
        good = np.isfinite(bs)
        bounds = np.percentile(bs[good], [2.5, 97.5]) if good.sum() >= 475 else [np.nan, np.nan]
        row = dict(stratum=name, delta_MSE=point, low95=bounds[0], high95=bounds[1],
                   valid_draws=int(good.sum()), sources=6, missing_sources=','.join(missing) or 'none',
                   estimable=not missing, unit='squared natural-log error',
                   scope='six fixed sources; incoming conditional, no source/refit/system/research-selection coverage')
        endpoint_rows.append(row)
        primary[name] = {k: clean(v) for k, v in row.items()}
    table('primary.tsv', endpoint_rows)
    table('source_primary.tsv', source_rows)
    assert max_bootstrap_difference <= 1e-10
    validation = dict(passed=True, source_count=6, bootstrap_draws=500, seed=2026110512,
                      max_event_identity_error=event_closure, max_aggregate_closure_error=aggregate_closure,
                      independent_key_aggregation_bootstrap_max_abs=max_bootstrap_difference,
                      complete_native_mask_differences=sum(q['native_mask_differences'] for q in source_audits),
                      no_source_renormalization_or_replacement=True,
                      no_cut_or_model_change=True)
    (OUT/'measurement_validation.json').write_text(json.dumps(validation, indent=2)+'\n')
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout='constrained')
    for ax, layer in zip(axes, ['E50_100', 'E100_200']):
        for pop, marker in [('Gplus', 'o'), ('S50', 's')]:
            values = [next(r['log_RMSE'] for r in risk if r['source'] == s['source'] and r['stratum'] == layer and r['population'] == pop) for s in sources]
            ax.plot(range(6), values, marker+'-', label=pop)
        ax.set(xticks=range(6), xticklabels=[s['source'] for s in sources], title=layer,
               xlabel='fixed PHYS source', ylabel='traditional log-energy RMSE')
        ax.legend()
    fig.savefig(OUT/'selection_risk.svg')
    plt.close(fig)
    return dict(primary=primary, validation=validation,
                conditional_only=True, new_model_benefit='not measured', source_or_full_acceptance='not measured')
