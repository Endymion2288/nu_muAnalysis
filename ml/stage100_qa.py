"""Batch-only <=40 original identity QA; no training or optimizer."""
import json
import time
import tempfile
import importlib.metadata
import numpy as np
import xgboost as xgb
from stage100_common import REPO, OUT, inputs, read, save, cost


def main():
    tick, cpu = time.perf_counter(), time.process_time()
    cases, A, B, avail = inputs(qa=True)
    assert len(cases) == 40
    original = REPO/'ml/artifacts/stage99/B_classifier_B.json'
    original_bytes = original.read_bytes()
    booster = xgb.Booster()
    booster.load_model(original)
    booster.set_param({'nthread': 1})
    matrix = xgb.DMatrix(B)
    pred = booster.predict(matrix)
    with tempfile.TemporaryDirectory() as directory:
        path = directory+'/roundtrip.json'
        booster.save_model(path)
        second = xgb.Booster()
        second.load_model(path)
        second.set_param({'nthread': 1})
        again = second.predict(matrix)
    np.testing.assert_array_equal(pred, again)
    assert original.read_bytes() == original_bytes
    old = {int(c['row']): float(c['B']) for c in read(REPO/'ntuples/energy_ml_stage99/B_classifier_predictions.tsv')}
    matched = [i for i, c in enumerate(cases) if c['row'] in old]
    assert matched
    np.testing.assert_array_equal(pred[matched], [old[cases[i]['row']] for i in matched])
    save(OUT/'QA.json', dict(passed=True, identities=40, optimizer_steps=0, new_fits=0,
         rows=[c['row'] for c in cases], sources=len({c['source'] for c in cases}),
         A_columns=A.shape[1], B_columns=B.shape[1], native_exact_available=0,
         collection_available=int(avail.sum()), matched_saved_B_cal=len(matched),
         B_roundtrip_prediction_bit_equal=True, B_original_file_byte_equal=True,
         nonfinite_A_values=int(np.isnan(A).sum()), legal_negative_values=int((A[:, :62] < 0).sum()),
         xgboost_version=xgb.__version__, sklearn_version=importlib.metadata.version('scikit-learn'),
         **cost(tick, cpu)))
    print((OUT/'QA.json').read_text(), flush=True)


if __name__ == '__main__':
    main()
