"""Stage76 integrate fixed float32 tree scores at their actual query transitions."""
import json
import numpy as np
import xgboost as xgb
from conditional_decision import (REPO, LOG_EDGES, PZ_EDGES, JOBS, ARMS, QUERY,
    MODEL_ART, model, fixed_indices, query_matrix, proposal, arrays, begin, resources, save, table)
from conditional_hypotheses import proposal_density

OUT = REPO/'workbook/stage76_energy_ml'
ART = REPO/'ml/artifacts/stage76'
CACHE = REPO/'ntuples/energy_ml_stage76'
KEYS = ['raw_log','logZ','low_bin_mass','high_bin_mass','normalization_error']


def serialized(booster):
    return json.loads(booster.save_raw(raw_format='json'))


def partition(booster):
    trees = serialized(booster)['learner']['gradient_booster']['model']['trees']
    query_feature = len(booster.feature_names)-1
    cuts = []
    for tree in trees:
        take = (np.array(tree['left_children'])>=0)&(np.array(tree['split_indices'])==query_feature)
        assert not np.any(np.array(tree['split_type'])[take])
        cuts.extend(np.array(tree['split_conditions'])[take])
    cuts = np.unique(np.array(cuts, dtype='float32'))
    # Real t is cast to float32 before the numerical split input < cut.
    transitions = (cuts.astype(float)+np.nextafter(cuts, np.float32(-np.inf)).astype(float))/2
    transitions = transitions[(transitions>LOG_EDGES[0])&(transitions<LOG_EDGES[-1])]
    edges = np.unique(np.r_[LOG_EDGES, transitions])
    assert np.all(np.diff(edges)>0)
    return edges, cuts


def constant_integral(edges, logits, pz, mass):
    width = np.diff(edges); center = (edges[:-1]+edges[1:])/2
    pb = np.searchsorted(PZ_EDGES, pz, side='right')-1
    eb = np.searchsorted(LOG_EDGES, center, side='right')-1
    q = mass[pb[:, None], eb]/np.diff(LOG_EDGES)[eb]
    with np.errstate(divide='ignore'):
        logmass = logits+np.log(q)+np.log(width)
    shift = logmass.max(1)
    assert np.isfinite(shift).all()
    unnormalized = np.exp(logmass-shift[:, None])
    z = unnormalized.sum(1); weight = unnormalized/z[:, None]
    result = dict(raw_log=weight@center, logZ=shift+np.log(z),
        low_bin_mass=weight[:, eb==0].sum(1), high_bin_mass=weight[:, eb==6].sum(1),
        normalization_error=abs(weight.sum(1)-1))
    assert np.isfinite(result['raw_log']).all()
    return result


def scores(booster, x, candidates, arm):
    xx = query_matrix(np.repeat(x, len(candidates), axis=0), np.tile(candidates, len(x)), arm)
    return booster.inplace_predict(xx, predict_type='margin').reshape(len(x), -1).astype(float)


def predict_exact(booster, x, pz, mass, arm, chunk=64, budget=None):
    """Deployment uses only reco and fixed candidates, never true-energy labels."""
    edges, _ = partition(booster); center = (edges[:-1]+edges[1:])/2
    result = {key: [] for key in KEYS}
    for start in range(0, len(x), chunk):
        if budget is not None: budget()
        stop = min(start+chunk, len(x))
        value = constant_integral(edges, scores(booster,x[start:stop],center,arm), pz[start:stop], mass)
        for key in KEYS: result[key].append(value[key])
    return {key: np.concatenate(value) for key,value in result.items()}


def traverse(raw, x):
    """Independent serialized numeric-tree traversal, float32 accumulation."""
    param = raw['learner']['learner_model_param']
    assert float(param['base_score'])==.5
    output = np.zeros(len(x), dtype='float32')  # logit(.5)=0
    rows = np.arange(len(x))
    for tree in raw['learner']['gradient_booster']['model']['trees']:
        left = np.array(tree['left_children']); right = np.array(tree['right_children'])
        feature = np.array(tree['split_indices']); cut = np.array(tree['split_conditions'],dtype='float32')
        default = np.array(tree['default_left'],dtype=bool); node = np.zeros(len(x),int)
        for _ in range(int(tree['tree_param']['num_nodes'])):
            active = left[node]>=0
            if not active.any(): break
            ii=rows[active]; nn=node[active]; value=x[ii,feature[nn]]
            goleft=np.where(np.isnan(value),default[nn],value<cut[nn])
            node[ii]=np.where(goleft,left[nn],right[nn])
        assert np.all(left[node]<0)
        output += cut[node]
    return output
