"""Independent record-space risk, sealed roles and typed-domain certification."""
import csv
import json
import time

import numpy as np

from audited_features import configuration
from latent_transfer_diagnostics import check_x
from stage119_curve_common import masks
from stage130_prepare import ROOT, OUT, CACHE, load, table

ART = ROOT / 'ml/artifacts/stage130'


def main():
    tick = time.perf_counter()
    old = load('ntuples/energy_ml_stage119/old_input.npz')
    new = load(CACHE / 'new_input.npz')
    assert [(old['role'] == role).sum() for role in range(4)] == [17657, 46575, 11612, 13189]
    names = configuration()['features']
    assert not set(names) & {'ML_mu_p_GeV', 'ML_track_p1_GeV', 'ML_track_pz1_GeV', 'ML_track_log_p1_over_p0'}
    domain_rows = []
    rules = configuration()['rules']
    for side, data in [('old', old), ('new', new)]:
        check_x(data['x'])
        assert np.all(data['pz'] > 50)
        for j, name in enumerate(names):
            values, rule = data['x'][:, j], rules[name]
            finite = np.isfinite(values)
            sentinels = int(np.isin(values, rule.get('sentinels', [])).sum())
            illegal = int((finite & (values <= 0 if rule['domain'] == 'positive' else values < 0)).sum()) if rule['domain'] in ['positive', 'nonnegative', 'count'] else 0
            assert sentinels == illegal == int(np.isinf(values).sum()) == 0
            domain_rows.append(dict(side=side, feature=name, domain=rule['domain'],
                finite_N=int(finite.sum()), NaN_N=int(np.isnan(values).sum()),
                negative_N=int((values < 0).sum()), minus1_N=int((values == -1).sum()),
                finite_sentinel_N=sentinels, domain_violation_N=illegal))
    table('feature_domain_audit.tsv', domain_rows)
    # Role isolation is independently rebuilt from the cached incoming keys.
    keys = new['incoming'].astype('float32')
    role_keys = {role: set(map(tuple, keys[new['role'] == role])) for role in range(1, 5)}
    for a in role_keys:
        for b in role_keys:
            if a < b:
                assert not role_keys[a] & role_keys[b]
    exposed = set()
    for path in json.loads((ROOT / 'workbook/stage119_energy_ml/exposure_inputs.json').read_text()) + ['ntuples/energy_ml_stage119/curve_input.npz']:
        exposed.update(map(tuple, load(path)['incoming'].astype('float32')))
    assert not set.union(*role_keys.values()) & exposed
    members = load(CACHE / 'curve_membership.npz')
    for side, data in [('old', old), ('new', new)]:
        for arm in ['N0', 'N2']:
            assert np.all(data['role'][members[side+'_'+arm]] == 1)
        assert set(members[side+'_N0']) <= set(members[side+'_N2'])
    maximum, scalar_count, rows = 0., 0, []
    for side, data in [('old', old), ('new', new)]:
        policies = load(ART / f'{side}_evaluation_predictions.npz')
        sealed = (data['role'] == 0) | (data['role'] == 4)
        for prediction in policies.values():
            assert np.isnan(prediction[sealed]).all()
        if side == 'old':
            cached = load('ml/artifacts/stage87/predictions.npz')
            np.testing.assert_array_equal(policies['direct_cal'][cached['row']], cached['direct_cal'])
        tab = list(csv.DictReader((OUT / f'{side}_paired.tsv').open(), delimiter='\t'))
        for role in [2, 3]:
            ix = np.flatnonzero(data['role'] == role)
            family = data['incoming'][ix]
            if side == 'new':
                family = family.astype('float32')
            _, first, gid, counts = np.unique(family, axis=0, return_index=True,
                                             return_inverse=True, return_counts=True)
            rng = np.random.default_rng(20261107300 + role + (10 if side == 'new' else 0))
            draws = np.zeros((500, len(first)), 'int16')
            for component in sorted(set(data['component'][ix[first]])):
                groups = np.flatnonzero(data['component'][ix[first]] == component)
                draws[:, groups] = rng.multinomial(len(groups), np.full(len(groups), 1/len(groups)), size=500)
            w = 1/counts[gid]
            sd = {k: v[ix] for k, v in data.items() if isinstance(v, np.ndarray) and len(v) == len(data['role'])}
            layers = masks(sd)
            layers.update(E1600_3200=(sd['truth_E_GeV'] >= 1600) & (sd['truth_E_GeV'] < 3200),
                          E3200_6400=(sd['truth_E_GeV'] >= 3200) & (sd['truth_E_GeV'] < 6400))
            for layer, mask in layers.items():
                relevant = [r for r in tab if int(r['role']) == role and r['stratum'] == layer]
                if not relevant:
                    continue
                # Directly weight every record; no per-family risk aggregation
                # or primary evaluator helper is reused for the arithmetic.
                ww = draws[:, gid[mask]] * w[mask][None, :]
                den = ww.sum(1)
                errors = {name: prediction[ix[mask]] - np.log(data['truth_E_GeV'][ix[mask]])
                          for name, prediction in policies.items()}
                squared = {name: ww @ error**2 for name, error in errors.items()}
                for row in relevant:
                    c, r = row['candidate'], row['reference']
                    ec, er = errors[c], errors[r]
                    good = (den > 0) & (squared[r] > 0)
                    values = dict(RMSE_ratio=float(np.sqrt((w[mask] @ ec**2)/(w[mask] @ er**2))))
                    values.update(zip(['low95', 'high95'], np.quantile(np.sqrt(squared[c][good]/squared[r][good]), [.025, .975])))
                    rc, rr = np.expm1(ec), np.expm1(er)
                    for sign, a, b in [('total', abs(rc) > .5, abs(rr) > .5),
                                       ('positive', rc > .5, rr > .5), ('negative', rc < -.5, rr < -.5)]:
                        delta = a.astype(float) - b.astype(float)
                        values[sign+'_tail_delta_pp'] = 100*(w[mask] @ delta)/w[mask].sum()
                        values.update(zip([sign+'_tail_low95_pp', sign+'_tail_high95_pp'],
                                          np.quantile(100*(ww[good] @ delta)/den[good], [.025, .975])))
                    maximum = max(maximum, max(abs(float(row[k])-v) for k, v in values.items()))
                    scalar_count += len(values)
                rows.append(dict(side=side, role=role, layer=layer, records_N=int(mask.sum()),
                                 incoming_N=len(np.unique(gid[mask]))))
    assert maximum < 1e-10
    table('independent_validation_support.tsv', rows)
    result = dict(paired_scalar_comparisons=scalar_count, max_abs_difference=maximum,
        typed_domains_passed=True, original_roles_preserved=True, old_baseline_exact=True,
        original_quarantine_predictions=0, new_reserve_predictions=0, known_exposure_in_active_new=0,
        nested_training_memberships=True, wall_s=time.perf_counter()-tick,
        scope='same conditional component/incoming draws, independently weighted records; not new blind/source/refit/system confidence')
    (OUT / 'independent_validation.json').write_text(json.dumps(result, indent=2)+'\n')
    print(result, flush=True)


if __name__ == '__main__':
    main()
