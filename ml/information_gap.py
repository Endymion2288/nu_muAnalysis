"""Stage30 inputs and train-only probability mappings (no deployment truth)."""
import csv
import json
from pathlib import Path

import numpy as np
from scipy.optimize import minimize
from scipy.special import softmax
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import SplineTransformer, StandardScaler
import yaml

from train_bdt import check_features, load


def configuration(repo):
    return yaml.safe_load((repo / 'ml/configs/information_gap.yaml').read_text())


def training_summary(folder):
    saved = json.loads((folder / 'summary.json').read_text())
    if 'shared_training_file' in saved:
        shared = json.loads((folder / saved['shared_training_file']).read_text())
        return dict(shared, **saved)
    return saved


def inputs(repo):
    base = yaml.safe_load((repo / 'ml/configs/baseline.yaml').read_text())
    truth_cfg = yaml.safe_load((repo / 'ml/configs/physics_decomposition.yaml').read_text())
    rows = list(csv.DictReader((repo / 'ml/configs/files.tsv').open(), delimiter='\t'))
    names = sum([base['feature_groups'][g] for g in base['feature_versions']['F5']], [])
    check_features(names, sum(base['feature_groups'].values(), []))
    sets = []
    for partition in ['train', 'validation']:
        data, groups = load(rows, base, partition)
        with np.load(repo / f'ntuples/energy_ml_stage15/{partition}_truth.npz') as z:
            assert json.loads(str(z['config_json'])) == truth_cfg
            truth = {k: z[k] for k in ['run', 'eventID', 'primary_valid', 'primary_p_GeV',
                     'vertex_x_mm', 'vertex_y_mm', 'vertex_z_mm', 'y_lepton',
                     'truth_E_GeV', 'lead_primary_parent_confirmed']}
        for k in ['run', 'eventID']:
            np.testing.assert_array_equal(data[k], truth[k])
        np.testing.assert_array_equal(data[base['target']], truth['truth_E_GeV'])
        assert len(set(zip(data['run'], data['eventID']))) == len(groups)
        oracle = {k: truth[k] for k in ['vertex_x_mm', 'vertex_y_mm', 'vertex_z_mm']}
        oracle['primary_log_p_GeV'] = np.log(truth['primary_p_GeV'])
        support = truth['primary_valid'] & np.isfinite(np.column_stack(list(oracle.values()))).all(1)
        # Stop rather than silently changing the common event population.
        assert support.all() and (truth['primary_p_GeV'] > 0).all()
        x = np.column_stack([data[k] for k in names]).astype('float32')
        x[~np.isfinite(x)] = np.nan
        sets.append(dict(x=x, y=truth['truth_E_GeV'], groups=groups, truth=truth,
                         oracle=oracle, p=data['ML_mu_p_GeV']))
    assert not set(sets[0]['groups']) & set(sets[1]['groups'])
    return base, names, sets


def split_groups(groups, cfg):
    rng = np.random.default_rng(cfg['split_seed'])
    assignment = {}
    for component in ['charm', 'k', 'pi']:
        unique = np.unique(groups[np.char.startswith(groups, component + ':')])
        order = rng.permutation(unique)
        nm = int(np.ceil(.2 * len(order))); ns = int(np.ceil(.1 * len(order)))
        assignment.update({g: 'map' if i < nm else 'stop' if i < nm + ns else 'fit'
                           for i, g in enumerate(order)})
    return np.array([assignment[g] for g in groups]), assignment


def class_index(y, cfg):
    b = np.searchsorted(cfg['energy_edges_GeV'], y, side='right') - 1
    assert ((b >= 0) & (b < 6)).all()
    return b


def calibrate(q, labels, prior, weights=None):
    """Temperature and five independent intercepts, fitted on independent predictions."""
    logits = np.log(np.maximum(q, 1e-12))
    if weights is None:
        weights = prior[labels] / (np.bincount(labels, minlength=6) / len(labels))[labels]
    weights = weights / weights.sum()
    def objective(v):
        scale = np.exp(v[0]); bias = np.r_[v[1:], 0.]
        z = logits * scale + bias
        p = softmax(z, axis=1)
        value = -np.sum(weights * np.log(np.maximum(p[np.arange(len(p)), labels], 1e-15)))
        d = p.copy(); d[np.arange(len(p)), labels] -= 1; d *= weights[:, None]
        grad = np.r_[np.sum(d * logits) * scale, d.sum(0)[:5]]
        return value, grad
    fit = minimize(objective, np.zeros(6), jac=True, method='L-BFGS-B',
                   bounds=[(-2, 2)] + [(-8, 8)] * 5, options={'maxiter': 200, 'ftol': 1e-11})
    assert fit.success
    state = dict(scale=float(np.exp(fit.x[0])), bias=np.r_[fit.x[1:], 0.].tolist(),
                 success=bool(fit.success), iterations=int(fit.nit), loss=float(fit.fun))
    return state


def calibrated(q, state):
    return softmax(np.log(np.maximum(q, 1e-12)) * state['scale'] + state['bias'], axis=1)


def scalar_mapping(xt, labels, xv, prior):
    weights = prior[labels] / (np.bincount(labels, minlength=6) / len(labels))[labels]
    pipe = make_pipeline(SplineTransformer(n_knots=8, degree=3, knots='quantile'),
                         StandardScaler(), LogisticRegression(C=1., max_iter=1000, solver='lbfgs'))
    pipe.fit(np.asarray(xt).reshape(len(xt), -1), labels, logisticregression__sample_weight=weights)
    assert pipe[-1].n_iter_.max() < 1000
    return pipe.predict_proba(np.asarray(xv).reshape(len(xv), -1)), int(pipe[-1].n_iter_.max())


def ten_bin_mapping(scalar, labels, evaluation, prior, edges):
    j = np.searchsorted(np.log(edges), scalar)
    hist = np.zeros((10, 6)); np.add.at(hist, (j, labels), 1)
    hist *= prior / (np.bincount(labels, minlength=6) / len(labels))
    populated = hist.sum(1) > 0
    posterior = np.tile(prior, (10, 1))
    posterior[populated] = hist[populated] / hist[populated].sum(1)[:, None]
    evaluation_bin = np.searchsorted(np.log(edges), evaluation)
    return posterior[evaluation_bin], int((~populated[evaluation_bin]).sum())
