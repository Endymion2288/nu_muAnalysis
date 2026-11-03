"""Stage73 fixed marginal-energy policies and reconstruction evidence contracts."""
import numpy as np
from support_augmentation import REPO, arrays, begin, resources, save, table, masks, metrics, indicator, boot_weights, LOW, COST, TAILS

OUT = REPO/'workbook/stage73_energy_ml'
ART = REPO/'ml/artifacts/stage73'
CACHE = REPO/'ntuples/energy_ml_stage73'
EDGES = np.array([50,100,200,400,800,1600,3200,6400.])
ENERGY = [f'E{int(a)}_{int(b)}' for a,b in zip(EDGES[:-1],EDGES[1:])]
ARMS = dict(U=0., S=.5, F=1.)


def weights(energy, alpha):
    # Explicit under/overflow categories preserve any events outside fixed edges.
    bins = np.searchsorted(EDGES, energy, side='right')
    count = np.bincount(bins, minlength=len(EDGES)+1)
    raw = count[bins].astype(float)**(-alpha)
    return raw/raw.mean(), bins, count


def support(d, m):
    return dict(N=int(m.sum()), groups=len(np.unique(d['group'][m])),
                sources=len(np.unique(d['source'][m])),
                unique_incoming=len(np.unique(d['incoming'][m],axis=0)))


def finite(value):
    if isinstance(value,dict): return {k:finite(v) for k,v in value.items()}
    if isinstance(value,list): return [finite(v) for v in value]
    if isinstance(value,(float,np.floating)) and not np.isfinite(value): return '未测量'
    return value
