"""One frozen signed charge-composition package, retaining the original X62."""
import json
from pathlib import Path

import numpy as np
import stage129_energy as energy

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage189_energy_ml'
CACHE = ROOT/'ntuples/energy_ml_stage189'
ART = ROOT/'ml/artifacts/stage189'
energy.OUT, energy.ART = OUT, ART
load, table = energy.load, energy.table


def write(name, data):
    (OUT/name).write_text(json.dumps(data, indent=2, allow_nan=False)+'\n')


def inputs(save=False):
    p = json.loads((OUT/'protocol.json').read_text())
    d = load(ROOT/'ntuples/energy_ml_stage119/old_input.npz')
    names = energy.configuration()['features']
    active = d['role']>0
    # No new content is constructed for quarantine or reserved.
    content = np.full((len(active),4), np.nan, dtype='float32')
    for j, pair in enumerate(p['pairs']):
        a,b = [names.index(n) for n in pair]
        content[active,j] = (np.arcsinh(d['x'][active,a].astype(float)/p['Q0_pC'])
                             - np.arcsinh(d['x'][active,b].astype(float)/p['Q0_pC'])).astype('float32')
    available = np.isfinite(content).astype('float32')
    arrays = dict(X=d['x'], A=np.column_stack([d['x'], available]).astype('float32'))
    arrays['C'] = np.column_stack([arrays['A'],content]).astype('float32')
    # Preserve joint composition distribution within predeclared observable conditions.
    raw_indices = [names.index(n) for n in p['conditioning_charge_columns']]
    total = np.sum(d['x'][:,raw_indices].astype(float),axis=1)
    scale = np.arcsinh(total/p['Q0_pC'])
    pzbin = np.digitize(d['pz'],p['pz_condition_edges_GeV'])
    qbin = np.digitize(np.where(np.isfinite(scale),scale,np.inf),p['asinh_charge_condition_edges'])
    patterns = available.astype(int)@np.array([1,2,4,8])
    keys = [(int(d['role'][i]),str(d['component'][i]),int(pzbin[i]),int(qbin[i]),int(patterns[i])) for i in np.flatnonzero(active)]
    buckets = {}
    for i,key in zip(np.flatnonzero(active),keys):
        buckets.setdefault(key,[]).append(i)
    rng = np.random.default_rng(p['shuffle_seed'])
    permutation = np.arange(len(active))
    for key in sorted(buckets):
        ix = np.asarray(buckets[key]); permutation[ix] = rng.permutation(ix)
    shuffled = content[permutation]
    np.testing.assert_array_equal(np.isfinite(content),np.isfinite(shuffled))
    arrays['S'] = np.column_stack([arrays['A'],shuffled]).astype('float32')
    labels = dict(X=names,A=names+[f'composition{j}_available' for j in range(4)])
    labels['C'] = labels['A']+[f'composition{j}_asinh_pC_contrast' for j in range(4)]
    labels['S'] = labels['A']+[f'composition{j}_shuffled_contrast' for j in range(4)]
    if save:
        CACHE.mkdir(exist_ok=True)
        np.savez_compressed(CACHE/'control.npz',content=content,permutation=permutation)
        records=[]
        for role in [1,2,3]:
            ix=d['role']==role
            for j,pair in enumerate(p['pairs']):
                records.append(dict(role=role,contrast=j,pair=' vs '.join(pair),parents_N=int(ix.sum()),
                    available_N=int(np.isfinite(content[ix,j]).sum()),
                    negative_primitive_N=int((d['x'][ix][:,[names.index(n) for n in pair]]<0).sum()),
                    moved_rows_N=int((permutation[ix]!=np.flatnonzero(ix)).sum())))
        table('content_support.tsv',records)
    assert not np.isfinite(content[~active]).any()
    return d,arrays,labels
