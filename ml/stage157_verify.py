"""Batch-only scalar reconstruction and Cholesky validation of heldout counts."""
import json
import math
from pathlib import Path

import numpy as np


def run(native, pairs):
    out = Path('workbook/stage157_energy_ml')
    models = json.loads((out/'models.json').read_text())
    summary = json.loads((out/'response_summary.json').read_text())
    names = ['VetoNu0', 'VetoNu1', 'Veto10', 'Veto20', 'Veto21',
             'Timing0', 'Timing1', 'Timing2', 'Timing3', 'Preshower0', 'Preshower1']
    names += [f'Calo{i}' for i in range(4)]
    comparisons = []
    for policy, model in models.items():
        if not model['supported']:
            continue
        covariance = np.asarray(model['covariance'])
        cholesky = np.linalg.cholesky(covariance)
        observed = {g: dict(original_heldout_N=0, scored_N=0, alerts=0,
                           missing_N=0, outside_fit_state_range_N=0)
                    for g in ['all', 'overflow', 'high_activity', 'pz50_100']}
        calibration_scores = []
        max_quadratic_delta = 0.
        for record, pair in zip(native, pairs):
            if not pair['new_selected']:
                continue
            state = record['tracks'][pair['leading_index']]['state']
            pz = state[5]/1000
            point = np.array([math.log(pz), state[0], state[1],
                              state[3]/state[5], state[4]/state[5]])
            waves = {w['name']: w for w in pair['readout']}
            charge = [waves[n]['raw_charge_pC'] for n in names]
            valid = all(q is not None and math.isfinite(q) and q not in [-999., -9999., -99999.]
                        for q in charge)
            y = [math.asinh(q) if q is not None else float('nan') for q in charge]
            if policy == 'Q15G6':
                for station in record['geometry']['stations'][1:]:
                    usable = (station['available'] and station['eligibleWafers'] == station['measuredWafers']
                              and station['onMeasuredWafer'] == station['eligibleCandidates'])
                    valid = valid and usable
                    if usable:
                        count = station['candidate_N']
                        total = count*station['mean_abs_dx_mm'] if count else 0.
                        y.extend([math.asinh(count), math.asinh(total)])
                    else:
                        y.extend([float('nan'), float('nan')])
            valid = valid and all(math.isfinite(v) for v in point) and all(math.isfinite(v) for v in y)
            inside = all(lo <= v <= hi for lo, v, hi in zip(model['state_lo'], point, model['state_hi']))
            score = None
            if valid:
                design = np.r_[1., (point-model['state_mean'])/model['state_scale']]
                residual = np.asarray(y)-design@np.asarray(model['beta'])
                white = np.linalg.solve(cholesky, residual)
                score = float(white@white)
                alternative = float(residual@np.linalg.solve(covariance, residual))
                assert math.isclose(score, alternative, rel_tol=1e-8, abs_tol=1e-8)
                max_quadratic_delta = max(max_quadratic_delta, abs(score-alternative))
            split = record['entry'] % 4
            if split == 2 and valid and inside:
                calibration_scores.append(score)
            if split != 3:
                continue
            groups = dict(all=True, overflow=any(waves[n]['status'] & 4 for n in names),
                          high_activity=valid and sum(charge) > model['high_activity_train_sum_raw_charge99_pC'],
                          pz50_100=50 <= pz < 100)
            # Activity is defined from raw readout, even if geometry is unavailable.
            groups['high_activity'] = (all(q is not None and math.isfinite(q) for q in charge)
                                      and sum(charge) > model['high_activity_train_sum_raw_charge99_pC'])
            for group, belongs in groups.items():
                if not belongs:
                    continue
                row = observed[group]
                row['original_heldout_N'] += 1
                if not valid:
                    row['missing_N'] += 1
                elif not inside:
                    row['outside_fit_state_range_N'] += 1
                else:
                    row['scored_N'] += 1
                    row['alerts'] += score > model['threshold']
        threshold = sorted(calibration_scores)[math.ceil(.95*(len(calibration_scores)+1))-1]
        assert math.isclose(threshold, model['threshold'], rel_tol=1e-10, abs_tol=1e-10)
        for group, measured in observed.items():
            primary = next(r for r in summary['heldout'] if r['policy'] == policy and r['group'] == group)
            assert all(measured[key] == primary[key] for key in measured), (policy, group, measured, primary)
            comparisons.append(dict(policy=policy, group=group, **measured, exact=True))
        comparisons.append(dict(policy=policy, calibration_N=len(calibration_scores),
                                threshold_abs_delta=abs(threshold-model['threshold']),
                                max_Cholesky_vs_linear_solve_delta=max_quadratic_delta))
    result = dict(passed=True, scalar_reconstruction=True, models_refitted=0,
                  checks=comparisons, population_FPR_certified=False)
    (out/'independent_validation.json').write_text(json.dumps(result, indent=2)+'\n')
    return result
