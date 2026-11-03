"""Measure native K Calo charge-to-energy formula; no residual-derived scaling."""
import json
import sys
import numpy as np
import uproot

with uproot.open(sys.argv[1]) as f:
    a = f['nt'].arrays([f'Calo{j}_{k}' for j in range(4) for k in ['charge','E_EM','status']], library='np')
checks = []
for j in range(4):
    q, e, status = (a[f'Calo{j}_{k}'] for k in ['charge','E_EM','status'])
    take = (status == 0) & np.isfinite(q) & (abs(q) > 1e-6)
    if take.any():
        ratio = e[take].astype(float)/q[take]
        np.testing.assert_allclose(ratio, 330/.07569999992847443, rtol=2e-6)
        checks.append(dict(module=j, N=int(take.sum()), median_MeV_per_pC=float(np.median(ratio))))
assert checks
with open(sys.argv[2], 'w') as f:
    json.dump(dict(passed=True, produced='WAVE-Calibration-03-LG', checks=checks,
                   reference='WAVE-Calibration-01-LG', conversion='payload only, once at collection'), f, indent=2)
