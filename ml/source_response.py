"""Run-mixture counterfactual and finite-pool source-label controls for stage26."""
from pathlib import Path

import numpy as np
import yaml

from closure import load_data
from profile_response import Response, config as parent_config

CASES = ['raw', 'run_bin_matched']
NULLS = ['event_stratified', 'group_component']
ALPHAS = [-1., 0., 1.]


def config(repo):
    return {**parent_config(repo), **yaml.safe_load((repo / 'ml/configs/source_response.yaml').read_text())}


def load_events(repo, cfg, model, smoke=False):
    y, bins, gi, groups, fold, predictions = load_data(repo, cfg, model, False)
    with np.load(repo / 'ntuples/energy_ml_stage12/dataset/validation.npz') as saved:
        run = saved['run'].copy()
    runs, ri = np.unique(run, return_inverse=True)
    original = fold[gi] == 'A'
    keep = np.ones(len(y), dtype=bool)
    if smoke:
        keep[:] = False
        rng = np.random.default_rng(cfg['seed'] + 26)
        for r in range(len(runs)):
            for b in range(6):
                for side in [False, True]:
                    indices = np.flatnonzero((ri == r) & (bins == b) & (original == side))
                    keep[rng.choice(indices, size=min(25, len(indices)), replace=False)] = True
    return y[keep], bins[keep], gi[keep], groups, fold, predictions[:, keep], runs, ri[keep]


def event_basis(y, bins, ri, scores, nruns, cfg):
    center = np.sqrt(np.array(cfg['truth_edges_GeV'][:-1]) * cfg['truth_edges_GeV'][1:])
    loge = np.log(y / center[bins])
    reco = np.searchsorted(cfg['energy_reco_internal_GeV'], scores, side='right')
    index = (ri * 6 + bins) * 10 + reco
    powers = [np.ones(len(y))]
    for k in range(1, cfg['moment_order'] + 1): powers.append(powers[-1] * loge / k)
    return np.stack(powers), index, loge, reco


def aggregate(basis, index, weights, nruns):
    return np.stack([np.bincount(index, weights=p * weights, minlength=nruns * 60).reshape(nruns, 6, 10) for p in basis])


class MatchedResponse:
    """Fixed pooled run proportions, with each run/bin response normalized."""
    def __init__(self, coefficients, target):
        total = coefficients[0].sum(axis=-1)
        if np.any((target > 0) & (total <= 0)): raise ValueError('missing_run_bin')
        self.coefficients = coefficients
        self.derivatives = np.arange(1, len(coefficients))[:, None, None, None] * coefficients[1:]
        self.target = target
        self.cache = {}

    def at(self, alpha):
        alpha = float(alpha)
        if alpha in self.cache: return self.cache[alpha]
        h = np.polynomial.polynomial.polyval(alpha, self.coefficients)
        dh = np.polynomial.polynomial.polyval(alpha, self.derivatives)
        assert h.min() >= -1e-12
        total = h.sum(axis=-1); active = self.target > 0
        ratio = np.divide(h, total[..., None], out=np.zeros_like(h), where=active[..., None])
        dr = np.divide(dh, total[..., None], out=np.zeros_like(dh), where=active[..., None])
        slope = np.divide(dh.sum(axis=-1), total, out=np.zeros_like(total), where=active)
        dr -= ratio * slope[..., None]
        result = np.einsum('rb,rbj->jb', self.target, ratio), np.einsum('rb,rbj->jb', self.target, dr)
        if alpha in [-3., -1., 0., 1., 3.]: self.cache[alpha] = result
        return result


def make_response(coefficients, target, case):
    if case == 0: return Response(coefficients.sum(axis=1))
    return MatchedResponse(coefficients, target)


def target_mix(pool):
    counts = pool[0].sum(axis=-1)
    return counts / counts.sum(axis=0)[None, :]


def random_partition(ni, trial, ri, bins, gi, groups, fold, cfg):
    rng = np.random.default_rng(np.random.SeedSequence([cfg['seed'], 26, ni, trial]))
    original = fold[gi] == 'A'
    if ni == 0:
        result = np.zeros(len(bins), dtype=bool)
        for r in range(int(ri.max()) + 1):
            for b in range(6):
                indices = np.flatnonzero((ri == r) & (bins == b))
                count = int(np.sum(original[indices]))
                result[rng.permutation(indices)[:count]] = True
        return result
    chosen = np.zeros(len(groups), dtype=bool)
    components = np.array([g.split(':')[0] for g in groups])
    for c in sorted(set(components)):
        indices = np.flatnonzero(components == c)
        count = int(np.sum(fold[indices] == 'A'))
        chosen[rng.permutation(indices)[:count]] = True
    return chosen[gi]


def counts_from_uniform(probability, uniforms):
    cdf = np.cumsum(probability); cdf[-1] = 1.
    return np.bincount(np.searchsorted(cdf, uniforms, side='right'), minlength=10)


def direct_check(coeff, target, y, bins, ri, reco, loge, mask, nruns):
    response = MatchedResponse(coeff, target); max_r, max_dr = 0., 0.
    for alpha in np.linspace(-3., 3., 13):
        index = (ri * 6 + bins) * 10 + reco
        weight = mask * np.exp(alpha * loge)
        h = np.bincount(index, weights=weight, minlength=nruns * 60).reshape(nruns, 6, 10)
        dh = np.bincount(index, weights=weight * loge, minlength=nruns * 60).reshape(nruns, 6, 10)
        active = target > 0; total = h.sum(axis=-1)
        r = np.divide(h, total[..., None], out=np.zeros_like(h), where=active[..., None])
        dr = np.divide(dh, total[..., None], out=np.zeros_like(dh), where=active[..., None])
        dr -= r * np.divide(dh.sum(axis=-1), total, out=np.zeros_like(total), where=active)[..., None]
        exact = np.einsum('rb,rbj->jb', target, r)
        exact_dr = np.einsum('rb,rbj->jb', target, dr)
        value, slope = response.at(alpha)
        max_r = max(max_r, float(abs(value - exact).max()))
        max_dr = max(max_dr, float(abs(slope - exact_dr).max()))
    assert max_r < 1e-12 and max_dr < 1e-12
    step = 1e-5
    difference = (response.at(.37 + step)[0] - response.at(.37 - step)[0]) / (2 * step)
    derivative_difference = float(abs(difference - response.at(.37)[1]).max())
    assert derivative_difference < 1e-9
    return dict(response_difference=max_r, direct_derivative_difference=max_dr,
                finite_difference_derivative_error=derivative_difference)
