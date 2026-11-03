"""Stage75 fixed score-density integration; deployment consumes reco only."""
import json
import numpy as np
import xgboost as xgb
from conditional_hypotheses import (REPO, LOG_EDGES, PZ_EDGES, JOBS, ARMS,
    QUERY, query_matrix, proposal, arrays, begin, resources, save, table)

OUT = REPO/'workbook/stage75_energy_ml'
ART = REPO/'ml/artifacts/stage75'
CACHE = REPO/'ntuples/energy_ml_stage75'
MODEL_ART = REPO/'ml/artifacts/stage74'


def grid(size):
    return np.unique(np.r_[np.linspace(LOG_EDGES[0], LOG_EDGES[-1], size), LOG_EDGES])


def integrate(nodes, logits, pz, mass):
    """Linear exp(score) within intervals; exact zeroth/first moments of that interpolant.

    Each interval uses one original q bin, so discontinuous q is never averaged
    across a boundary. Tree scores at the nodes remain an approximation.
    """
    left, right = nodes[:-1], nodes[1:]
    width = right-left
    eb = np.searchsorted(LOG_EDGES, (left+right)/2, side='right')-1
    pb = np.searchsorted(PZ_EDGES, pz, side='right')-1
    q = mass[pb[:, None], eb]/np.diff(LOG_EDGES)[eb]
    supported = np.zeros_like(logits, dtype=bool)
    supported[:, :-1] |= q>0
    supported[:, 1:] |= q>0
    shift = np.max(np.where(supported, logits, -np.inf), axis=1)
    assert np.isfinite(shift).all()
    # Unsupported nodes need no exponential; no clipping of supported scores.
    value = np.exp(np.where(supported, logits-shift[:, None], -np.inf))
    fl, fr = value[:, :-1], value[:, 1:]
    zseg = q*width*(fl+fr)/2
    first = q*width*((2*left+right)*fl+(left+2*right)*fr)/6
    z = zseg.sum(1)
    mean = first.sum(1)/z
    assert np.all(z>0) and np.isfinite(mean).all()
    return dict(raw_log=mean, logZ=shift+np.log(z),
        low_bin_mass=zseg[:, eb==0].sum(1)/z,
        high_bin_mass=zseg[:, eb==6].sum(1)/z,
        normalization_error=np.abs((zseg/z[:, None]).sum(1)-1))


def model(job, arm, features):
    booster = xgb.Booster(params={'nthread': 1})
    booster.load_model(MODEL_ART/job/(arm+'.ubj'))
    names = ([features[0]] if arm=='M' else features)+[QUERY]
    assert booster.feature_names==names and booster.num_boosted_rounds()==400
    return booster


def predict(booster, x, pz, mass, arm, size=257, chunk=64):
    """No truth arguments; reduce every query chunk and discard its full grid."""
    nodes = grid(size)
    result = {k: [] for k in ['raw_log','logZ','low_bin_mass','high_bin_mass','normalization_error']}
    for start in range(0, len(x), chunk):
        stop = min(start+chunk, len(x))
        xx = query_matrix(np.repeat(x[start:stop], len(nodes), axis=0),
                          np.tile(nodes, stop-start), arm)
        logits = booster.inplace_predict(xx, predict_type='margin').astype(float).reshape(stop-start, -1)
        values = integrate(nodes, logits, pz[start:stop], mass)
        for key in result: result[key].append(values[key])
    return {key: np.concatenate(value) for key,value in result.items()}


def fixed_indices(rows, n):
    order = np.argsort(rows)
    return order[np.linspace(0, len(rows)-1, min(n, len(rows))).astype(int)]
