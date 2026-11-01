#!/usr/bin/env python3
"""Diagnose saved integrals and paired signal residuals without refitting events."""
import csv
import json
import math
import resource
import time
from pathlib import Path

import numpy as np
from scipy.integrate import quad, trapezoid

from report_calonu_native import table


def stable_shape(x, peak, mean, width, alpha, power):
    z = (x-mean)/width
    if alpha < 0:
        z = -z
    a = abs(alpha)
    if z > -a:
        return peak*math.exp(-.5*z*z)
    return peak*math.exp(-.5*a*a-power*math.log1p((-a-z)*a/power))


def main():
    tick, cpu = time.perf_counter(), time.process_time()
    repo = Path(__file__).resolve().parents[1]
    out = repo/'workbook/stage37_energy_ml'
    cfg = json.loads((repo/'ml/configs/calonu_native_control.json').read_text())
    with np.load(repo/'ntuples/energy_ml_stage37/native_response.npz') as z:
        d = {k: z[k] for k in z.files}
    cases = json.loads(str(d['cases_json']))
    # Only saved parameters: this makes no new waveform or ML fits.
    rows = []
    for j, case in enumerate(cases):
        for i in range(4):
            if np.isfinite(d['integral'][j, i]):
                continue
            pars = [float(d[k][j, i]) for k in ['peak', 'mean', 'width', 'alpha', 'nval']]
            peak, mean, width, alpha, power = pars
            lo, hi = d['saved_time'][j, i, [0, -1]]
            split = mean-alpha*width
            integral, error = quad(stable_shape, lo, hi, args=tuple(pars),
                                   points=[split] if lo < split < hi else None,
                                   epsabs=1e-9, epsrel=1e-10, limit=200)
            fine_x = np.linspace(lo, hi, 30001)
            trap = trapezoid([stable_shape(x, *pars) for x in fine_x], fine_x)
            assert np.isfinite(integral) and integral > 0
            np.testing.assert_allclose(integral, trap, rtol=1e-6, atol=1e-8)
            log_a = power*math.log(power/abs(alpha))-.5*alpha*alpha
            rows.append(dict(group=case['group'], input_entry=case['input_entry'], branch=i,
                             saved_status=int(d['status'][j, i]), saved_integral_mVns=d['integral'][j, i],
                             peak_mV=peak, mean_ns=mean, width_ns=width, alpha=alpha, power=power,
                             log_ROOT_analytic_A=log_a, log_max_float64=math.log(np.finfo(float).max),
                             analytic_A_overflows=log_a > math.log(np.finfo(float).max),
                             stable_integral_mVns=integral, quadrature_error_mVns=error,
                             fine_trapezoid_mVns=trap, stable_integral_pC=integral/50))
    table(out/'nonfinite_integral_diagnosis.tsv', rows)
    regular = np.array([r['role'] == 'regular' for r in cases])
    groups = np.array([r['group'] for r in cases])
    gid = np.searchsorted(cfg['groups'], groups)
    rng = np.random.default_rng(cfg['bootstrap_seed'])
    draws = np.zeros((cfg['bootstrap_replicates'], 4), int)
    for cols in [[0, 1], [2, 3]]:
        draws[:, cols] = rng.multinomial(2, [.5, .5], size=len(draws))
    residuals = []
    for subset, mask in [('regular', regular),
                         ('regular_p100_250', regular & (np.array([r['reco_p_GeV'] for r in cases]) < 250)),
                         ('regular_p250_1000', regular & (np.array([r['reco_p_GeV'] for r in cases]) >= 250))]:
        observed = np.array([r['signed_known_total_pC'] for r in cases])[mask]
        signal = np.array([r['predicted_signal_total_pC'] for r in cases])[mask]
        delta = observed-signal
        boots = np.array([np.average(delta, weights=w[gid[mask]]) for w in draws])
        residuals.append(dict(subset=subset, N=int(mask.sum()), mean_observed_pC=observed.mean(),
                              mean_predicted_pC=signal.mean(), mean_residual_pC=delta.mean(),
                              mean_residual_lo_pC=np.quantile(boots, .025), mean_residual_hi_pC=np.quantile(boots, .975),
                              residual_std_pC=delta.std(ddof=1),
                              ideal_independent_ADC_noise_std_pC=3*(2/16.384)*2/50*math.sqrt(4*76),
                              predicted_peak_below_5sigma=int(sum(r['predicted_peak_sigma'] < 5 for r, use in zip(cases, mask) if use)),
                              all_four_saved_threshold_failed=int(((d['status'] & 1).all(axis=1) & mask).sum())))
    table(out/'paired_signal_residual.tsv', residuals)
    # Trigger patterns were already saved in stage36; no ROOT reread or new selection.
    with np.load(repo/'ntuples/energy_ml_stage36/data.npz') as z:
        data = {k: z[k] for k in z.files}
    selected = data['run'] == 15838
    patterns = sorted(set(zip(data['TBP'][selected].tolist(), data['TAP'][selected].tolist())))
    trigger = []
    for group in [12, 13]:
        mask = data['group_index'] == group
        for pattern in [None]+patterns:
            use = mask if pattern is None else mask & (data['TBP'] == pattern[0]) & (data['TAP'] == pattern[1])
            if not use.any():
                continue
            x = data['CaloNu_total_E_EM'][use].astype(float)/1000
            trigger.append(dict(group=group, TBP='all' if pattern is None else pattern[0],
                                TAP='all' if pattern is None else pattern[1], N=int(use.sum()),
                                fraction_of_file=use.sum()/mask.sum(), finite_total=int(np.isfinite(x).sum()),
                                median_total_GeV_EM=np.median(x[np.isfinite(x)]),
                                median_reco_p_GeV=np.median(data['Track_p0'][use].astype(float))/1000))
    table(out/'data15838_trigger_patterns.tsv', trigger)
    conditions = json.loads((out/'conditions_audit.json').read_text())
    calibration = []
    for sample in ['MC', 'data']:
        with np.load(repo/f'ntuples/energy_ml_stage36/{sample}.npz') as z:
            for run in np.unique(z['run']):
                payload = next(r['rows'] for r in conditions['records']
                               if r['label'] == f'{sample}{run}' and r['folder'] == '/WAVE/Calibration/MIP_ref')
                payload = sorted(payload, key=lambda r: r['channel'])
                for i, row in enumerate(payload):
                    q, nmip = z[f'CaloNu{i}_charge'], z[f'CaloNu{i}_nMIP']
                    use = (z['run'] == run) & np.isfinite(q) & np.isfinite(nmip) & (nmip != 0)
                    observed = q[use].astype(float)
                    mip = nmip[use].astype(float)
                    ratio = observed/mip
                    ref = row['payload']['charge_ref']
                    # Keep subnormal float32 fits: a ratio of two values near 1e-45 loses precision.
                    subnormal = (abs(observed) < np.finfo(np.float32).tiny) | (abs(mip) < np.finfo(np.float32).tiny)
                    np.testing.assert_allclose(observed, mip*ref, rtol=3e-6,
                                               atol=2*float(np.finfo(np.float32).smallest_subnormal)*(1+ref))
                    calibration.append(dict(sample=sample, run=int(run), branch=i, hardware_channel=row['channel'],
                                            N=int(use.sum()), reference_charge_pC_per_MIP=ref,
                                            observed_charge_per_MIP_median=float(np.median(ratio)),
                                            subnormal_float32_pairs=int(subnormal.sum()),
                                            max_relative_difference=float(np.max(abs(ratio/ref-1))),
                                            max_normal_relative_difference=float(np.max(abs(ratio[~subnormal]/ref-1))),
                                            forward_relation_passed=True))
    table(out/'calibration_constant_checks.tsv', calibration)
    summary = dict(nonfinite_modules=len(rows), all_saved_unflagged=all(r['saved_status'] & 48 == 0 for r in rows),
                   all_analytic_A_overflow=all(r['analytic_A_overflows'] for r in rows),
                   all_stable_integrals_finite_positive=True, fine_quadrature_crosscheck=True,
                   ROOT_source='https://github.com/root-project/root/blob/v6-28-12/math/mathcore/src/ProbFuncMathCore.cxx',
                   no_output_corrections=True, waveform_refits=0, ML_fits=0,
                   wall_s=time.perf_counter()-tick, cpu_s=time.process_time()-cpu,
                   peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    (out/'diagnosis_summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
