"""Stage71 fixed F7 augmentation: common contracts, metrics and compact I/O."""
import csv
import json
import resource
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
OUT = REPO/'workbook/stage71_energy_ml'
ART = REPO/'ml/artifacts/stage71'
CACHE = REPO/'ntuples/energy_ml_stage71'
LOW = ['E50_100', 'E100_200']
COST = dict(all=1.01, E200_inf=1.03, pz50_100=1.03, high_y=1.03, unconfirmed=1.03)
TAILS = ['tail50', 'positive_tail50', 'negative_tail50', 'tail100', 'positive_tail100', 'negative_tail100']


def begin():
    return time.perf_counter(), time.process_time()


def resources(start):
    return dict(wall_s=time.perf_counter()-start[0], CPU_s=time.process_time()-start[1],
                peak_RSS_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n')


def table(path, rows):
    with path.open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter='\t', lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def arrays(path):
    with np.load(path) as z:
        return {k:z[k] for k in z.files}


def masks(d):
    e, p = d['truth_E_GeV'], d['pz']
    result = dict(all=np.ones(len(e), bool), E50_100=(e>=50)&(e<100), E100_200=(e>=100)&(e<200),
                  E200_inf=e>=200, pz50_100=(p>=50)&(p<100), pz100_250=(p>=100)&(p<250),
                  high_y=d['y_lepton']>=.8, unconfirmed=~d['confirmed'], input_missing=d['missing'])
    for lo, hi in zip([50,75,100,150,200,400,800,1600,3200], [75,100,150,200,400,800,1600,3200,6400]):
        result[f'E{lo}_{hi}'] = (e>=lo)&(e<hi)
    result['E6400_inf'] = e>=6400
    return result


def indicator(error, key):
    r = np.expm1(error)
    threshold = .5 if '50' in key else 1.
    return r>threshold if key.startswith('positive') else r< -threshold if key.startswith('negative') else abs(r)>threshold


def metrics(y, pred):
    names = ['log_RMSE','mean_bias_pct','median_bias_pct','R68_pct']
    names += [tail+suffix for tail in TAILS for suffix in ['_pct','_loss_fraction']]
    if not len(y):
        return dict.fromkeys(names, '未测量')
    err = pred-y
    relative = np.expm1(err)
    q = np.quantile(relative, [.16,.5,.84])
    loss = err**2
    result = dict(log_RMSE=float(np.sqrt(loss.mean())), mean_bias_pct=float(100*relative.mean()),
                  median_bias_pct=float(100*q[1]), R68_pct=float(50*(q[2]-q[0])))
    for tail in TAILS:
        use = indicator(err, tail)
        result[tail+'_pct'] = float(100*use.mean())
        result[tail+'_loss_fraction'] = float(loss[use].sum()/loss.sum()) if loss.sum() else 0.
    return result


def boot_weights(d, seed, repeats):
    groups, gid = np.unique(d['group'], return_inverse=True)
    rng = np.random.default_rng(seed)
    weights = np.zeros((repeats,len(groups)), int)
    for component in ['pi','k','charm']:
        idx = np.flatnonzero(np.char.startswith(groups, component+':'))
        if len(idx):
            weights[:,idx] = rng.multinomial(len(idx), np.full(len(idx),1/len(idx)), size=repeats)
    return groups, gid, weights
