"""Independent finite-MC ensembles on a fixed empirical joint population."""
import numpy as np
import yaml

from profile_response import Response, config as parent_config

LAYERS = ['oracle', 'source_mc', 'mean_mc', 'both_mc']


def config(repo):
    return {**parent_config(repo), **yaml.safe_load((repo / 'ml/configs/independent_response.yaml').read_text())}


def basis(y, bins, scores, cfg):
    centers = np.sqrt(np.array(cfg['truth_edges_GeV'][:-1]) * cfg['truth_edges_GeV'][1:])
    logs = np.log(y / centers[bins])
    reco = np.searchsorted(cfg['energy_reco_internal_GeV'], scores, side='right')
    powers = [np.ones(len(y))]
    for k in range(1, cfg['moment_order'] + 1): powers.append(powers[-1] * logs / k)
    return np.stack(powers), bins * 10 + reco, logs, reco


def aggregate(powers, index, weights):
    return np.stack([np.bincount(index, weights=p * weights, minlength=60).reshape(6, 10) for p in powers])


def sample_weights(bins, sizes, side, trial, cfg):
    rng = np.random.default_rng(np.random.SeedSequence([cfg['seed'], 27, 0, side, trial]))
    weights = np.zeros(len(bins), dtype=np.int32)
    for b, n in enumerate(sizes):
        indices = np.flatnonzero(bins == b)
        selected = rng.choice(indices, size=int(n), replace=True)
        weights += np.bincount(selected, minlength=len(bins)).astype(np.int32)
    return weights


def count_uniforms(seed, ai, trial, cfg):
    rng = np.random.default_rng(np.random.SeedSequence([cfg['seed'], 27, 1, seed, ai, trial]))
    return rng.random(cfg['benchmark_selected_events'])


def local_covariance(response, fractions, alpha, bins, reco, logs, sizes, cfg):
    """Truth-point first-order covariance, with normalized importance weights.

    theta=(f0,...,f4,alpha); f5=1-sum(f0,...,f4).
    Source and independent empirical-mean errors have opposite influence signs,
    hence equal covariance for equal MC sizes. This is an oracle diagnostic.
    """
    r, dr = response.at(alpha)
    p = r @ fractions
    tangent = np.vstack([np.eye(5), -np.ones(5)])
    mapping = np.zeros((7, 6)); mapping[:6, :5] = tangent; mapping[6, 5] = 1
    design = np.column_stack([r @ tangent, dr @ fractions])
    positive = p > 0
    information = (design[positive].T / p[positive]) @ design[positive]
    influence = np.linalg.solve(information, design[positive].T / p[positive])
    count_cov = (np.diag(p) - np.outer(p, p)) / cfg['benchmark_selected_events']
    mc_cov = np.zeros((10, 10))
    for b in range(6):
        mask = bins == b
        weight = np.exp(alpha * logs[mask]); weight /= weight.mean()
        centered = np.eye(10)[reco[mask]] - r[:, b]
        z = weight[:, None] * centered
        mc_cov += fractions[b] ** 2 * (z.T @ z) / (len(z) * sizes[b])
    count_theta = influence @ count_cov[np.ix_(positive, positive)] @ influence.T
    mc_theta = influence @ mc_cov[np.ix_(positive, positive)] @ influence.T
    count_full = mapping @ count_theta @ mapping.T
    mc_full = mapping @ mc_theta @ mapping.T
    return np.stack([count_full, mc_full, mc_full]), dict(condition=float(np.linalg.cond(information)),
                                                       probability_mc_covariance=mc_cov.tolist())


def population_checks(response, bins, reco, logs):
    max_r = 0.; max_dr = 0.
    index = bins * 10 + reco
    for alpha in np.linspace(-3, 3, 13):
        weights = np.exp(alpha * logs)
        h = np.bincount(index, weights=weights, minlength=60).reshape(6, 10)
        dh = np.bincount(index, weights=weights * logs, minlength=60).reshape(6, 10)
        total = h.sum(axis=1)
        r = (h / total[:, None]).T
        dr = (dh / total[:, None]).T - r * (dh.sum(axis=1) / total)[None, :]
        actual, slope = response.at(alpha)
        max_r = max(max_r, float(abs(actual - r).max()))
        max_dr = max(max_dr, float(abs(slope - dr).max()))
    assert max_r < 1e-12 and max_dr < 1e-12
    return dict(maximum_direct_response_error=max_r, maximum_direct_derivative_error=max_dr)
