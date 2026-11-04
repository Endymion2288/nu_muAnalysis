"""One A fit, durable predictions first, frozen-B paired evaluation second."""
import json
import os
import time
import numpy as np
import xgboost as xgb
from stage100_common import REPO, OUT, CACHE, ART, inputs, read, save, table, task, cost
from stage100_report import report


def atomic_table(path, rows):
    temp = path.with_suffix('.tmp')
    table(temp, rows)
    assert read(temp) == [{k: str(v) for k, v in r.items()} for r in rows]
    os.replace(temp, path)
    assert path.is_file()


def main():
    tick, cpu = time.perf_counter(), time.process_time()
    assert json.loads((OUT/'QA.json').read_text())['passed']
    assert not (OUT/'fit_started.json').exists()
    assert not (CACHE/'predictions.tsv').exists()
    ART.mkdir(parents=True, exist_ok=True)
    cases, A, B, avail = inputs()
    labels, train, cal, support = task(cases)
    table(OUT/'class_support.tsv', support)
    train_idx, cal_idx = np.flatnonzero(train), np.flatnonzero(cal)
    frozen = read(REPO/'ntuples/energy_ml_stage99/B_classifier_predictions.tsv')
    np.testing.assert_array_equal([c['row'] for c in frozen], np.array([str(cases[i]['row']) for i in cal_idx]))
    np.testing.assert_array_equal([int(c['label']) for c in frozen], labels[cal])
    B_saved = np.array([float(c['B']) for c in frozen])
    old_path = REPO/'ml/artifacts/stage99/B_classifier_B.json'
    old_bytes = old_path.read_bytes()
    booster = xgb.Booster()
    booster.load_model(old_path)
    booster.set_param({'nthread': 1})
    B_all = booster.predict(xgb.DMatrix(B)).astype(float)
    np.testing.assert_array_equal(B_all[cal], B_saved)
    # Write the one-attempt ledger immediately before invoking the optimizer.
    save(OUT/'fit_started.json', dict(attempt=1, cell='A', train_N=int(train.sum()),
         cal_N=int(cal.sum()), energy_fits=0, B_fits=0, seed=2026110499))
    model = xgb.XGBClassifier(n_estimators=100, max_depth=2, learning_rate=.05,
        min_child_weight=10, reg_lambda=10, random_state=2026110499,
        n_jobs=1, tree_method='hist', objective='binary:logistic', eval_metric='logloss')
    fit_tick, fit_cpu = time.perf_counter(), time.process_time()
    model.fit(A[train], labels[train])
    fit_cost = cost(fit_tick, fit_cpu)
    A_cal = np.clip(model.predict_proba(A[cal])[:, 1].astype(float), 1e-12, 1-1e-12)
    A_train = model.predict_proba(A[train])[:, 1].astype(float)
    rows = [dict(row=cases[i]['row'], key_id=cases[i]['key_id'], label=int(labels[i]), A=float(a), B=float(b))
            for i, a, b in zip(cal_idx, A_cal, B_saved)]
    train_rows = [dict(row=cases[i]['row'], label=int(labels[i]), A=float(a), B=float(b))
                  for i, a, b in zip(train_idx, A_train, B_all[train])]
    atomic_table(CACHE/'predictions.tsv', rows)
    atomic_table(CACHE/'train_predictions.tsv', train_rows)
    save(OUT/'predictions_persisted.json', dict(cal_rows=len(rows), train_rows=len(train_rows), readback_exact=True, fits_completed=1))
    model.get_booster().save_model(ART/'A_classifier.json')
    again = xgb.Booster()
    again.load_model(ART/'A_classifier.json')
    again.set_param({'nthread': 1})
    np.testing.assert_array_equal(again.predict(xgb.DMatrix(A[cal])).astype(float), A_cal)
    assert old_path.read_bytes() == old_bytes
    nchecks = report([cases[i] for i in cal_idx], [cases[i] for i in train_idx], labels[cal], labels[train],
                     dict(A=A_cal, B=B_saved), dict(A=A_train, B=B_all[train]))
    table(OUT/'availability.tsv', [dict(role=code, N=sum(c['role'] == code for c in cases),
          available=int(sum(v for c, v in zip(cases, avail) if c['role'] == code)),
          unavailable=int(sum(1-v for c, v in zip(cases, avail) if c['role'] == code))) for code in [1, 2]])
    save(OUT/'complete.json', dict(passed=True, N=len(cases), unique_incoming=len({c['key_id'] for c in cases}),
         new_A_fits=1, B_fits=0, new_energy_fits=0, new_temperature_fits=0, ROOT_reads=0,
         cal_N=len(rows), train_N=len(train_rows), B_cal_prediction_bit_equal=True,
         B_model_byte_equal=True, A_model_roundtrip_prediction_bit_equal=True,
         prior_B_scalar_checks=nchecks, fit=fit_cost, **cost(tick, cpu)))
    print((OUT/'complete.json').read_text(), flush=True)


if __name__ == '__main__':
    main()
