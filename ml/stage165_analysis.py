"""All predeclared source partitions, fixed predictions and original 500 draws."""
import csv
import json
import multiprocessing as mp
import resource
import time

import numpy as np
from stage119_reportcurve import ci
from stage165_common import ROOT, OUT, inputs, load, masks, protocol, table

G = None


def task(spec):
    role, group_name = spec
    d, pred, groups = G
    ix = np.flatnonzero(d['role'] == role)
    draw = load('ntuples/energy_ml_stage131/bootstrap_draws.npz')[f'role{role}']
    assert draw.shape == (500, len(ix))
    layers = masks({k: v[ix] for k, v in d.items()})
    rows, supports = [], []
    for layer in protocol()['strata']:
        use = groups[group_name][ix] & layers[layer]
        indices = ix[use]; w = d['weight'][indices]
        support = dict(role=role, group=group_name, stratum=layer, N=len(indices),
            ESS=float(w.sum() ** 2 / (w @ w)) if len(w) else None,
            weight_sum=float(w.sum()), source_N=len(np.unique(d['source'][indices])))
        supports.append(support)
        if not len(indices):
            for a, b in protocol()['comparisons']:
                rows.append(dict(**support, candidate=a, reference=b, RMSE_ratio=None, low95=None, high95=None,
                    valid_draws=0, **{s + k: None for s in ['total', 'positive', 'negative']
                                     for k in ['_tail_delta_pp', '_tail_low95_pp', '_tail_high95_pp']}))
            continue
        names = ['AZH', 'AZ', 'H', 'A']
        err = np.column_stack([pred[n][indices] - np.log(d['truth_E_GeV'][indices]) for n in names])
        rel = np.expm1(err); weighted = draw[:, use] * w
        den = weighted.sum(axis=1); sq = weighted @ (err ** 2)
        central = np.average(err ** 2, weights=w, axis=0)
        flags = dict(total=abs(rel) > .5, positive=rel > .5, negative=rel < -.5)
        for a, b in protocol()['comparisons']:
            j, k = names.index(a), names.index(b)
            good = (den > 0) & (sq[:, k] > 0)
            lo, hi = ci(np.sqrt(sq[good, j] / sq[good, k]))
            r = dict(**support, candidate=a, reference=b,
                RMSE_ratio=float(np.sqrt(central[j] / central[k])) if central[k] > 0 else None,
                low95=lo, high95=hi, valid_draws=int(good.sum()))
            for sign, flag in flags.items():
                delta = flag[:, j].astype(float) - flag[:, k].astype(float)
                lo, hi = ci(100 * (weighted[good] @ delta) / den[good])
                r.update({sign + '_tail_delta_pp': 100 * float(np.average(delta, weights=w)),
                          sign + '_tail_low95_pp': lo, sign + '_tail_high95_pp': hi})
            rows.append(r)
    return rows, supports


def main():
    global G
    cpu, tick = time.process_time(), time.perf_counter()
    G = inputs(); d, pred, groups = G
    assert not (OUT / 'analysis_lock.json').exists()
    (OUT / 'analysis_lock.json').write_text(json.dumps(dict(energy_fits=0, model_forward=0, fixed_groups=list(groups))) + '\n')
    table('source_mapping.tsv', [dict(source=int(i), component=str(d['component'][d['source'] == i][0]),
        N=int((d['source'] == i).sum()), nominal=bool(groups['flux_context:nominal'][d['source'] == i][0]))
        for i in np.unique(d['source'])])
    with mp.get_context('fork').Pool(4) as pool:
        results = pool.map(task, [(r, g) for r in [2, 3] for g in groups])
    rows = [r for batch, _ in results for r in batch]
    support = [r for _, batch in results for r in batch]
    assert len(rows) == 216 and len(support) == 72
    prior = list(csv.DictReader((ROOT / 'workbook/stage164_energy_ml/paired.tsv').open(), delimiter='\t'))
    max_difference = 0.; checks = 0
    for r in rows:
        if r['group'] != 'inclusive':
            continue
        old = next(v for v in prior if (int(v['role']), v['stratum'], v['candidate'], v['reference']) ==
                   (r['role'], r['stratum'], r['candidate'], r['reference']))
        for k in ['RMSE_ratio', 'low95', 'high95'] + [s + t for s in ['total', 'positive', 'negative'] for t in ['_tail_delta_pp', '_tail_low95_pp', '_tail_high95_pp']]:
            assert r[k] is not None and old[k] != 'NA'
            error = abs(r[k] - float(old[k])); assert error < 1e-12, (k, error)
            max_difference = max(max_difference, error); checks += 1
    table('paired.tsv', rows); table('support.tsv', support)
    result = dict(passed=True, N=3002, roles=[1708, 653, 641], mapped_source_N=len(np.unique(d['source'])),
        source_component_exact=True, inclusive_scalars_checked=checks, inclusive_max_abs_difference=max_difference,
        comparison_rows=len(rows), support_rows=len(support), empty_cells=sum(r['N'] == 0 for r in support),
        missing_intervals=sum(r['high95'] is None for r in rows), energy_fits=0, model_forward=0,
        promotion=False, overall_complete=False, reserved_forward=0, CPU_parent_s=time.process_time() - cpu,
        wall_s=time.perf_counter() - tick, RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        scope='fixed-policy descriptive source marginals, not calibrated flux nuisance or causal material effects')
    (OUT / 'analysis_summary.json').write_text(json.dumps(result, indent=2) + '\n'); print(result)


if __name__ == '__main__':
    main()
