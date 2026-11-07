"""Conditional paired quantity/flux comparisons, original gates, sealed reserve."""
import json
from pathlib import Path

import numpy as np

from stage119_curve_common import LAYERS, masks
from stage119_reportcurve import ci, metrics
from stage130_prepare import load, table

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'workbook/stage130_energy_ml'
ART = ROOT / 'ml/artifacts/stage130'
ARMS = ['N0', 'N2', 'augmented']


def evaluate(side, d, baseline):
    policies = {}
    suffix = '_new' if side == 'new' else ''
    for arm in ARMS:
        policies[arm] = load(ART / f'quantity_{arm}{suffix}_prediction.npz')['cal']
    active = (d['role'] > 0) & (d['role'] < 4)
    traditional = np.full(len(active), np.nan)
    traditional[active] = np.log(d['pz'][active] / .8)
    policies.update(direct_cal=baseline, traditional=traditional)
    for prediction in policies.values():
        assert np.isnan(prediction[~active]).all()
    np.savez_compressed(ART / f'{side}_evaluation_predictions.npz', **policies)
    names = list(policies)
    contrasts = [('N2', 'N0'), ('augmented', 'N0'), ('augmented', 'N2')]
    contrasts += [(arm, ref) for arm in ARMS for ref in ['direct_cal', 'traditional']]
    points, pairs, support, gates = [], [], [], []
    for role in [2, 3]:
        ix = np.flatnonzero(d['role'] == role)
        if not len(ix):
            continue
        sd = {k: v[ix] for k, v in d.items() if isinstance(v, np.ndarray) and len(v) == len(active)}
        family = sd['incoming'] if side == 'old' else sd['incoming'].astype('float32')
        _, first, gid, counts = np.unique(family, axis=0,
            return_index=True, return_inverse=True, return_counts=True)
        w = 1 / counts[gid]
        rng = np.random.default_rng(20261107300 + role + (10 if side == 'new' else 0))
        draw = np.zeros((500, len(first)), 'int16')
        for component in sorted(set(sd['component'][first])):
            use = np.flatnonzero(sd['component'][first] == component)
            draw[:, use] = rng.multinomial(len(use), np.full(len(use), 1/len(use)), size=500)
        layers = masks(sd)
        layers.update(E1600_3200=(sd['truth_E_GeV'] >= 1600) & (sd['truth_E_GeV'] < 3200),
                      E3200_6400=(sd['truth_E_GeV'] >= 3200) & (sd['truth_E_GeV'] < 6400))
        for layer, mask in layers.items():
            rows, weight, group = ix[mask], w[mask], gid[mask]
            if not len(rows):
                continue
            base = dict(side=side, role=role, stratum=layer, N=len(rows),
                        incoming=len(np.unique(group)), ESS=float(weight.sum()**2/(weight@weight)))
            support.append(base)
            error = np.column_stack([policies[name][rows] - np.log(d['truth_E_GeV'][rows]) for name in names])
            assert np.isfinite(error).all()
            aggregate = np.zeros((len(first), len(names)))
            np.add.at(aggregate, group, weight[:, None] * error**2)
            squared = draw @ aggregate
            denominator = draw @ np.bincount(group, weights=weight, minlength=len(first))
            valid = denominator > 0
            for j, name in enumerate(names):
                lo, hi = ci(np.sqrt(squared[valid, j] / denominator[valid]))
                points.append(dict(**base, model=name, **metrics(error[:, j], weight), RMSE_low95=lo, RMSE_high95=hi))
            relative = np.expm1(error)
            tails = {}
            for sign, flag in [('total', abs(relative) > .5), ('positive', relative > .5), ('negative', relative < -.5)]:
                aggregate_tail = np.zeros_like(aggregate)
                np.add.at(aggregate_tail, group, weight[:, None] * flag)
                tails[sign] = aggregate_tail.sum(0)/weight.sum(), draw @ aggregate_tail
            for candidate, reference in contrasts:
                j, k = names.index(candidate), names.index(reference)
                good = valid & (squared[:, k] > 0)
                lo, hi = ci(np.sqrt(squared[good, j] / squared[good, k]))
                pair = dict(**base, candidate=candidate, reference=reference,
                    RMSE_ratio=float(np.sqrt(aggregate[:, j].sum()/aggregate[:, k].sum())), low95=lo, high95=hi)
                for sign, (central, bootstrap) in tails.items():
                    lo, hi = ci(100*(bootstrap[good, j]-bootstrap[good, k])/denominator[good])
                    pair.update({sign+'_tail_delta_pp':float(100*(central[j]-central[k])),
                                 sign+'_tail_low95_pp':lo, sign+'_tail_high95_pp':hi})
                pairs.append(pair)
        for arm in ARMS:
            for layer in LAYERS:
                ref = 'traditional' if layer in LAYERS[:2] else 'direct_cal'
                limit = 1.05 if ref == 'traditional' else 1.01 if layer == 'all' else 1.03
                row = next((r for r in pairs if r['role'] == role and r['stratum'] == layer and
                            r['candidate'] == arm and r['reference'] == ref), None)
                tail = next((r for r in pairs if r['role'] == role and r['stratum'] == layer and
                             r['candidate'] == arm and r['reference'] == 'direct_cal'), None)
                gates.append(dict(side=side, role=role, arm=arm, stratum=layer,
                    RMSE_upper95=row['high95'] if row else None, limit=limit,
                    RMSE_pass=bool(row and row['high95'] is not None and row['high95'] <= limit),
                    tail_pass=bool(tail and all(tail[s+'_tail_high95_pp'] is not None and
                                              tail[s+'_tail_high95_pp'] <= 2 for s in ['total', 'positive', 'negative']))))
    for label, rows in [('metrics', points), ('paired', pairs), ('support', support), ('gates', gates)]:
        table(f'{side}_{label}.tsv', rows)
    return {f'{side}_{role}_{arm}':sum(g['role'] == role and g['arm'] == arm for g in gates) == len(LAYERS)
            and all(g['RMSE_pass'] and g['tail_pass'] for g in gates
            if g['role'] == role and g['arm'] == arm) for role in [2, 3] for arm in ARMS}


def main():
    old = load('ntuples/energy_ml_stage119/old_input.npz')
    new = load('ntuples/energy_ml_stage130/new_input.npz')
    cached = load('ml/artifacts/stage87/predictions.npz')
    reference = np.full(len(old['role']), np.nan)
    reference[cached['row']] = cached['direct_cal']
    summary = evaluate('old', old, reference)
    summary.update(evaluate('new', new, load(ART / 'reference_new.npz')['cal']))
    (OUT / 'energy_summary.json').write_text(json.dumps(dict(joint=summary, reserve_predictions=0,
        original_roles_unchanged=True, original_reference_exact=True,
        inference='fixed incoming/component conditional bootstrap; not GENIE/source/refit/system confidence or independent confirmation'), indent=2)+'\n')
    print(summary, flush=True)


if __name__ == '__main__':
    main()
