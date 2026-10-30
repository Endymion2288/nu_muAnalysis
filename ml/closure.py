"""Small-array conditional spectrum inference; no training or held-out samples."""
import csv
from pathlib import Path

import numpy as np
from scipy.optimize import minimize


SCHEMES = ['energy', 'rank']
DIRECTIONS = ['A_to_B', 'B_to_A']


def read_table(path):
    with Path(path).open() as handle:
        return list(csv.DictReader(handle, delimiter='\t'))


def write_table(path, rows):
    if not rows:
        return
    with Path(path).open('w') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter='\t', lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def fit_shape(response, observed, cfg):
    """Normalized multinomial likelihood on the simplex, without regularization."""
    observed = np.asarray(observed, dtype=float)
    observed = observed / observed.sum()
    if np.any((response.sum(axis=1) == 0) & (observed > 0)):
        return None, dict(status='support', iterations=0, kkt=np.nan)

    def objective(f):
        prob = np.maximum(response @ f, 1e-15)
        return -observed @ np.log(prob), -response.T @ (observed / prob)

    n = response.shape[1]
    result = minimize(objective, np.full(n, 1 / n), jac=True,
                      method=cfg['optimizer']['method'], bounds=[(0, 1)] * n,
                      constraints={'type': 'eq', 'fun': lambda f: f.sum() - 1,
                                   'jac': lambda f: np.ones(n)},
                      options={k: cfg['optimizer'][k] for k in ['ftol', 'maxiter']})
    f = result.x
    grad = objective(f)[1]
    active = f > 1e-7
    lagrange = grad[active].mean()
    kkt = max(np.max(abs(grad[active] - lagrange)),
              np.max(np.maximum(lagrange - grad[~active], 0), initial=0))
    status = 'ok' if result.success and np.all(f >= -1e-10) and abs(f.sum() - 1) < 1e-9 else 'optimizer'
    return (f if status == 'ok' else None), dict(status=status, iterations=int(result.nit), kkt=float(kkt))


def fisher(response, fractions, cfg):
    n = len(fractions)
    tangent = np.vstack([np.eye(n - 1), -np.ones(n - 1)])
    probability = response @ fractions
    positive = probability > 0
    a = response[positive] @ tangent
    information = cfg['benchmark_selected_events'] * (a.T / probability[positive]) @ a
    eigenvalues = np.linalg.eigvalsh(information)
    condition = eigenvalues[-1] / eigenvalues[0] if eigenvalues[0] > 0 else np.inf
    if eigenvalues[0] <= cfg['fisher_relative_eigenvalue_floor'] * eigenvalues[-1]:
        return None, float(condition)
    covariance = tangent @ np.linalg.inv(information) @ tangent.T
    return covariance, float(condition)


def synthetic_checks(cfg):
    rng = np.random.default_rng(271828)
    response = .8 * np.vstack([np.eye(6), np.zeros((4, 6))]) + .2 * rng.uniform(.1, 1, (10, 6))
    response /= response.sum(axis=0)
    fractions = np.array([.05, .12, .3, .28, .18, .07])
    observed = response @ fractions
    fitted, status = fit_shape(response, observed, cfg)
    assert status['status'] == 'ok'
    err = float(np.max(abs(fitted - fractions)))
    assert err < 2e-5
    f = np.full(6, 1 / 6)
    grad = -response.T @ (observed / (response @ f))
    eps = 1e-6
    numeric = np.array([(-observed @ np.log(response @ (f + eps * e)) + observed @ np.log(response @ (f - eps * e))) / (2 * eps) for e in np.eye(6)])
    gradient_error = float(np.max(abs(grad - numeric)))
    assert gradient_error < 1e-8
    cov, condition = fisher(response, fractions, cfg)
    assert np.max(abs(cov.sum(axis=0))) < 1e-12
    unsupported = response.copy(); unsupported[-1] = 0; unsupported /= unsupported.sum(axis=0)
    assert fit_shape(unsupported, np.ones(10), cfg)[1]['status'] == 'support'
    singular = np.tile(response[:, :1], (1, 6))
    assert fisher(singular, fractions, cfg)[0] is None
    return dict(fraction_error=err, gradient_error=gradient_error, condition=condition,
                zero_support_detected=True, nonidentifiability_detected=True)


def load_data(repo, cfg, model, smoke):
    with np.load(repo / 'ntuples/energy_ml_stage12/dataset/validation.npz') as data:
        data = {key: data[key] for key in ['run', 'eventID', 'group', 'ML_truth_E_GeV', 'ML_mu_p_GeV']}
    spec = cfg['models'][model]
    if spec.get('kind') == 'mu':
        predictions = np.array([data['ML_mu_p_GeV'] * spec['scale']])
    else:
        with np.load(repo / spec['path']) as saved:
            for key in ['run', 'eventID', 'group']:
                np.testing.assert_array_equal(data[key], saved[key])
            np.testing.assert_array_equal(data['ML_truth_E_GeV'], saved['truth_E_GeV'])
            predictions = np.stack([saved[f'seed_{s}'] for s in spec['seeds']])
    assert len(data['group']) == 13375
    assert len(set(zip(data['run'], data['eventID']))) == 13375
    groups, group_index = np.unique(data['group'], return_inverse=True)
    folds_table = read_table(repo / 'workbook/stage23_energy_ml/folds.tsv')
    fold_by_group = {row['group']: row['fold'] for row in folds_table}
    assert set(groups) == set(fold_by_group)
    fold = np.array([fold_by_group[g] for g in groups])
    for g, row in zip(groups, sorted(folds_table, key=lambda row: row['group'])):
        assert g == row['group'] and int(row['events']) == (data['group'] == g).sum()
    y = data['ML_truth_E_GeV']
    truth_bin = np.searchsorted(cfg['truth_edges_GeV'], y, side='right') - 1
    assert np.all((truth_bin >= 0) & (truth_bin < 6))
    keep = np.ones(len(y), dtype=bool)
    if smoke:
        keep[:] = False
        smoke_rng = np.random.default_rng(cfg['seed'] + 23)
        for f in ['A', 'B']:
            for b in range(6):
                local = np.flatnonzero((fold[group_index] == f) & (truth_bin == b))
                keep[smoke_rng.choice(local, size=min(150, len(local)), replace=False)] = True
        predictions = predictions[:1]
    assert np.isfinite(predictions).all() and (predictions > 0).all()
    return y[keep], truth_bin[keep], group_index[keep], groups, fold, predictions[:, keep]


def histograms(y, truth_bin, group_index, reco, groups, cfg):
    index = (group_index * 6 + truth_bin) * 10 + reco
    weights = [np.ones(len(y))]
    centers = np.sqrt(np.array(cfg['truth_edges_GeV'][:-1]) * cfg['truth_edges_GeV'][1:])
    for case in cfg['bootstrap_cases'][1:]:
        base = 800 if case.startswith('tilt') else centers[truth_bin]
        weights.append((y / base) ** cfg['tilt_exponents'][case])
    return np.stack([np.bincount(index, weights=w, minlength=len(groups) * 60).reshape(len(groups), 6, 10) for w in weights])


def matrices(hist, case, response_weights, pseudo_weights, cfg):
    # hist axes case, group, truth, reco. Within-bin normalization must be redone
    # after each group resample, otherwise it inadvertently alters binned truth.
    source = np.einsum('g,gbj->bj', response_weights, hist[0])
    base = np.einsum('g,gbj->bj', pseudo_weights, hist[0])
    if case == 'component_matched':
        pseudo = base
    else:
        pseudo = np.einsum('g,gbj->bj', pseudo_weights, hist[cfg['bootstrap_cases'].index(case)])
        if case.startswith('within'):
            denominator = pseudo.sum(axis=1)
            if np.any(denominator == 0):
                return None, None, None, 'empty_truth'
            pseudo *= (base.sum(axis=1) / denominator)[:, None]
    source_total = source.sum(axis=1)
    truth_total = pseudo.sum(axis=1)
    if np.any(source_total == 0) or np.any(truth_total == 0):
        return None, None, None, 'empty_truth'
    return source.T / source_total, truth_total / truth_total.sum(), pseudo.sum(axis=0) / pseudo.sum(), 'ok'


def evaluate(response, truth, observed, cfg):
    fhat, info = fit_shape(response, observed, cfg)
    cov, condition = fisher(response, truth, cfg)
    sigma = np.sqrt(np.diag(cov)) / truth if cov is not None else np.full(6, np.nan)
    bias = fhat / truth - 1 if fhat is not None else np.full(6, np.nan)
    info.update(condition=condition, identifiable=cov is not None,
                rms_bias=float(np.sqrt(np.mean(bias ** 2))),
                rms_sigma=float(np.sqrt(np.mean(sigma ** 2))))
    if fhat is not None:
        p = np.maximum(response @ fhat, 1e-15)
        pos = observed > 0
        info['deviance_N1000'] = float(2 * cfg['benchmark_selected_events'] * np.sum(observed[pos] * np.log(observed[pos] / p[pos])))
        info['boundary'] = int((fhat < 1e-7).sum())
    else:
        info.update(deviance_N1000=np.nan, boundary=-1)
    return fhat, bias, sigma, cov, info
