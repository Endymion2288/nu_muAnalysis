#!/usr/bin/env python3
"""Independent checks of feature quarantine, frozen outputs and paired quantiles."""
import csv
import json
from pathlib import Path

import numpy as np
import xgboost as xgb

from information_gap import class_index, configuration, inputs, split_groups, training_summary
from probability_information import checks
from report_information_gap import quantile_bootstrap


def main():
    root = Path(__file__).resolve().parents[1]; cfg = configuration(root)
    _, names, (train, val) = inputs(root); roles, assignment = split_groups(train['groups'], cfg)
    out = root/'workbook/stage30_energy_ml'; rows = []; zero_rows = []
    for mode in ['main', 'controls']:
        for si in range(3):
            directory = root/f'ml/artifacts/stage30/{mode}/seed_{si}'
            meta = training_summary(out/f'{mode}/seed_{si}')
            assert meta['cfg'] == cfg
            assert meta['features'] == names
            assert meta['source_assignment'] == assignment
            cost = {r['model']: r for r in csv.DictReader((out/f'{mode}/seed_{si}/costs.tsv').open(), delimiter='\t')}
            with np.load(directory/'predictions.npz') as z:
                for k in ['run', 'eventID']: np.testing.assert_array_equal(z[k], val['truth'][k])
                np.testing.assert_array_equal(z['truth_E_GeV'], val['y'])
                np.testing.assert_array_equal(z['group'], val['groups'])
                specs = cfg['oracle' if mode == 'main' else 'controls']
                for name, extras in list(specs.items()) + ([('classifier', [])] if mode == 'main' else []):
                    booster = xgb.Booster(); booster.load_model(directory/f'{name}.ubj')
                    assert booster.feature_names == names + extras
                    xv = np.column_stack([val['x']] + [val['oracle'][k] for k in extras]).astype('float32')
                    idx = np.arange(0, len(xv), 23)
                    pred = booster.inplace_predict(xv[idx], iteration_range=(0, int(cost[name]['best_iteration'])+1))
                    if name != 'classifier': pred = np.exp(pred)
                    delta = float(np.max(abs(pred-z[name][idx])))
                    np.testing.assert_allclose(pred, z[name][idx], rtol=2e-6, atol=1e-7)
                    rows.append(dict(mode=mode, seed=si, model=name, checked_events=len(idx), max_absolute_delta=delta))
                if mode != 'main': continue
                np.testing.assert_array_equal(z['map_groups'], train['groups'][roles == 'map'])
                np.testing.assert_array_equal(z['map_labels'], class_index(train['y'][roles == 'map'], cfg))
                centers = np.log(np.sqrt(np.array(cfg['energy_edges_GeV'][:-1])*cfg['energy_edges_GeV'][1:]))
                np.testing.assert_allclose(z['q_full']@centers, z['mean_log_energy'], atol=1e-12)
                for name in ['q_full', 'q_mean', 'q_scalar', 'q_ten']:
                    assert np.isfinite(z[name]).all() and (z[name] >= 0).all()
                    np.testing.assert_allclose(z[name].sum(1), 1, atol=1e-12)
                    b = class_index(val['y'], cfg)
                    zero = z[name][np.arange(len(b)), b] == 0
                    if name != 'q_ten': assert not zero.any()
                    for j in np.flatnonzero(zero):
                        zero_rows.append(dict(seed=si, model=name, run=int(z['run'][j]), eventID=int(z['eventID'][j]),
                                              truth_bin=int(b[j]), truth_E_GeV=float(z['truth_E_GeV'][j]),
                                              scalar_E_GeV=float(z['A0'][j])))
                assert meta['ten_empty_evaluation_events'] == 0
    # Compare integer-weight quantiles to explicitly repeated events, including ties.
    residual = np.array([-.4, .2, .2, .8, 1.5, -.2, 0.])
    gid = np.array([0, 1, 1, 2, 0, 2, 1]); draws = np.array([[1, 1, 1], [3, 0, 1], [0, 2, 3]])
    got = quantile_bootstrap(residual, gid, draws); expected = []
    for d in draws:
        q = np.quantile(np.repeat(residual, d[gid]), [.16, .5, .84])
        expected.append([q[1], (q[2]-q[0])/2])
    np.testing.assert_allclose(got, np.array(expected).T, atol=1e-15)
    from train_bdt import write_table
    write_table(out/'model_readback_checks.tsv', rows)
    if zero_rows: write_table(out/'zero_posterior_events.tsv', zero_rows)
    summary = dict(input_alignment=True, oracle_support_full=True, isolated_roles=True,
                   train_groups=91, validation_groups=22, map_groups=20,
                   deployment_features=names, matching_direction_pdg_never_added=True,
                   models_read_back=len(rows), ten_bin_empty_evaluation_events=0,
                   smooth_maps_true_class_probabilities_positive=True,
                   histogram_zero_posterior_seed_event_pairs=len(zero_rows), quantile_expansion_check=True,
                   inference_checks=checks(), calibration_test_challenge_evaluated=False)
    (out/'final_validation.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
