#!/usr/bin/env python3
"""Descriptive noise covariance/stationarity audit; no neutrino labels or fits."""
import json
from pathlib import Path
import numpy as np
from calonu_weak_readout import template_weights
from train_bdt import write_table


def main():
    repo = Path(__file__).resolve().parents[1]; out = repo/'workbook/stage43_energy_ml'
    cfg = json.loads((repo/'ml/configs/calonu_data_noise.json').read_text())['data_noise']
    with np.load(repo/'ntuples/energy_ml_stage43/data_noise.npz') as z: data = {k: z[k] for k in z.files}
    a = data['adc'].astype(float); n = data['residual_mV'].astype(float); centered = n-n.mean(2, keepdims=True)
    condition = json.loads((repo/'workbook/stage37_energy_ml/conditions_audit.json').read_text())
    digi = next(r['rows'][0]['payload'] for r in condition['records'] if r['label'] == 'MC100049' and r['folder'] == '/WAVE/Digitization')
    pars = {k: digi['cb_'+k] for k in ['norm', 'sigma', 'alpha']}; pars.update(mean=820, exponent=digi['cb_n'])
    w, _ = template_weights(np.arange(760, 912, 2.), pars); q = n@w
    records = []; correlations = {}
    for name, mask in [('all', np.ones(len(a), bool))]+[(f'run{r}', data['run'] == r) for r in cfg['runs']]+[(f'fold{f}', data['noise_fold'] == f) for f in range(3)]:
        correlations[name] = dict(events=int(mask.sum()), charge_covariance_pC2=np.cov(q[mask].T).tolist(), charge_correlation=np.corrcoef(q[mask].T).tolist())
        for j in range(4):
            c = centered[mask, j]; r = n[mask, j]; sd = float(np.sqrt(np.mean(c*c)))
            iid_known = sd*float(np.linalg.norm(w)); iid_finite = sd*float(np.sqrt(w@w+w.sum()**2/40))
            item = dict(stratum=name, module=j, N=int(mask.sum()), centered_RMS_mV=sd,
                        finite_pedestal_fixed_RMS_pC=float(np.sqrt(np.mean(q[mask, j]**2))),
                        iid_known_pedestal_expected_SD_pC=iid_known, iid_40_sample_pedestal_expected_SD_pC=iid_finite,
                        block_mean_drift_mV=float(r.mean()), block_mean_RMS_mV=float(np.sqrt(np.mean(r.mean(1)**2))),
                        centered_max_abs_mV=float(abs(c).max()), centered_abs_gt_5RMS_fraction=float(np.mean(abs(c) > 5*sd)))
            for lag in [1, 2, 4, 8, 16]:
                item[f'lag{lag}'] = float(np.sum(c[:, :-lag]*c[:, lag:])/np.sqrt(np.sum(c[:, :-lag]**2)*np.sum(c[:, lag:]**2)))
            records.append(item)
    windows = []
    for lo, hi in [(0, 40), (32, 56), (180, 218), (218, 256)]:
        for run in cfg['runs']:
            for j in range(4):
                wave = a[data['run'] == run, j, lo:hi]; residual = (wave-wave.mean(1, keepdims=True))*cfg['ADC_mV']
                windows.append(dict(run=run, module=j, sample_start=lo, sample_stop_exclusive=hi, events=len(wave),
                                    RMS_mV=float(np.sqrt(np.mean(residual**2))), ADC_mean=float(wave.mean())))
    write_table(out/'noise_statistics.tsv', records); write_table(out/'noise_time_windows.tsv', windows)
    (out/'noise_covariance.json').write_text(json.dumps(dict(groups=correlations, templates_sum_pC_per_mV=float(w.sum()),
                                                          template_norm_pC_per_mV=float(np.linalg.norm(w)),
                                                          iid_pedestal_variance_fraction=float((w.sum()**2/40)/(w@w+w.sum()**2/40)),
                                                          uncertainty='descriptive fixed 504-event library; not independent noise replicas or calibrated signal gain'), indent=2)+'\n')
    print(json.dumps([r for r in records if r['stratum'] == 'all'], indent=2))


if __name__ == '__main__': main()
