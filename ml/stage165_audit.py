"""Independent scalar and explicit-row resampling for every source cell."""
import csv
import json
import math

import numpy as np
from stage165_common import ROOT, OUT, inputs, load, masks, protocol, table


def main():
    d, pred, groups = inputs()
    rows = list(csv.DictReader((OUT / 'paired.tsv').open(), delimiter='\t'))
    draws = load('ntuples/energy_ml_stage131/bootstrap_draws.npz')
    assert len(rows) == 216
    manifest = json.loads((ROOT / 'workbook/stage130_energy_ml/source_protocol.json').read_text())['sources']
    source_rows = list(csv.DictReader((OUT / 'source_mapping.tsv').open(), delimiter='\t'))
    for r in source_rows:
        original = next(s for s in manifest if s['index'] == int(r['source']))
        assert original['component'] == r['component']
        assert original['nominal'] == (r['nominal'] == 'True')
        assert int(r['N']) == int((d['source'] == int(r['source'])).sum())
    records = []; maximum = 0.; scalars = 0; missing = 0
    for r in rows:
        role = int(r['role']); ix = np.flatnonzero(d['role'] == role)
        layer = masks({k: v[ix] for k, v in d.items()})[r['stratum']]
        use = layer & groups[r['group']][ix]; indices = ix[use]
        assert len(indices) == int(r['N'])
        if not len(indices):
            assert int(r['valid_draws']) == 0
            assert all(r[k] == 'NA' for k in ['RMSE_ratio', 'low95', 'high95', 'ESS'])
            missing += 1; continue
        w = d['weight'][indices]; a = pred[r['candidate']][indices] - np.log(d['truth_E_GeV'][indices])
        b = pred[r['reference']][indices] - np.log(d['truth_E_GeV'][indices])
        ra, rb = np.expm1(a), np.expm1(b)
        values = dict(RMSE_ratio=math.sqrt(math.fsum(float(v * e * e) for v, e in zip(w, a)) /
                                        math.fsum(float(v * e * e) for v, e in zip(w, b))))
        flags = dict(total=(abs(ra) > .5, abs(rb) > .5), positive=(ra > .5, rb > .5), negative=(ra < -.5, rb < -.5))
        for sign, (fa, fb) in flags.items():
            values[sign + '_tail_delta_pp'] = 100 * math.fsum(float(v) * (int(x) - int(y)) for v, x, y in zip(w, fa, fb)) / math.fsum(map(float, w))
        boot = []; tails = {s: [] for s in flags}
        for counts in draws[f'role{role}'][:, use]:
            pos = np.repeat(np.arange(len(indices)), counts)
            if not len(pos):
                continue
            ww = w[pos]; den = np.average(b[pos] ** 2, weights=ww)
            if den <= 0:
                continue
            boot.append(math.sqrt(np.average(a[pos] ** 2, weights=ww) / den))
            for sign, (fa, fb) in flags.items():
                tails[sign].append(100 * np.average(fa[pos].astype(float) - fb[pos].astype(float), weights=ww))
        assert len(boot) == int(r['valid_draws'])
        if len(boot) >= 475:
            values.update(zip(['low95', 'high95'], np.quantile(boot, [.025, .975])))
            for sign, v in tails.items():
                values.update(zip([sign + '_tail_low95_pp', sign + '_tail_high95_pp'], np.quantile(v, [.025, .975])))
        else:
            assert r['low95'] == r['high95'] == 'NA'
            for sign in flags:
                assert r[sign + '_tail_low95_pp'] == r[sign + '_tail_high95_pp'] == 'NA'
            missing += 1
        error = max(abs(v - float(r[k])) for k, v in values.items())
        assert error < 1e-10, (r['group'], r['stratum'], error)
        maximum = max(maximum, error); scalars += len(values)
        records.append(dict(role=role, group=r['group'], stratum=r['stratum'], candidate=r['candidate'], reference=r['reference'],
            N=len(indices), independent_scalars=len(values), valid_draws=len(boot), max_abs_difference=error))
    table('independent_validation.tsv', records)
    report = dict(passed=True, independent_scalars=scalars, max_abs_difference=maximum,
        total_predeclared_cells=len(rows), missing_intervals_checked=missing, source_mapping_rows=len(source_rows),
        fixed_predictions_only=True, energy_fits=0, model_forward=0, reserved_forward=0,
        scope='independent fsum and explicit resampled rows; source marginals do not certify generator-family independence or calibrated nuisance')
    (OUT / 'independent_validation.json').write_text(json.dumps(report, indent=2) + '\n'); print(report)


if __name__ == '__main__':
    main()
