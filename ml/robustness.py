#!/usr/bin/env python3
"""Frozen BDT capacity/prior controls; reads train/validation caches only."""
import argparse
import csv
import json
import resource
import time
from pathlib import Path

import numpy as np
import xgboost as xgb
import yaml

from train_bdt import check_features, load, macro_score, metric_values, write_table


def conditional_cells(data, config):
    keys = np.column_stack([
        data['run'], data['LeadTrack_charge'],
        np.floor(np.log(data['ML_mu_p_GeV']) / config['log_p_width']),
        np.floor(data['LeadTrack_Theta'] / config['theta_width_mrad']),
        np.floor(data['LeadTrack_rVetoNu'] / config['radius_width_mm'])])
    _, inverse, counts = np.unique(keys, axis=0, return_inverse=True, return_counts=True)
    order = np.argsort(inverse, kind='stable')
    cells = np.split(order, np.cumsum(counts)[:-1])
    return cells


def permuted_donors(cells, n, rng):
    donors = np.arange(n)
    for indices in cells:
        donors[indices] = rng.permutation(indices)
    return donors


def bin_weights(train_energy, energy, edges):
    train_bin = np.searchsorted(edges, train_energy, side='right') - 1
    bins = np.searchsorted(edges, energy, side='right') - 1
    if np.any((train_bin < 0) | (train_bin >= len(edges)-1)) or np.any((bins < 0) | (bins >= len(edges)-1)):
        raise ValueError('Prior reweighting outside frozen energy support')
    counts = np.bincount(train_bin, minlength=len(edges)-1)
    if np.any(counts == 0):
        raise ValueError('Unsupported training energy bin')
    mapping = len(train_energy) / (len(counts) * counts)
    return mapping[bins], counts, mapping


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--seed-index', type=int, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args()
    started = time.perf_counter()
    cpu_start = time.process_time()
    repo = args.repo.resolve()
    baseline = yaml.safe_load((repo/'ml/configs/baseline.yaml').read_text())
    study = yaml.safe_load((repo/'ml/configs/robustness.yaml').read_text())
    rows = list(csv.DictReader((repo/'ml/configs/files.tsv').open(), delimiter='\t'))
    train, train_groups = load(rows, baseline, 'train')
    val, val_groups = load(rows, baseline, 'validation')
    assert not set(train_groups) & set(val_groups)
    if args.smoke:
        train = {k:v[:1200] for k,v in train.items()}
        val = {k:v[:400] for k,v in val.items()}
        train_groups, val_groups = train_groups[:1200], val_groups[:400]
    seed = study['seeds'][args.seed_index]
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    ytrain, y = train[baseline['target']], val[baseline['target']]
    edges = np.array(baseline['energy_edges_GeV'])
    bins = [(y >= lo) & (y < hi) for lo,hi in zip(edges[:-1], edges[1:])]
    allowed = sum(baseline['feature_groups'].values(), [])
    predictions, costs, traces, permutations = {}, [], {}, []
    weights_report = {}
    models = {}

    def fit(name, groups, capacity, prior='unit', subset=None, shuffled=None, permutation_seed=None):
        names = sum([baseline['feature_groups'][g] for g in groups], [])
        check_features(names, allowed)
        select = np.ones(len(ytrain), dtype=bool) if subset is None else subset
        xtrain = np.column_stack([train[c] for c in names])
        xval = np.column_stack([val[c] for c in names])
        if shuffled:
            rng = np.random.default_rng(permutation_seed)
            for data, x in [(train,xtrain),(val,xval)]:
                cells = conditional_cells(data, study['conditional_permutation']['coarse'])
                donor = permuted_donors(cells, len(x), rng)
                indices = [names.index(c) for c in baseline['feature_groups'][shuffled]]
                x[:, indices] = x[donor][:, indices]
        wt, wv = np.ones(len(ytrain)), np.ones(len(y))
        if prior == 'flat_energy_bins':
            wt, counts, mapping = bin_weights(ytrain[select], ytrain, edges)
            wv, _, _ = bin_weights(ytrain[select], y, edges)
            weights_report[name] = dict(train_counts=counts.tolist(), mapping=mapping.tolist(),
                                        train_sumw=float(wt[select].sum()), train_sumw2=float((wt[select]**2).sum()),
                                        train_Neff=float(wt[select].sum()**2/(wt[select]**2).sum()))
        training = xgb.DMatrix(xtrain[select], label=np.log(ytrain[select]), weight=wt[select], feature_names=names, nthread=1)
        validation = xgb.DMatrix(xval, label=np.log(y), weight=wv, feature_names=names, nthread=1)
        params = dict(baseline['xgboost'])
        for k in ['n_estimators','early_stopping_rounds','n_jobs']:
            params.pop(k)
        params.update(max_depth=capacity['max_depth'], objective='reg:squarederror', seed=seed, nthread=1)
        history = {}
        tick, cpu = time.perf_counter(), time.process_time()
        model = xgb.train(params, training, num_boost_round=20 if args.smoke else capacity['rounds'],
                          evals=[(training,'train'),(validation,'validation')],
                          early_stopping_rounds=study['patience'], evals_result=history, verbose_eval=False)
        wall, used_cpu = time.perf_counter()-tick, time.process_time()-cpu
        raw = model.inplace_predict(xval, iteration_range=(0,model.best_iteration+1))
        predictions[name] = np.exp(raw)
        models[name] = (model,names,xval)
        traces[name] = history
        cost = dict(model=name,seed=seed,features=len(names),train_events=int(select.sum()),
                    best_iteration=model.best_iteration,iterations=len(history['train']['rmse']),
                    train_wall_s=wall,train_cpu_s=used_cpu,
                    macro_log_RMSE=macro_score(y,predictions[name],bins),
                    integrated_log_RMSE=float(np.sqrt(np.mean((raw-np.log(y))**2))))
        costs.append(cost)
        print(json.dumps(cost),flush=True)
        return cost

    for cap_name, cap in study['capacities'].items():
        for version, groups in study['versions'].items():
            fit(f'{cap_name}__{version}',groups,cap)
    if args.seed_index == 0:
        capacity = study['capacities']['d3_2400']
        if not args.smoke:
            for version in ['F1','F3','F5']:
                fit(f'flat_prior__{version}',study['versions'][version],capacity,prior='flat_energy_bins')
        rng = np.random.default_rng(seed)
        groups = rng.permutation(np.unique(train_groups))
        for fraction in study['learning_curve_fractions']:
            selected_groups = groups[:max(1,round(len(groups)*fraction))]
            select = np.isin(train_groups, selected_groups)
            for version in ['F1','F3']:
                fit(f'learning_{fraction}__{version}',study['versions'][version],capacity,subset=select)
        for version, group in [('F2','counts'),('F3','scintillator')]:
            fit(f'shuffled_train_val__{version}',study['versions'][version],capacity,
                shuffled=group,permutation_seed=seed+77)
        controls = study['conditional_permutation']
        for resolution in ['coarse','fine']:
            cells = conditional_cells(val,controls[resolution])
            movable = sum(len(c) for c in cells if len(c)>1)
            for version, groups in controls['targets'].items():
                model,names,x = models[f'd3_2400__{version}']
                for group in groups:
                    indices = [names.index(c) for c in baseline['feature_groups'][group]]
                    rng = np.random.default_rng(seed+100)
                    for repeat in range(2 if args.smoke else controls['repeats']):
                        donor = permuted_donors(cells,len(y),rng)
                        # No truth bin or target is used in the permutation.
                        assert np.array_equal(val['run'],val['run'][donor])
                        assert np.array_equal(val['LeadTrack_charge'],val['LeadTrack_charge'][donor])
                        shuffled = x.copy()
                        shuffled[:,indices] = x[donor][:,indices]
                        name = f'permuted__{resolution}__{version}__{group}__{repeat}'
                        prediction = np.exp(model.inplace_predict(shuffled,iteration_range=(0,model.best_iteration+1)))
                        predictions[name] = prediction
                        permutations.append(dict(model=name,base=f'd3_2400__{version}',group=group,
                                                 resolution=resolution,repeat=repeat,cells=len(cells),
                                                 movable_events=movable,changed_donor_events=int((donor!=np.arange(len(y))).sum()),
                                                 mean_abs_logp_change=float(np.mean(np.abs(np.log(val['ML_mu_p_GeV'][donor]/val['ML_mu_p_GeV'])))),
                                                 mean_abs_theta_change_mrad=float(np.mean(np.abs(val['LeadTrack_Theta'][donor]-val['LeadTrack_Theta']))),
                                                 mean_abs_radius_change_mm=float(np.mean(np.abs(val['LeadTrack_rVetoNu'][donor]-val['LeadTrack_rVetoNu'])))))
        for version in ['F2','F3','F5']:
            model,names,_ = models[f'd3_2400__{version}']
            model.save_model(output/f'{version}.ubj')
            (output/f'{version}.features.json').write_text(json.dumps(names,indent=2)+'\n')
    metrics = []
    for name,prediction in predictions.items():
        metrics.append(dict(model=name,seed=seed,macro_log_RMSE=macro_score(y,prediction,bins),
                            **metric_values(y,prediction,np.ones(len(y),dtype=bool))))
    write_table(output/'metrics.tsv',metrics)
    write_table(output/'costs.tsv',costs)
    if permutations:
        write_table(output/'permutation_controls.tsv',permutations)
    (output/'learning_traces.json').write_text(json.dumps(traces)+'\n')
    np.savez_compressed(output/'predictions.npz',run=val['run'],eventID=val['eventID'],truth_E_GeV=y,
                        group=val_groups,**predictions)
    summary = dict(seed=seed,smoke=args.smoke,train_events=len(ytrain),validation_events=len(y),
                   train_groups=len(np.unique(train_groups)),validation_groups=len(np.unique(val_groups)),
                   calibration_test_challenge_evaluated=False,train_prior_weights=weights_report,
                   wall_s=time.perf_counter()-started,cpu_s=time.process_time()-cpu_start,
                   peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                   baseline=baseline,study=study,xgboost_version=xgb.__version__)
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ['baseline','study']}),flush=True)


if __name__ == '__main__':
    main()
