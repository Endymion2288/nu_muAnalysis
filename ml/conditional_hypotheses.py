"""Stage74 known conditional proposals and paired hypothesis discrimination."""
import numpy as np
from support_augmentation import REPO, arrays, begin, resources, save, table, masks, boot_weights
from energy_reweight import support, finite

OUT = REPO/'workbook/stage74_energy_ml'
ART = REPO/'ml/artifacts/stage74'
CACHE = REPO/'ntuples/energy_ml_stage74'
E_EDGES = np.array([50.,100,200,400,800,1600,3200,6400])
PZ_EDGES = np.array([50.,75,100,150,250,500,1000,np.inf])
LOG_EDGES = np.log(E_EDGES)
JOBS = ['fold0','fold1','fold2','final']
ARMS = ['M','X']
CRITICAL = ['E50_100','E100_200','pz50_100_E50_100','pz50_100_E100_200',
            'pz50_100_E200_inf','high_y','unconfirmed']
QUERY = 'hypothesis_logE_GeV'


def bins(pz, energy):
    pb = np.searchsorted(PZ_EDGES,pz,side='right')-1
    eb = np.searchsorted(E_EDGES,energy,side='right')-1
    return pb, eb


def proposal(pz, energy):
    pb, eb = bins(pz,energy)
    assert np.all((pb>=0)&(pb<7)) and np.all((eb>=0)&(eb<7))
    counts = np.zeros((7,7),int)
    np.add.at(counts,(pb,eb),1)
    totals = counts.sum(1)
    mass = np.divide(counts,totals[:,None],out=np.zeros((7,7)),where=totals[:,None]>0)
    return counts, mass


def proposal_density(pz, log_energy, mass):
    pb = np.searchsorted(PZ_EDGES,pz,side='right')-1
    eb = np.searchsorted(LOG_EDGES,log_energy,side='right')-1
    density = np.zeros(len(pz))
    valid = (pb>=0)&(pb<7)&(eb>=0)&(eb<7)
    density[valid] = mass[pb[valid],eb[valid]]/np.diff(LOG_EDGES)[eb[valid]]
    return density


def draw(pz, mass, rng):
    pb = np.searchsorted(PZ_EDGES,pz,side='right')-1
    assert np.all((pb>=0)&(pb<7))
    assert np.allclose(mass[pb].sum(1),1), 'no proposal for an occupied reco-pz slice'
    cdf = np.cumsum(mass[pb],axis=1);cdf[:,-1]=1.
    eb = (rng.random(len(pz))[:,None]>=cdf).sum(1)
    result = LOG_EDGES[eb]+rng.random(len(pz))*np.diff(LOG_EDGES)[eb]
    assert np.all(proposal_density(pz,result,mass)>0)
    return result


def query_matrix(x, log_energy, arm):
    """A candidate query is explicit; this function cannot read any truth labels."""
    reco = x[:,:1] if arm=='M' else x
    return np.column_stack([reco,log_energy]).astype('float32')


def paired_matrix(x, true_log_energy, negative_log_energy, arm):
    queries = np.column_stack([true_log_energy,negative_log_energy]).ravel()
    return query_matrix(np.repeat(x,2,axis=0),queries,arm), np.tile([1.,0.],len(x)).astype('float32')


def losses(logits):
    # Each physical X carries its positive and synthetic negative together.
    positive = np.logaddexp(0.,-logits[:,0])
    negative = np.logaddexp(0.,logits[:,1])
    probability = np.exp(-np.logaddexp(0.,-logits))
    brier = np.mean((probability-np.array([1.,0.]))**2,axis=1)
    return dict(BCE=.5*(positive+negative),positive_BCE=positive,negative_BCE=negative,
                Brier=brier,probability=probability)


def strata(d, timing_quartiles):
    result = masks(d)
    p,e = d['pz'],d['truth_E_GeV']
    result.update(pz50_75=(p>=50)&(p<75),pz75_100=(p>=75)&(p<100))
    for label in ['E50_100','E100_200','E200_inf']:
        result['pz50_100_'+label]=result['pz50_100']&result[label]
    # Original stage73 train thresholds are diagnostics only, never proposal input.
    timing=np.sum(d['x'][:,29:33],axis=1)
    cell=np.full(len(p),-1,int);low=result['pz50_100'];good=low&np.isfinite(timing)
    cell[good]=4*(p[good]>=75)+np.searchsorted(timing_quartiles,timing[good],side='right')
    cell[low&~np.isfinite(timing)]=8
    for c in range(9):
        result[f'activity_cell{c}']=cell==c
        for label in ['E50_100','E100_200','E200_inf']:
            result[f'activity_cell{c}_{label}']=(cell==c)&result[label]
    return result
