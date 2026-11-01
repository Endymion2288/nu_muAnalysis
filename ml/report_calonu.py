#!/usr/bin/env python3
"""Locked, paired CaloNu readout ablation with source and calibration uncertainty."""
import json
import resource
import time
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

from calonu_inputs import configuration, feature_names, load
from calonu_ablation import predict, reports, root, matrix
from frozen_evaluation import save_json, stamp
from report_frozen_evaluation import METRICS, draws, intervals, macro_result, sufficient_bootstrap
from train_bdt import metric_values, write_table


def strata(data, cfg):
    n = len(data['run'])
    proxy = data['primary_kinematic_parent_proxy']
    finite = np.isfinite(data['CaloNu_total_E_EM'])
    subsets = dict(all=np.ones(n, bool), kinematic_parent_proxy=proxy, other_than_proxy=~proxy,
                   primary_invalid=~data['primary_valid'], calonu_zero=finite & (data['CaloNu_total_E_EM'] == 0),
                   calonu_nonzero=finite & (data['CaloNu_total_E_EM'] != 0), calonu_invalid=~finite)
    for prefix, value in [('reco_p', data['reco_p_GeV']), ('truth_p', data['primary_p_GeV']),
                          ('proxy_truth_p', data['primary_p_GeV'])]:
        for lo, hi, suffix in [(100, 1000, '100_1000'), (100, 250, '100_250'),
                               (250, 1000, '250_1000'), (1000, np.inf, 'ge1000')]:
            subsets[prefix + '_' + suffix] = (value >= lo) & (value < hi) & (proxy if prefix.startswith('proxy') else True)
    for lo, hi in zip(cfg['energy_edges_GeV'][:-1], cfg['energy_edges_GeV'][1:]):
        subsets[f'energy_{lo}_{hi}'] = (data['truth_E_GeV'] >= lo) & (data['truth_E_GeV'] < hi)
    y = data['y_lepton']
    for lo, hi in zip(cfg['y_edges'][:-1], cfg['y_edges'][1:]):
        subsets[f'y_{lo}_{hi}'] = (y >= lo) & ((y <= hi) if hi == 1 else (y < hi))
    subsets['truth_p_100_1000_y_ge0p8'] = (data['primary_p_GeV'] >= 100) & (data['primary_p_GeV'] < 1000) & (y >= .8) & (y <= 1)
    subsets['proxy_truth_p_100_1000_y_ge0p8'] = subsets['truth_p_100_1000_y_ge0p8'] & proxy
    subsets['y_missing_or_outside'] = ~np.isfinite(y) | (y < 0) | (y > 1)
    z = data['vertex_z_mm']
    for lo, hi in [(-3000, -2928), (-2812, -2650), (-2650, -2300), (-2300, -1950), (-1769.65, -1619.65)]:
        subsets[f'vertex_z_{lo}_{hi}'] = (z >= lo) & (z < hi)
    for component in np.unique(data['component']):
        subsets['component_' + component] = data['component'] == component
    return subsets


def old_references(repo, data):
    import xgboost as xgb
    names, extra = feature_names(repo)
    result = {}
    state = json.loads((repo / 'workbook/stage34_energy_ml/calibration_state.json').read_text())
    for version in ['F5', 'F6']:
        x = matrix(data, names + (extra if version == 'F6' else []))
        raw = []
        for i in range(3):
            model = xgb.Booster(params={'nthread': 1})
            path = repo / (f'ml/artifacts/stage30/main/seed_{i}/A0.ubj' if version == 'F5' else f'ml/artifacts/stage31/seed_{i}/nu_F6.ubj')
            model.load_model(path)
            assert model.feature_names == names + (extra if version == 'F6' else [])
            raw.append(model.inplace_predict(x, iteration_range=(0, model.best_iteration + 1)).astype(float))
        result['ordinary_' + version + '_frozen_reference'] = np.mean(raw, axis=0) + state['offset_log'][version]
    return result


def main():
    repo = Path(__file__).resolve().parents[1]
    out = reports(repo)
    assert not (out / 'test_summary.json').exists(), 'Never silently reevaluate a published locked test'
    cfg = configuration(repo)
    state = json.loads((out / 'calibration_state.json').read_text())
    assert state['six_models_frozen'] and state['test_not_evaluated']
    tick = time.perf_counter()
    cpu = time.process_time()
    cal = load(repo, 'calibration')
    data = load(repo, 'test')
    assert not set(cal['group']) & set(data['group'])
    infer = time.perf_counter()
    pred = predict(repo, data)
    inference = time.perf_counter() - infer
    with np.load(root(repo) / 'calibration_predictions.npz') as z:
        calpred = {k: z[k] for k in z.files}
    for version in cfg['models']:
        np.testing.assert_allclose(np.mean(np.log(cal['truth_E_GeV']) - calpred[version]), state['offset_log'][version], atol=1e-14)
    rng = np.random.default_rng(cfg['bootstrap_seed'])
    _, cgid, cw = draws(cal['group'], rng, cfg['bootstrap_replicates'])
    cn = np.bincount(cgid)
    cb = {v: (cw @ np.bincount(cgid, weights=np.log(cal['truth_E_GeV']) - calpred[v])) / (cw @ cn) for v in cfg['models']}
    groups, gid, weights = draws(data['group'], rng, cfg['bootstrap_replicates'])
    zero = np.zeros(len(weights))
    methods = dict(mu_raw=(np.log(data['reco_p_GeV']), 0., zero), mu_div0p8=(np.log(data['reco_p_GeV'] / .8), 0., zero))
    for version in cfg['models']:
        methods[version + '_raw'] = pred[version], 0., zero
        methods[version + '_cal'] = pred[version], state['offset_log'][version], cb[version]
    # These are out-of-domain references; never treated as the readout causal contrast.
    for name, value in old_references(repo, data).items():
        methods[name] = value, 0., zero
    np.savez_compressed(root(repo) / 'test_predictions.npz', **{k: v[0] for k, v in methods.items()})
    subsets = strata(data, cfg)
    table = []
    store = {}
    truth = np.log(data['truth_E_GeV'])
    for subset, mask in subsets.items():
        for model, (logp, correction, bootcorr) in methods.items():
            row = dict(subset=subset, model=model, N=int(mask.sum()), source_groups=len(np.unique(data['group'][mask])))
            if not mask.any():
                for k in METRICS:
                    row.update({k: np.nan, k + '_lo': np.nan, k + '_hi': np.nan, k + '_invalid_boot': len(weights)})
                table.append(row)
                continue
            central = metric_values(data['truth_E_GeV'], np.exp(logp + correction), mask)
            sampled = sufficient_bootstrap((logp - truth)[mask], gid[mask], weights, bootcorr)
            for k in METRICS:
                lo, hi, invalid = intervals(sampled[k])
                row.update({k: central[k], k + '_lo': lo, k + '_hi': hi, k + '_invalid_boot': invalid})
            table.append(row)
            store[subset, model] = central, sampled
    write_table(out / 'test_metrics.tsv', table)
    paired = []
    for subset in subsets:
        for reference, candidate in [('C0_cal', 'C1_cal'), ('C0_raw', 'C1_raw')]:
            if (subset, reference) not in store:
                continue
            a, ab = store[subset, reference]
            b, bb = store[subset, candidate]
            row = dict(subset=subset, reference=reference, candidate=candidate, N=a['N'])
            stats = {k + '_delta': (b[k] - a[k], bb[k] - ab[k]) for k in METRICS}
            stats['relative_log_RMSE_gain'] = 1 - b['log_RMSE'] / a['log_RMSE'], 1 - bb['log_RMSE'] / ab['log_RMSE']
            for k, (value, sampled) in stats.items():
                lo, hi, invalid = intervals(sampled)
                row.update({k: value, k + '_lo': lo, k + '_hi': hi, k + '_invalid_boot': invalid})
            paired.append(row)
    write_table(out / 'test_paired.tsv', paired)
    macro = []
    macro_store = {}
    for model, (logp, correction, bootcorr) in methods.items():
        point, boot, active = macro_result(logp - truth, data['truth_E_GeV'], subsets['all'], gid, weights, correction, bootcorr, cfg['energy_edges_GeV'])
        lo, hi, invalid = intervals(boot)
        macro.append(dict(model=model, macro_log_RMSE=point, lo=lo, hi=hi, invalid_boot=invalid, active_bins=','.join(map(str, active))))
        macro_store[model] = point, boot
    write_table(out / 'test_macro.tsv', macro)
    response = []
    for name, mask in subsets.items():
        if not mask.any():
            continue
        energy = data['ML_calonu_total_E_EM_GeV'][mask]
        transfer = data['truth_E_GeV'][mask] * data['y_lepton'][mask]
        valid = np.isfinite(transfer) & np.isfinite(energy)
        rho = spearmanr(energy[valid], transfer[valid]).statistic if len(np.unique(energy[valid])) > 1 else np.nan
        finite = np.isfinite(energy)
        nonzero = finite & (energy != 0)
        sample = weights @ np.bincount(gid[mask], weights=nonzero.astype(float), minlength=len(groups))
        counts = weights @ np.bincount(gid[mask], minlength=len(groups))
        with np.errstate(divide='ignore', invalid='ignore'):
            lo, hi, invalid = intervals(sample / counts)
        q = np.quantile(energy[finite], [0, .16, .5, .84, 1]) if finite.any() else np.full(5, np.nan)
        response.append(dict(subset=name, N=int(mask.sum()), source_groups=len(np.unique(data['group'][mask])),
                             finite=int(finite.sum()), nonfinite=int((~finite).sum()),
                             nonzero=int(nonzero.sum()), nonzero_fraction=float(np.mean(nonzero)), nonzero_fraction_lo=lo,
                             nonzero_fraction_hi=hi, invalid_boot=invalid, min_GeV=q[0], q16_GeV=q[1], median_GeV=q[2],
                             q84_GeV=q[3], max_GeV=q[4], spearman_with_transfer_proxy=rho))
    write_table(out / 'test_readout_response.tsv', response)
    focus = next(r for r in paired if r['subset'] == 'reco_p_100_1000' and r['reference'] == 'C0_cal')
    allrow = next(r for r in paired if r['subset'] == 'all' and r['reference'] == 'C0_cal')
    a, ab = macro_store['C0_cal']
    b, bb = macro_store['C1_cal']
    lo, hi, invalid = intervals(1 - bb / ab)
    summary = dict(created_utc=stamp(), events=len(truth), groups=len(groups),
                   primary_valid=int(data['primary_valid'].sum()), kinematic_parent_proxy=int(data['primary_kinematic_parent_proxy'].sum()),
                   strict_primary_barcode_confirmation='unmeasured: truth_barcode absent',
                   micro_C0_cal=store['all', 'C0_cal'][0]['log_RMSE'], micro_C1_cal=store['all', 'C1_cal'][0]['log_RMSE'],
                   all_relative_gain=allrow['relative_log_RMSE_gain'], all_gain_lo=allrow['relative_log_RMSE_gain_lo'], all_gain_hi=allrow['relative_log_RMSE_gain_hi'],
                   focus_relative_gain=focus['relative_log_RMSE_gain'], focus_gain_lo=focus['relative_log_RMSE_gain_lo'], focus_gain_hi=focus['relative_log_RMSE_gain_hi'],
                   macro_C0_cal=a, macro_C1_cal=b, macro_gain=1 - b / a, macro_gain_lo=lo, macro_gain_hi=hi,
                   further_readout_modeling_gate=bool(focus['relative_log_RMSE_gain'] >= .05 and focus['relative_log_RMSE_gain_lo'] > 0 and allrow['relative_log_RMSE_gain_lo'] > -.01),
                   calibration_offset_95={v: list(intervals(cb[v])[:2]) for v in cfg['models']},
                   six_model_inference_wall_s=inference, six_model_inference_events_per_s=len(truth) / inference,
                   wall_s=time.perf_counter() - tick, cpu_s=time.process_time() - cpu,
                   peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
                   bootstrap_replicates=len(weights), calibration_uncertainty_propagated=True, unchanged_test_parameters=True)
    save_json(out / 'test_summary.json', summary)
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
