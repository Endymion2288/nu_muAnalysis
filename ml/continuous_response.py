"""Stage62 fixed smooth joint/product ratio models and explicit log-energy density."""
import json
from pathlib import Path

import numpy as np
import torch
from torch import nn

from audited_features import REPO, configuration, load
from expert_combination import begin, resources, save, subset

OUT = REPO / 'workbook/stage62_energy_ml'
ART = REPO / 'ml/artifacts/stage62'
MODELS = ['A_full_unit', 'B_full_flat', 'C_mu_unit']


def inputs():
    d, s, x = load()
    rows = s['row']
    role = np.full(len(rows), 'unused', dtype='<U6')
    role[d['train_eligible'][rows]] = 'train'
    role[d['cal_eligible'][rows]] = 'cal'
    role[d['partition'][rows] == 'validation'] = 'eval'
    use = role != 'unused'
    selected = rows[use]
    out = {k: d[k][selected] for k in ['truth_E_GeV', 'y_lepton', 'confirmed', 'source', 'group', 'component']}
    out.update(row=selected, role=role[use], x=x[use], pz=d['reco_pz_GeV'][selected],
               missing=np.isnan(x[use]).any(axis=1))
    assert [int((out['role'] == r).sum()) for r in ['train', 'cal', 'eval']] == [41447, 8440, 14057]
    return out


def raw_transform(x, state):
    a = np.asarray(x, float).copy()
    for j, kind in enumerate(state['kind']):
        if kind == 'log':
            a[:, j] = np.log(a[:, j])
        elif kind == 'log1p':
            a[:, j] = np.log1p(a[:, j])
        else:
            a[:, j] = np.arcsinh(a[:, j] / state['signed_scale'][j])
    return a


def transform_state(x):
    cfg = configuration()
    kind = []
    for name in cfg['features']:
        domain = cfg['rules'][name]['domain']
        kind.append('log' if domain == 'positive' else 'log1p' if domain in ['count', 'nonnegative'] else 'asinh')
    scales = np.nanmedian(abs(x.astype(float)), axis=0)
    scales = np.where(np.isfinite(scales) & (scales > 0), scales, 1.)
    state = dict(features=cfg['features'], kind=kind, signed_scale=scales.tolist())
    a = raw_transform(x, state)
    center = np.nanmedian(a, axis=0)
    center = np.where(np.isfinite(center), center, 0.)
    spread = np.nanquantile(a, .75, axis=0) - np.nanquantile(a, .25, axis=0)
    spread = np.where(np.isfinite(spread) & (spread > 1e-8), spread, 1.)
    state.update(center=center.tolist(), scale=spread.tolist(), pz_index=cfg['features'].index('ML_mu_pz0_GeV'))
    return state


def transform(x, state, mu_only=False):
    a = raw_transform(x, state)
    missing = ~np.isfinite(a)
    center, scale = np.asarray(state['center']), np.asarray(state['scale'])
    a = np.where(missing, center, a)
    logpz = a[:, state['pz_index']].copy()
    a = (a - center) / scale
    if mu_only:
        j = state['pz_index']
        a = a[:, j:j+1]
        missing = missing[:, j:j+1]
    return np.column_stack([a, missing]).astype('float32'), logpz


def pair_indices(n, weights, seed):
    rng = np.random.default_rng(seed)
    p = weights / weights.sum()
    return rng.choice(n, 2*n, p=p), rng.choice(n, 2*n, p=p)


def pair_matrix(x, logpz, t, ix, it, p):
    u = (t[it] - logpz[ix] - p['u_center']) / p['u_scale']
    return np.column_stack([x[ix], u]).astype('float32')


def network(dim):
    return nn.Sequential(nn.Linear(dim, 64), nn.SiLU(), nn.Linear(64, 64), nn.SiLU(), nn.Linear(64, 1))


def training_weights(t, p, flat):
    edges = np.asarray(p['flat_log_edges'])
    index = np.minimum(np.searchsorted(edges, t, side='right')-1, len(edges)-2)
    assert (index >= 0).all() and (t <= edges[-1]).all()
    counts = np.bincount(index, minlength=len(edges)-1)
    w = len(t) / (np.count_nonzero(counts)*counts[index]) if flat else np.ones(len(t))
    return w, index


def scan(model, x, logpz, p, event_batch=None):
    """Only transformed readouts and hypothetical t enter deployment inference."""
    grid = np.asarray(p['scan_log_grid'])
    batch = event_batch or p['inference_event_batch']
    result = []
    model.eval()
    with torch.inference_mode():
        for start in range(0, len(x), batch):
            a, lp = x[start:start+batch], logpz[start:start+batch]
            v = np.repeat(a, len(grid), axis=0)
            u = ((grid[None, :] - lp[:, None] - p['u_center']) / p['u_scale']).reshape(-1, 1)
            arg = torch.from_numpy(np.column_stack([v, u]).astype('float32'))
            result.append(model(arg).numpy().reshape(len(a), len(grid)))
    return np.concatenate(result)


def density(logits, p, truth=None, flat_prior=False):
    """Linear likelihood interpolation times exact piecewise-constant logE prior.

    Split integration at scan nodes AND prior discontinuities. The density is
    linear on each interval, so mass, moments, CDF and CRPS integrate exactly.
    This is a declared finite-grid density, not an exact continuous neural ratio.
    """
    grid = np.asarray(p['scan_log_grid'])
    edges = np.asarray(p['prior_log_edges'])
    knots = np.unique(np.r_[grid, edges])
    h = np.diff(knots)
    mids = .5*(knots[:-1]+knots[1:])
    prior = np.ones(len(h))/(grid[-1]-grid[0]) if flat_prior else np.asarray(p['prior_log_density'])[np.clip(np.searchsorted(edges, mids)-1, 0, len(edges)-2)]
    # Subtract an event constant before exponentiation; it cancels in q.
    likelihood = np.exp(np.asarray(logits, float)-np.max(logits, axis=1)[:, None])
    j = np.clip(np.searchsorted(grid, knots, side='right')-1, 0, len(grid)-2)
    f = (knots-grid[j])/(grid[j+1]-grid[j])
    interp = likelihood[:, j]*(1-f)+likelihood[:, j+1]*f
    left, right = interp[:, :-1]*prior, interp[:, 1:]*prior
    mass = .5*(left+right)*h
    z = mass.sum(axis=1)
    left, right, mass = left/z[:, None], right/z[:, None], mass/z[:, None]
    slope = (right-left)/h
    cdf = np.c_[np.zeros(len(logits)), np.cumsum(mass, axis=1)]
    mean = np.sum(knots[:-1]*mass + left*h*h/2 + slope*h**3/3, axis=1)

    def cdf_at(t):
        t = np.broadcast_to(t, (len(logits),))
        k = np.clip(np.searchsorted(knots, t, side='right')-1, 0, len(h)-1)
        dx = np.clip(t-knots[k], 0, h[k]); rows = np.arange(len(logits))
        return cdf[rows, k]+left[rows, k]*dx+.5*slope[rows, k]*dx*dx

    probabilities = np.column_stack([cdf_at(t) for t in edges])
    quantiles = []
    for prob in p['quantiles']:
        k = np.minimum((cdf <= prob).sum(axis=1)-1, len(h)-1)
        rr = np.arange(len(logits)); target = prob-cdf[rr, k]
        q0, b = left[rr, k], slope[rr, k]
        root = np.sqrt(np.maximum(0, q0*q0+2*b*target))
        dx = np.divide(2*target, q0+root, out=np.zeros_like(target), where=(q0+root)>0)
        quantiles.append(knots[k]+np.clip(dx, 0, h[k]))
    modes = np.isclose(logits, np.max(logits, axis=1)[:, None], rtol=0, atol=p['mode_logit_tolerance'])
    local = (logits[:, 1:-1] > logits[:, :-2]) & (logits[:, 1:-1] > logits[:, 2:])
    summary = dict(point_raw_log=mean, probabilities=probabilities, quantiles=np.column_stack(quantiles),
                   normalization_error=abs(mass.sum(axis=1)-1),
                   mle_low_log=np.min(np.where(modes, grid, np.inf), axis=1),
                   mle_high_log=np.max(np.where(modes, grid, -np.inf), axis=1),
                   mle_boundary=modes[:, 0] | modes[:, -1], local_peak_count=local.sum(axis=1),
                   endpoint_mass=np.c_[mass[:, :1].sum(axis=1), mass[:, -1:].sum(axis=1)])
    if truth is not None:
        y = np.asarray(truth)
        rows = np.arange(len(y))
        inside = (y >= grid[0]) & (y <= grid[-1])
        k = np.clip(np.searchsorted(knots, y, side='right')-1, 0, len(h)-1)
        dx = np.clip(y-knots[k], 0, h[k])
        pdf = left[rows, k]+slope[rows, k]*dx
        summary['log_density'] = np.where(inside, np.log(np.maximum(pdf, np.finfo(float).tiny)), -np.inf)
        summary['pit'] = cdf_at(y)
        c0 = cdf[:, :-1]
        int_f2 = c0*c0*h+c0*left*h*h+(left*left+c0*slope)*h**3/3+left*slope*h**4/4+slope*slope*h**5/20
        int_f = c0*h+left*h*h/2+slope*h**3/6
        partial = c0[rows, k]*dx+left[rows, k]*dx*dx/2+slope[rows, k]*dx**3/6
        suffix = np.cumsum(int_f[:, ::-1], axis=1)[:, ::-1][rows, k]-partial
        clipped = np.clip(y, grid[0], grid[-1])
        summary['crps_logE'] = int_f2.sum(axis=1)-2*suffix+grid[-1]-clipped+abs(y-clipped)
        summary['outside_support'] = ~inside
    return summary


def summarize_scan(model, x, logpz, p, truth=None):
    """Keep only summaries; never retain the full event-by-energy grid."""
    chunks = {}
    for start in range(0, len(x), p['inference_event_batch']):
        end = start+p['inference_event_batch']
        logits = scan(model, x[start:end], logpz[start:end], p)
        unit = density(logits, p, None if truth is None else truth[start:end])
        flat = density(logits, p, None if truth is None else truth[start:end], True)
        unit.update(flat_point_raw_log=flat['point_raw_log'], flat_log_density=flat.get('log_density'),
                    flat_crps_logE=flat.get('crps_logE'), flat_probabilities=flat['probabilities'])
        for key, value in unit.items():
            if value is not None:
                chunks.setdefault(key, []).append(value)
    return {key: np.concatenate(value) for key, value in chunks.items()}
