#!/usr/bin/env python3
"""Truth-isolated signal visibility by geometry; not a deployment feature or cut."""
import json
from pathlib import Path
import numpy as np
from calonu_weak_readout import template_weights
from report_calonu_information import strata
from report_calonu_native import crystalball
from train_bdt import write_table


repo = Path(__file__).resolve().parents[1]; out = repo/'workbook/stage43_energy_ml'
with np.load(repo/'ntuples/energy_ml_stage43/predictions.npz') as z: data = {k: z[k] for k in z.files}
with np.load(repo/'ntuples/energy_ml_stage42/sensitive.npz') as z: energy = z['hit_energy_MeV']
audit = json.loads((out/'response_audit.json').read_text())
pars = json.loads((repo/'workbook/stage42_energy_ml/synthetic_response.json').read_text())['parameters']
times = np.arange(760, 912, 2.)
kernel = crystalball(np.arange(12000)*.1, **pars).reshape(600, 20).mean(1)[(times/2).astype(int)]
gain = float(kernel.sum()*2/50*(2/16.384)); signal = energy*gain
rms = np.array(audit['fixed_noise_RMS_pC_by_module'])
with np.load(repo/'ntuples/energy_ml_stage43/data_noise.npz') as z: noise = z['residual_mV']
weights, _ = template_weights(times, pars); noise_charge = noise@weights
rows = []
for label, mask in strata(data).items():
    if not mask.any(): continue
    q = signal[mask]; snr = (q/rms).max(1)
    rows.append(dict(stratum=label, N=int(mask.sum()), empty_HITS=int((q == 0).all(1).sum()),
                     signal_sum_median_pC=float(np.median(q.sum(1))), signal_sum_p90_pC=float(np.quantile(q.sum(1), .9)),
                     max_module_SNR_median=float(np.median(snr)), fraction_max_module_SNR_lt1=float(np.mean(snr < 1)),
                     fraction_max_module_SNR_gt3=float(np.mean(snr > 3))))
write_table(out/'signal_visibility.tsv', rows)
(out/'noise_signal_scale.json').write_text(json.dumps(dict(charge_gain_pC_per_sensitive_MeV=gain,
                                                          total_fixed_noise_RMS_pC=float(np.sqrt(np.mean(noise_charge.sum(1)**2))),
                                                          total_fixed_noise_SD_pC=float(noise_charge.sum(1).std()), signal_summary=rows[:5]), indent=2)+'\n')
print(json.dumps(rows[:2]))
