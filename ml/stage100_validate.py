"""Independent persisted-model and sklearn metric audit, zero new fits."""
import json
import time
import numpy as np
import xgboost as xgb
from sklearn.metrics import log_loss, brier_score_loss, roc_auc_score
from stage100_common import REPO, OUT, CACHE, ART, inputs, task, read, save, table, cost


def scores(y, p):
    # sklearn standardizes partial AUC to a random baseline of .5; invert it
    # to match the reported area divided by the interval width .1.
    standardized = roc_auc_score(y, p, max_fpr=.1)
    partial = (.005+(2*standardized-1)*(.1-.005))/.1
    return [log_loss(y, p, labels=[0, 1]), brier_score_loss(y, p), roc_auc_score(y, p), partial]


def main():
    tick, cpu = time.perf_counter(), time.process_time()
    assert json.loads((OUT/'complete.json').read_text())['new_A_fits'] == 1
    cases, A, B, _ = inputs()
    y, tr, cal, _ = task(cases)
    cal_idx, train_idx = np.flatnonzero(cal), np.flatnonzero(tr)
    rows, train_rows = read(CACHE/'predictions.tsv'), read(CACHE/'train_predictions.tsv')
    old = read(REPO/'ntuples/energy_ml_stage99/B_classifier_predictions.tsv')
    np.testing.assert_array_equal([int(r['row']) for r in rows], [cases[i]['row'] for i in cal_idx])
    np.testing.assert_array_equal([int(r['row']) for r in train_rows], [cases[i]['row'] for i in train_idx])
    np.testing.assert_array_equal([float(r['B']) for r in rows], [float(r['B']) for r in old])
    assert not {c['key_id'] for c in cases if c['role'] == 1} & {c['key_id'] for c in cases if c['role'] == 2}
    assert not {c['source'] for c in cases if c['role'] == 1} & {c['source'] for c in cases if c['role'] == 2}
    q = {name: np.array([float(r[name]) for r in rows]) for name in ['A', 'B']}
    trainq = {name: np.array([float(r[name]) for r in train_rows]) for name in ['A', 'B']}
    for name, path, values in [('A', ART/'A_classifier.json', A), ('B', REPO/'ml/artifacts/stage99/B_classifier_B.json', B)]:
        booster = xgb.Booster()
        booster.load_model(path)
        booster.set_param({'nthread': 1})
        pred = booster.predict(xgb.DMatrix(values)).astype(float)
        np.testing.assert_array_equal(pred[cal], q[name])
        np.testing.assert_array_equal(pred[tr], trainq[name])
    # Expand sampled incoming IDs, independently of the reporter's matrix means.
    keys = np.array([cases[i]['key_id'] for i in cal_idx])
    order = np.argsort(keys)
    component = np.array([cases[i]['component'] for i in cal_idx])[order]
    rng = np.random.default_rng(2026110499)
    counts = np.zeros((500, len(keys)), int)
    for comp in sorted(set(component)):
        ids = np.flatnonzero(component == comp)
        counts[:, ids] = rng.multinomial(len(ids), np.full(len(ids), 1/len(ids)), size=500)
    boot = {name: [] for name in ['A', 'B']}
    labels = y[cal]
    for draw in counts:
        sample = order[np.repeat(np.arange(len(keys)), draw)]
        for name in ['A', 'B']:
            boot[name].append(scores(labels[sample], q[name][sample]))
    boot = {k: np.array(v) for k, v in boot.items()}
    metrics = read(OUT/'metrics.tsv')
    paired = read(OUT/'paired.tsv')
    checks = []
    for name in ['A', 'B']:
        actual = scores(labels, q[name])
        stored = next(r for r in metrics if r['model'] == name)
        for j, metric in enumerate(['logscore', 'Brier', 'AUC', 'pAUC_0_10']):
            bounds = np.quantile(boot[name][:, j], [.025, .975])
            for suffix, value in [('', actual[j]), ('_low95', bounds[0]), ('_high95', bounds[1])]:
                err = abs(value-float(stored[metric+suffix]))
                assert err < 1e-12, (name, metric, err)
                checks.append(dict(check='independent_sklearn_sample_expansion', model=name, metric=metric+suffix, max_abs_error=float(err)))
    for j, metric in enumerate(['logscore', 'Brier', 'AUC', 'pAUC_0_10']):
        actual = scores(labels, q['B'])[j]-scores(labels, q['A'])[j]
        bounds = np.quantile(boot['B'][:, j]-boot['A'][:, j], [.025, .975])
        stored = next(r for r in paired if r['metric'] == metric)
        for field, value in [('B_minus_A', actual), ('low95', bounds[0]), ('high95', bounds[1])]:
            err = abs(value-float(stored[field]))
            assert err < 1e-12
            checks.append(dict(check='independent_paired_interval', model='B_minus_A', metric=metric+'_'+field, max_abs_error=float(err)))
    working, paired_working = read(OUT/'working_points.tsv'), read(OUT/'paired_working_points.tsv')
    flags = {}
    for r in working:
        name, alpha = r['model'], float(r['nominal_FPR'])
        low = trainq[name][y[tr] == 0]
        # Descend unique thresholds from +infinity until another step violates alpha.
        selected = np.inf
        for t in np.unique(low)[::-1]:
            if np.mean(low > t) <= alpha+1e-14:
                selected = t
        assert selected == float(r['train_threshold'])
        flags[name, alpha] = q[name] > selected
        for cls, lab in [(0, 'L_FPR'), (1, 'H_TPR')]:
            z = labels == cls
            stats = []
            for draw in counts:
                sample = order[np.repeat(np.arange(len(keys)), draw)]
                chosen = sample[labels[sample] == cls]
                stats.append(flags[name, alpha][chosen].mean())
            bounds = np.quantile(stats, [.025, .975])
            for field, value in [(lab, flags[name, alpha][z].mean()), (lab+'_low95', bounds[0]), (lab+'_high95', bounds[1])]:
                err = abs(value-float(r[field]))
                assert err < 1e-12
                checks.append(dict(check='independent_train_threshold_and_working', model=name, metric=field, max_abs_error=float(err)))
    for r in paired_working:
        alpha = float(r['nominal_FPR'])
        delta = flags['B', alpha].astype(float)-flags['A', alpha].astype(float)
        for cls, lab in [(0, 'L_FPR'), (1, 'H_TPR')]:
            point = 100*delta[labels == cls].mean()
            values = []
            for draw in counts:
                sample = order[np.repeat(np.arange(len(keys)), draw)]
                values.append(100*delta[sample[labels[sample] == cls]].mean())
            bounds = np.quantile(values, [.025, .975])
            for field, value in [(lab+'_delta_pp', point), (lab+'_low95_pp', bounds[0]), (lab+'_high95_pp', bounds[1])]:
                err = abs(value-float(r[field]))
                assert err < 1e-10
                checks.append(dict(check='independent_paired_working', model='B_minus_A', metric=field, max_abs_error=float(err)))
    table(OUT/'independent_checks.tsv', checks)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6), layout='constrained')
    curves = read(OUT/'ROC.tsv')
    for name, color in [('A', 'C0'), ('B', 'C1')]:
        r = [v for v in curves if v['model'] == name]
        axes[0].plot([float(v['FPR']) for v in r], [float(v['TPR']) for v in r], color=color, label=name)
        r = next(v for v in working if v['model'] == name and float(v['nominal_FPR']) == .02)
        x, z = float(r['L_FPR']), float(r['H_TPR'])
        axes[1].errorbar(x, z, xerr=[[x-float(r['L_FPR_low95'])], [float(r['L_FPR_high95'])-x]],
                        yerr=[[z-float(r['H_TPR_low95'])], [float(r['H_TPR_high95'])-z]], fmt='o', color=color, label=name)
    axes[0].set(xlabel='Cal low-E false-positive rate', ylabel='Cal high-E recognition', xlim=(0, 1), ylim=(0, 1), title='Fixed pilot: L20 / H46')
    axes[1].set(xlabel='Actual cal low-E false-positive rate', ylabel='Cal high-E recognition', xlim=(-.02, .3), ylim=(.4, 1), title='Train-frozen nominal 2% thresholds')
    for ax in axes:
        ax.legend(title='A:62 summaries; B:+activity', fontsize=8)
    fig.savefig(OUT/'paired_pilot.svg')
    fig.savefig(OUT/'paired_pilot.pdf')
    plt.close(fig)
    save(OUT/'validation.json', dict(passed=True, new_fits=0, optimizer_steps=0,
        all_cal_and_train_booster_predictions_bit_equal=True, B_saved_cal_bit_equal=True,
        original_role_source_incoming_disjoint=True, independent_scalar_checks=len(checks),
        max_abs_error=max(r['max_abs_error'] for r in checks), replicates=500,
        independent_implementation='sklearn metrics, standardized partial-AUC inversion, explicit repeated-incoming sample expansion',
        **cost(tick, cpu)))
    print((OUT/'validation.json').read_text(), flush=True)


if __name__ == '__main__':
    main()
