"""Nonparametric response-MC bootstrap calibration for profile likelihood."""
import numpy as np
import yaml

from profile_response import Response, config as parent_config


def config(repo):
    return {**parent_config(repo), **yaml.safe_load((repo / 'ml/configs/mc_bootstrap.yaml').read_text())}


def basis(y, bins, scores, cfg):
    centers = np.sqrt(np.array(cfg['truth_edges_GeV'][:-1]) * cfg['truth_edges_GeV'][1:])
    logs = np.log(y / centers[bins]); reco = np.searchsorted(cfg['energy_reco_internal_GeV'], scores, side='right')
    powers=[np.ones(len(y))]
    for k in range(1,cfg['moment_order']+1): powers.append(powers[-1]*logs/k)
    return np.stack(powers), bins*10+reco, logs, reco


def aggregate(powers,index,weights):
    return np.stack([np.bincount(index,weights=p*weights,minlength=60).reshape(6,10) for p in powers])


def source_sample_indices(bins,sizes,trial,cfg,seed):
    rng=np.random.default_rng(np.random.SeedSequence([cfg['seed'],28,0,seed,trial]))
    return [rng.choice(np.flatnonzero(bins==b),size=int(n),replace=True) for b,n in enumerate(sizes)]


def bootstrap_indices(source_indices,trial,replicate,cfg,seed):
    rng=np.random.default_rng(np.random.SeedSequence([cfg['seed'],28,2,seed,trial,replicate]))
    return [rng.choice(indices,size=len(indices),replace=True) for indices in source_indices]


def observed_uniform(seed,trial,cfg):
    return np.random.default_rng(np.random.SeedSequence([cfg['seed'],28,1,seed,trial])).random(cfg['selected_events'])


def pseudo_uniform(seed,trial,replicate,cfg):
    return np.random.default_rng(np.random.SeedSequence([cfg['seed'],28,3,seed,trial,replicate])).random(cfg['selected_events'])


def counts_from_uniform(probability,uniforms):
    cdf=np.cumsum(probability);cdf[-1]=1.
    return np.bincount(np.searchsorted(cdf,uniforms,side='right'),minlength=10)
