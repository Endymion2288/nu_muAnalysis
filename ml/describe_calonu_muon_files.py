#!/usr/bin/env python3
"""Posthoc file variation, retaining every frozen candidate; no fitting or new cuts."""
import json
import time
from pathlib import Path

import numpy as np

from calonu_muon_control import cache_dir, manifest, output_dir, write_json
from report_calonu_muon import write_table


def median(values):
    finite = values[np.isfinite(values)]
    return float(np.median(finite)) if len(finite) else np.nan


def main():
    repo = Path(__file__).resolve().parents[1]
    tick = time.perf_counter()
    files = {int(row['index']): row for row in manifest(repo)}
    totals, modules = [], []
    for sample in ['MC', 'data']:
        with np.load(cache_dir(repo)/f'{sample}.npz') as z:
            d = {key: z[key] for key in z.files}
        for group in np.unique(d['group_index']):
            mask = d['group_index'] == group
            context = dict(sample=sample, group=files[group]['group'], run=int(d['run'][mask][0]))
            status = np.column_stack([d[f'CaloNu{i}_status'][mask] for i in range(4)]).astype(int)
            em = d['CaloNu_total_E_EM'][mask].astype(float)/1000
            totals.append(dict(**context, N=int(mask.sum()), eventTime_min=int(d['eventTime'][mask].min()),
                               eventTime_max=int(d['eventTime'][mask].max()), finite_total=int(np.isfinite(em).sum()),
                               median_total_E_EM_GeV=median(em), all_four_threshold_failed_fraction=float(((status & 1) != 0).all(axis=1).mean())))
            for i in range(4):
                fit, mip = [d[f'CaloNu{i}_{key}'][mask].astype(float) for key in ['charge', 'nMIP']]
                with np.errstate(divide='ignore', invalid='ignore'):
                    reference = fit/mip
                modules.append(dict(**context, module=i, N=len(fit),
                                    median_raw_charge_pC=median(d[f'CaloNu{i}_raw_charge'][mask]),
                                    median_fit_charge_pC=median(fit), median_baseline_rms_mV=median(d[f'CaloNu{i}_baseline_rms'][mask]),
                                    median_effective_charge_per_MIP_pC=median(reference),
                                    threshold_failed_fraction=float(((status[:, i] & 1) != 0).mean()),
                                    fit_failed_fraction=float(((status[:, i] & 48) != 0).mean())))
    out = output_dir(repo)
    write_table(out/'file_total_response_posthoc.tsv', totals)
    write_table(out/'file_module_response_posthoc.tsv', modules)
    write_json(out/'file_variation_summary.json', dict(wall_s=time.perf_counter()-tick,
               note='Posthoc descriptive file medians; no within-file interval, cuts, rescaling or model change; eventTime is stored Unix seconds'))


if __name__ == '__main__':
    main()
