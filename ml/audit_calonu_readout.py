#!/usr/bin/env python3
"""Bounded MC/data readout audit; neither a gain fit nor a hadronic calibration."""
import json
import resource
import time
from pathlib import Path

import numpy as np
import uproot

from calonu_inputs import load
from calonu_ablation import reports
from frozen_evaluation import save_json
from train_bdt import write_table


def audit(values, sample):
    rows = []
    n = len(values['CaloNu0_charge'])
    combined = np.zeros(n)
    fit = np.zeros(n)
    statuses = {}
    for i in range(4):
        q = np.asarray(values[f'CaloNu{i}_charge'], float)
        raw = np.asarray(values[f'CaloNu{i}_raw_charge'], float)
        energy = np.asarray(values[f'CaloNu{i}_E_EM'], float)
        mip = np.asarray(values[f'CaloNu{i}_nMIP'], float)
        dep = np.asarray(values[f'CaloNu{i}_E_dep'], float)
        status = np.asarray(values[f'CaloNu{i}_status'], int)
        statuses[str(i)] = {str(int(k)): int(v) for k, v in zip(*np.unique(status, return_counts=True))}
        with np.errstate(divide='ignore', invalid='ignore', over='ignore'):
            ratio = np.divide(raw, q, out=np.ones(n), where=q != 0)
            combined += energy * np.where(status & 4, 1, ratio)
        fit += energy
        for name, arr, unit in [('charge', q, 'pC'), ('raw_charge', raw, 'pC'), ('E_EM', energy / 1000, 'GeV EM scale'),
                                ('nMIP', mip, 'MIP'), ('E_dep', dep, 'MeV')]:
            finite = arr[np.isfinite(arr)]
            quant = np.quantile(finite, [0, .16, .5, .84, 1])
            rows.append(dict(sample=sample, module=i, observable=name, unit=unit, N=n, finite=len(finite),
                             nonfinite=n - len(finite), zero=int((arr == 0).sum()), min=quant[0], q16=quant[1], median=quant[2], q84=quant[3], max=quant[4]))
    observed = np.asarray(values['CaloNu_total_E_EM'], float)
    unit_errors = []
    for i in range(4):
        mip = np.asarray(values[f'CaloNu{i}_nMIP'], float)
        em = np.asarray(values[f'CaloNu{i}_E_EM'], float)
        dep = np.asarray(values[f'CaloNu{i}_E_dep'], float)
        em_valid = np.isfinite(em) & np.isfinite(mip)
        dep_valid = np.isfinite(dep) & np.isfinite(mip)
        unit_errors.append(dict(module=i, E_EM_eligible=int(em_valid.sum()), E_dep_eligible=int(dep_valid.sum()),
                                E_EM_equals_330_nMIP_failures=int((~np.isclose(em[em_valid], 330 * mip[em_valid], rtol=3e-6, atol=.001)).sum()),
                                E_dep_equals_58p5_nMIP_failures=int((~np.isclose(dep[dep_valid], 58.5 * mip[dep_valid], rtol=3e-6, atol=.001)).sum())))
    pair_finite = np.isfinite(observed) & np.isfinite(combined)
    difference = abs(observed[pair_finite] - combined[pair_finite])
    fit_finite = np.isfinite(values['CaloNu_total_fit_E_EM']) & np.isfinite(fit)
    summary = dict(sample=sample, N=n, status_counts=statuses, overflow_events=int(np.logical_or.reduce([np.asarray(values[f'CaloNu{i}_status'], int) & 4 != 0 for i in range(4)]).sum()),
                   total_zero=int((observed == 0).sum()), total_nonzero=int((np.isfinite(observed) & (observed != 0)).sum()),
                   total_nonfinite=int((~np.isfinite(observed)).sum()),
                   total_definition_eligible=int(pair_finite.sum()), total_definition_unmeasured_nonfinite=int((~pair_finite).sum()),
                   total_definition_failures=int((~np.isclose(observed[pair_finite], combined[pair_finite], rtol=3e-6, atol=.003)).sum()),
                   total_definition_max_abs_diff_MeV=float(np.max(difference)) if len(difference) else None,
                   fit_sum_definition_eligible=int(fit_finite.sum()),
                   fit_sum_definition_failures=int((~np.isclose(values['CaloNu_total_fit_E_EM'][fit_finite], fit[fit_finite], rtol=3e-6, atol=.003)).sum()),
                   unit_formula_tests=unit_errors)
    return rows, summary


def main():
    repo = Path(__file__).resolve().parents[1]
    out = reports(repo)
    tick = time.perf_counter()
    cpu = time.process_time()
    rows = []
    summaries = []
    # Development data only: no new test values are opened by this audit.
    values = load(repo, 'fit')
    r, s = audit(values, 'MC_fit')
    rows += r
    summaries.append(s)
    data_path = 'root://eospublic.cern.ch//eos/experiment/faser/data0/phys/2024_back/r0022/016000/Faser-Physics-016000-00000-00049-r0022-PHYS.root'
    columns = [f'CaloNu{i}_{k}' for i in range(4) for k in ['charge', 'raw_charge', 'status', 'E_EM', 'E_dep', 'nMIP']]
    columns += ['CaloNu_total_E_EM', 'CaloNu_total_fit_E_EM']
    with uproot.open(data_path) as f:
        values = f['nt'].arrays(columns, entry_stop=2048, library='np')
    r, s = audit(values, 'data16000_first2048_unselected')
    rows += r
    summaries.append(s)
    write_table(out / 'readout_audit.tsv', rows)
    save_json(out / 'readout_audit_summary.json', dict(samples=summaries, data_input=data_path,
              data_selection='first 2048 entries, no GRL/trigger/MIP selection, descriptive only',
              wall_s=time.perf_counter() - tick, cpu_s=time.process_time() - cpu,
              peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
              physical_data_MC_closure=False, hadronic_energy_calibration=False))
    print(json.dumps(summaries), flush=True)


if __name__ == '__main__':
    main()
