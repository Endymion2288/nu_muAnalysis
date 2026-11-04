"""Zero-fit diagnosis of identical A/B predictions; original train/cal only."""
import json
import time
from collections import Counter

import numpy as np
import xgboost as xgb

from audited_features import configuration
from stage100_common import ACTIVITY, ART, OUT, REPO, cost, inputs, save, table, task


def main():
    tick, cpu = time.perf_counter(), time.process_time()
    cases, A, B, available = inputs()
    _, train, cal, _ = task(cases)
    assert np.array_equal(A, B[:, :127], equal_nan=True)
    names = configuration()['features']
    names = names + [n+'_missing' for n in names] + [
        'status_other', 'PHYS_available', 'exact_native_available']
    names += ACTIVITY + [n+'_missing' for n in ACTIVITY]
    activity = []
    for role, mask in [('train', train), ('cal', cal)]:
        for j in range(127, 211):
            values = B[mask, j]
            finite = values[np.isfinite(values)]
            activity.append(dict(role=role, column=j, feature=names[j],
                N=len(values), finite_N=len(finite), missing_N=int(np.isnan(values).sum()),
                unique_finite=len(np.unique(finite)),
                minimum=float(finite.min()) if len(finite) else '',
                maximum=float(finite.max()) if len(finite) else ''))
    table(OUT/'activity_input_audit.tsv', activity)
    models, raw, prediction = {}, {}, {}
    for name, path, values in [('A', ART/'A_classifier.json', A),
            ('B', REPO/'ml/artifacts/stage99/B_classifier_B.json', B)]:
        model = xgb.Booster()
        model.load_model(path)
        model.set_param({'nthread': 1})
        models[name] = model
        raw[name] = json.loads(path.read_text())
        prediction[name] = model.predict(xgb.DMatrix(values))
    trees = {k: v['learner']['gradient_booster']['model']['trees'] for k, v in raw.items()}
    splits = {}
    for name in ['A', 'B']:
        counts = Counter(int(t['split_indices'][i]) for t in trees[name]
                         for i, left in enumerate(t['left_children']) if left >= 0)
        splits[name] = counts
    table(OUT/'tree_split_audit.tsv', [dict(model=k, column=j, feature=names[j], splits=n)
          for k in ['A', 'B'] for j, n in sorted(splits[k].items())])
    differing_fields = Counter()
    for a, b in zip(trees['A'], trees['B']):
        for key in set(a) | set(b):
            if a.get(key) != b.get(key):
                differing_fields[key] += 1
    value_summary = {}
    for role in ['train', 'cal']:
        rows = [r for r in activity if r['role'] == role]
        value_summary[role] = dict(
            varying_values=sum(r['unique_finite'] > 1 for r in rows if r['column'] < 169),
            varying_masks=sum(r['unique_finite'] > 1 for r in rows if r['column'] >= 169),
            populated_values=sum(r['finite_N'] > 0 for r in rows if r['column'] < 169))
    result = dict(passed=True, new_fits=0, optimizer_steps=0, ROOT_reads=0,
        original_train_cal_only=True, N=len(cases), shared_input_equal=True,
        model_dimensions={k: models[k].num_features() for k in models},
        trees={k: len(trees[k]) for k in trees},
        total_splits={k: sum(splits[k].values()) for k in splits},
        B_added_feature_splits=sum(n for j, n in splits['B'].items() if j >= 127),
        tree_dump_exact_equal=models['A'].get_dump(dump_format='json') == models['B'].get_dump(dump_format='json'),
        raw_tree_differing_fields=dict(differing_fields),
        base_score_equal=raw['A']['learner']['learner_model_param']['base_score'] ==
                         raw['B']['learner']['learner_model_param']['base_score'],
        all_2048_predictions_bit_equal=bool(np.array_equal(prediction['A'], prediction['B'])),
        max_abs_prediction_difference=float(np.max(np.abs(prediction['A']-prediction['B']))),
        activity_input=value_summary,
        availability={role: int(available[mask].sum()) for role, mask in [('train', train), ('cal', cal)]},
        interpretation='Fixed-model mechanism only; no extra feature was selected if B_added_feature_splits=0. '
                       'Nonconstant input does not guarantee predictive information or prove an information bound.',
        **cost(tick, cpu))
    assert result['model_dimensions'] == {'A': 127, 'B': 211}
    save(OUT/'structural_audit.json', result)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
