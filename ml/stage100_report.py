"""Paired A versus frozen B; no optimizer, threshold tuning or test access."""
import numpy as np
from stage100_common import OUT, REPO, CACHE, bootstrap, interval, read, roc, save, table, threshold


def report(cases, train_cases, cal_labels, train_labels, predictions, train_predictions):
    draws = bootstrap(cases)
    den = draws.sum(1)
    losses, curves, metrics, operating, thresholds = {}, {}, [], [], []
    rocs = {}
    flags = {}
    for name in ['A', 'B']:
        q = np.clip(predictions[name], 1e-12, 1-1e-12)
        logscore = -(cal_labels*np.log(q)+(1-cal_labels)*np.log1p(-q))
        brier = (q-cal_labels)**2
        losses[name] = [logscore, brier]
        fp, tp, auc, pauc = roc(q, cal_labels, np.ones(len(q)))
        rocs[name] = (fp, tp)
        curves[name] = np.array([roc(q, cal_labels, w)[2:] for w in draws])
        row = dict(model=name, N=len(q), L_N=int((cal_labels == 0).sum()), H_N=int((cal_labels == 1).sum()))
        for metric, value in [('logscore', logscore), ('Brier', brier)]:
            bounds = interval(draws@value/den)
            row.update({metric: float(value.mean()), metric+'_low95': bounds[0], metric+'_high95': bounds[1]})
        for j, metric, value in [(0, 'AUC', auc), (1, 'pAUC_0_10', pauc)]:
            bounds = interval(curves[name][:, j])
            row.update({metric: value, metric+'_low95': bounds[0], metric+'_high95': bounds[1]})
        metrics.append(row)
        for alpha in [.02, .05, .1]:
            t = threshold(train_predictions[name], train_labels, alpha)
            flag = q > t
            flags[name, alpha] = flag
            train_fpr = float(np.mean(train_predictions[name][train_labels == 0] > t))
            thresholds.append(dict(model=name, nominal_FPR=alpha, threshold=t, strict_greater=True, train_FPR=train_fpr, fit_role='train_only'))
            row = dict(model=name, nominal_FPR=alpha, train_threshold=t, train_FPR=train_fpr, certified=False)
            for cls, label in [(0, 'L_FPR'), (1, 'H_TPR')]:
                z = cal_labels == cls
                classdraw = draws[:, z]
                de = classdraw.sum(1)
                values = classdraw@flag[z].astype(float)/de
                bounds = interval(values)
                row.update({label: float(flag[z].mean()), label+'_low95': bounds[0], label+'_high95': bounds[1],
                            label+'_N': int(z.sum()), label+'_recognized': int(flag[z].sum()),
                            label+'_incoming': len({c['key_id'] for c, include in zip(cases, z) if include}),
                            label+'_sources': len({c['source'] for c, include in zip(cases, z) if include})})
            operating.append(row)
    paired = []
    for j, metric in enumerate(['logscore', 'Brier']):
        value = losses['B'][j]-losses['A'][j]
        bounds = interval(draws@value/den)
        paired.append(dict(metric=metric, B_minus_A=float(value.mean()), low95=bounds[0], high95=bounds[1], lower_is_better=True, draws=500))
    for j, metric in enumerate(['AUC', 'pAUC_0_10']):
        bounds = interval(curves['B'][:, j]-curves['A'][:, j])
        paired.append(dict(metric=metric, B_minus_A=metrics[1][metric]-metrics[0][metric], low95=bounds[0], high95=bounds[1], lower_is_better=False, draws=500))
    paired_work = []
    for alpha in [.02, .05, .1]:
        delta = flags['B', alpha].astype(float)-flags['A', alpha].astype(float)
        row = dict(nominal_FPR=alpha, comparison='B_minus_A', thresholds_fixed_on_train=True)
        for cls, label in [(0, 'L_FPR'), (1, 'H_TPR')]:
            z = cal_labels == cls
            values = draws[:, z]@delta[z]/draws[:, z].sum(1)
            bounds = interval(values)
            row.update({label+'_delta_pp': float(100*delta[z].mean()), label+'_low95_pp': 100*bounds[0], label+'_high95_pp': 100*bounds[1]})
        paired_work.append(row)
    # Reproduce every old B metric and low-FPR value without changing B.
    checks = []
    previous = read(REPO/'workbook/stage99_energy_ml/B_classifier_metrics.tsv')[0]
    for key in ['logscore', 'logscore_low95', 'logscore_high95', 'Brier', 'Brier_low95', 'Brier_high95', 'AUC', 'pAUC_0_10']:
        error = abs(metrics[1][key]-float(previous[key]))
        assert error < 1e-12
        checks.append(dict(check='stage99_B_metric', field=key, abs_difference=error))
    previous = read(REPO/'workbook/stage99_energy_ml/B_classifier_ROC_working.tsv')
    for old, new in zip(previous, [r for r in operating if r['model'] == 'B']):
        assert float(old['nominal_FPR']) == new['nominal_FPR']
        for key in ['train_threshold', 'train_FPR', 'L_FPR', 'L_FPR_low95', 'L_FPR_high95', 'L_FPR_N', 'L_FPR_recognized', 'H_TPR', 'H_TPR_low95', 'H_TPR_high95', 'H_TPR_N', 'H_TPR_recognized']:
            error = abs(new[key]-float(old[key]))
            assert error < 1e-12
            checks.append(dict(check='stage99_B_working_point', field=key, abs_difference=error))
    table(OUT/'metrics.tsv', metrics)
    table(OUT/'paired.tsv', paired)
    table(OUT/'working_points.tsv', operating)
    table(OUT/'paired_working_points.tsv', paired_work)
    table(OUT/'thresholds.tsv', thresholds)
    table(OUT/'B_reproduction_checks.tsv', checks)
    table(OUT/'ROC.tsv', [dict(model=name, FPR=float(a), TPR=float(b)) for name, (f, t) in rocs.items() for a, b in zip(f, t)])
    supported = paired[0]['high95'] < 0
    save(OUT/'decision.json', dict(primary='cal paired logscore B-minus-A upper95<0',
        primary_information_gain_supported=bool(supported), Brier_gain_supported=paired[1]['high95'] < 0,
        complete_energy_gain_measured=False, strict_low_FPR_population_certified=False,
        expansion_authorized=False, new_energy_model_promotion=False,
        action='separate full-input/energy contract required before expansion' if supported else 'stop extension of this collection-statistic family',
        scope='original source/X-quota train/cal cohort, conditional500 component incoming, no source/refit/response/research-selection coverage'))
    return len(checks)
