"""Source-held-out, incoming-purged folds inside the original Stage87 train."""
import json
import sys
import time

import numpy as np

from stage117_common import OUT, cached_inputs, masks, save, table

SEED = 2026110517


def weights(d, ids):
    _, inverse, counts = np.unique(d['key_id'][ids], return_inverse=True, return_counts=True)
    return 1. / counts[inverse]


def purged(d, candidates, validation):
    return candidates[~np.isin(d['key_id'][candidates], d['key_id'][validation])]


def design(d):
    train = np.flatnonzero(d['role'] == 1)
    assignment = {}
    rng = np.random.default_rng(SEED)
    for component in ['charm', 'k', 'pi']:
        groups = np.unique(d['group'][train][d['component'][train] == component])
        assert len(groups) >= 3
        for j, group in enumerate(rng.permutation(groups)):
            assignment[str(group)] = j % 3
    fold = np.full(len(d['row']), -1, np.int8)
    fold[train] = [assignment[str(g)] for g in d['group'][train]]
    pairs = {}
    for j in range(3):
        valid = train[fold[train] == j]
        pairs[f'outer{j}'] = (purged(d, train[fold[train] != j], valid), valid)
    discovery, dev = pairs['outer0']
    for j in [1, 2]:
        valid = discovery[fold[discovery] == j]
        pairs[f'inner{j}'] = (purged(d, discovery[fold[discovery] != j], valid), valid)
    return train, fold, pairs, assignment


def audit(d):
    tick = time.perf_counter()
    train, fold, pairs, assignment = design(d)
    rows = []
    for name, (fit, valid) in pairs.items():
        assert not set(d['key_id'][fit]) & set(d['key_id'][valid])
        assert not set(d['group'][fit]) & set(d['group'][valid])
        assert (d['role'][fit] == 1).all() and (d['role'][valid] == 1).all()
        # Every nested fit excludes both the development source and its incoming.
        if name.startswith('inner'):
            dev = pairs['outer0'][1]
            assert not set(d['key_id'][fit]) & set(d['key_id'][dev])
            assert not set(d['group'][fit]) & set(d['group'][dev])
        for side, ids in [('fit', fit), ('validation', valid)]:
            groups = masks({k: v[ids] for k, v in d.items()})
            w = weights(d, ids)
            for comp in ['all', 'charm', 'k', 'pi']:
                m = np.ones(len(ids), bool) if comp == 'all' else d['component'][ids] == comp
                rows.append(dict(pair=name, side=side, component=comp, N=int(m.sum()),
                    incoming=len(np.unique(d['key_id'][ids[m]])),
                    sources=len(np.unique(d['group'][ids[m]])),
                    low50_100=int((m & groups['E50_100']).sum()),
                    low100_200=int((m & groups['E100_200']).sum()), weight_sum=float(w[m].sum())))
    table('fold_support.tsv', rows)
    table('source_folds.tsv', [dict(group=k, fold=v) for k, v in sorted(assignment.items())])
    checks = [r for r in rows if r['component'] == 'all']
    supported = all(r['low50_100'] >= 30 and r['low100_200'] >= 100 for r in checks)
    supported &= all(r['incoming'] >= 100 and r['sources'] >= 1 for r in rows)
    save('fold_audit.json', dict(passed=bool(supported), train_rows=len(train),
        train_connected_blocks=len(np.unique(d['block'][train])), source_groups=len(assignment),
        source_and_incoming_disjoint_every_pair=True, nested_development_disjoint=True,
        all_original_train_rows_have_outer_validation=True,
        outer_validation_rows=[len(pairs[f'outer{j}'][1]) for j in range(3)],
        outer_fit_rows=[len(pairs[f'outer{j}'][0]) for j in range(3)],
        development_rows=len(pairs['outer0'][1]), discovery_rows=len(pairs['outer0'][0]),
        support_criterion='each pair-side >=30 low50-100, >=100 low100-200; each component >=100 incoming and >=1 source',
        parent_scope='canonical source group plus exact native incoming proxy; no new generator lineage family identity is present',
        target_used_for_assignment=False, weights='recomputed within every fit/evaluation subset, sum1 per incoming',
        CPU_fits=0, wall_s=time.perf_counter()-tick))
    return bool(supported)


if __name__ == '__main__':
    start = time.perf_counter()
    d, x, sub, pw = cached_inputs()
    from stage117_head import qa
    qa(x['B'], d)
    good = audit(d)
    save('probe_resources.json', dict(wall_s=time.perf_counter()-start, no_model_fits=True))
    if not good:
        raise SystemExit('Source/incoming-purged OOF not supported; no row-random fallback')
