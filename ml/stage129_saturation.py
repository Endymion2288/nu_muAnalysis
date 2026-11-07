"""Frozen full-parent saturation ablation; no replacement of original raw charge."""
import json
import multiprocessing as mp
import time

import numpy as np

from audited_features import configuration
from stage129_energy import ROOT, OUT, CACHE, ART, load, table, fit, evaluate


def main():
    tick = time.perf_counter()
    d = load(ROOT/'ntuples/energy_ml_stage119/old_input.npz')
    m = load(CACHE/'measurement.npz')
    policy = json.loads((OUT/'recovery_interval_policy.json').read_text())
    n = len(d['role'])
    valid = np.zeros((n, 12), 'float32')
    value = np.full((n, 15), np.nan, 'float32')
    seen = np.zeros((n, 3), int)
    names, flags = [], []
    channels = [14, 6, 7]
    for j, ch in enumerate(channels):
        valid[:, 4*j] = m['present'][:, j+2]
        valid[:, 4*j+1] = m['present'][:, j+2] & (m['rail_samples']>0)[:, j+2]
        flags += [f'recovery_{ch}_{s}' for s in ['present', 'rail', 'two_edges', 'available']]
        names += [f'recovery_{ch}_{s}' for s in ['Q_pC', 'lower_halfwidth_pC', 'upper_halfwidth_pC', 'rail_samples', 'chi2_ndof']]
    for index in range(20):
        a = load(CACHE/f'recovercov_{index}.npz')
        for j, ch in enumerate(channels):
            use = a['channel'] == ch
            row = a['row'][use]
            assert (m['present'][row, j+2] & (m['rail_samples']>0)[row, j+2]).all()
            seen[row, j] += 1
            available = a['available'][use] & (policy[str(ch)] is not None)
            valid[row, 4*j+2] = a['leading'][use] & a['trailing'][use]
            valid[row, 4*j+3] = available
            value[row, 5*j+3] = a['rail_samples'][use]
            value[row, 5*j+4] = a['chi2_ndof'][use]
            accepted = row[available]
            q = a['Q_pC'][use][available]
            factor = policy[str(ch)] or 1.
            value[accepted, 5*j] = q
            value[accepted, 5*j+1] = factor*(q-a['lower95_pC'][use][available])
            value[accepted, 5*j+2] = factor*(a['upper95_pC'][use][available]-q)
    assert (seen <= 1).all()
    assert np.array_equal(seen.astype(bool), m['present'][:, 2:] & (m['rail_samples']>0)[:, 2:])
    assert not np.isinf(value).any()
    assert not np.isfinite(value[:, [0, 5, 10]][valid[:, [3, 7, 11]] == 0]).any()
    np.savez_compressed(CACHE/'saturation_features.npz', valid=valid, features=value, names=names, flag_names=flags)
    support = []
    for role in [1, 2, 3]:
        for layer, mask in [('all', np.ones(n, bool)), ('E50_100', (d['truth_E_GeV']>=50)&(d['truth_E_GeV']<100)), ('E100_200', (d['truth_E_GeV']>=100)&(d['truth_E_GeV']<200))]:
            for j, ch in enumerate(channels):
                ix = (d['role']==role)&mask
                support.append(dict(role=role, stratum=layer, channel=ch, N=int(ix.sum()), present=int(valid[ix, 4*j].sum()), rail=int(valid[ix, 4*j+1].sum()), two_edges=int(valid[ix, 4*j+2].sum()), available=int(valid[ix, 4*j+3].sum())))
    table('saturation_observable_support.tsv', support)
    np.savez_compressed(ART/'saturation_X_prediction.npz', **load(ART/'depth_X_prediction.npz'))
    base = configuration()['features']
    tasks = [('saturation', 'V', np.column_stack([d['x'], valid]), base+flags, d),
             ('saturation', 'Q', np.column_stack([d['x'], valid, value]), base+flags+names, d)]
    with mp.get_context('fork').Pool(2) as pool:
        fits = pool.map(fit, tasks)
    (OUT/'saturation_fits.json').write_text(json.dumps(fits, indent=2)+'\n')
    evaluate('saturation', d, ['X', 'V', 'Q'])
    (OUT/'saturation_cost.json').write_text(json.dumps(dict(wall_s=time.perf_counter()-tick), indent=2)+'\n')


if __name__ == '__main__':
    main()
