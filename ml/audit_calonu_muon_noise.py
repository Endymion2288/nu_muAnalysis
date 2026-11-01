#!/usr/bin/env python3
"""Post-fit descriptive interpretation of frozen response controls; no new selections."""
import json
import time
from pathlib import Path

import numpy as np

from calonu_muon_control import cache_dir, config, output_dir, write_json
from report_calonu_muon import describe, geometry, weights, write_table


def main():
    repo = Path(__file__).resolve().parents[1]
    cfg, out = config(repo), output_dir(repo)
    tick = time.perf_counter()
    rng = np.random.default_rng(cfg['bootstrap_seed'])
    audit = json.loads((out/'geometry_audit.json').read_text())
    noise_rows, matrix, quality = [], [], []
    for sample in ['MC', 'data']:
        with np.load(cache_dir(repo)/f'{sample}.npz') as z:
            d = {k: z[k] for k in z.files}
        gid, draws = weights(d, sample, rng, cfg['bootstrap_replicates'])
        n = len(gid)
        status = np.column_stack([d[f'CaloNu{i}_status'] for i in range(4)]).astype(int)
        em = np.column_stack([d[f'CaloNu{i}_E_EM'] for i in range(4)])/1000
        raw = np.column_stack([d[f'CaloNu{i}_raw_charge'] for i in range(4)])
        qnoise = 2*cfg['raw_noise_samples']*np.column_stack([d[f'CaloNu{i}_baseline_rms'] for i in range(4)])/(50*np.sqrt(2*np.pi))
        refs = []
        for i in range(4):
            with np.errstate(divide='ignore', invalid='ignore'):
                ratio = d[f'CaloNu{i}_charge']/d[f'CaloNu{i}_nMIP']
            refs.append(np.median(ratio[np.isfinite(ratio)]))
        expected = np.sum(qnoise/refs*.330, axis=1)
        total = d['CaloNu_total_E_EM']/1000
        allmask = np.ones(n, bool)
        allfailed = (status & 1 != 0).all(axis=1)
        for subset, mask in [('all', allmask), ('all_four_threshold_failed', allfailed)]:
            for name, value, unit in [('noise_expected_total', expected, 'GeV EM scale'),
                                      ('total_over_noise_expected', total/expected, 'dimensionless'),
                                      ('all_four_threshold_failed_fraction', allfailed.astype(float), 'fraction')]:
                noise_rows.append(describe(value, mask, gid, draws, dict(sample=sample, subset=subset, observable=name, unit=unit)))
        # Posthoc count audit: status flags are not a truth label for a defective waveform.
        nonfinite = ~np.isfinite(em)
        extreme = nonfinite | (abs(em) > 1000)
        flag = status & 48 != 0
        for label, mask in [('nonfinite_EM', nonfinite), ('finite_abs_EM_gt_1000GeV', np.isfinite(em) & (abs(em) > 1000)), ('negative_finite_EM', np.isfinite(em) & (em < 0))]:
            quality.append(dict(sample=sample, diagnostic=label, module_observations=4*n, count=int(mask.sum()),
                                with_fit_failure_flag=int((mask & flag).sum()), without_fit_failure_flag=int((mask & ~flag).sum()),
                                finite_raw=int((mask & np.isfinite(raw)).sum()),
                                note='Count audit only; extreme finite values are not automatically errors'))
        geo = geometry(d, audit)
        for region in range(4):
            mask = geo['robust_interior'][:, region]
            for channel in range(4):
                matrix.append(describe(raw[:, channel], mask, gid, draws,
                                       dict(sample=sample, nominal_region=region, readout_module=channel, observable='raw_charge', unit='pC')))
        # A descriptive same-row fingerprint verifies IDs collide without silently deduplicating.
        fingerprint = np.rec.fromarrays([d['group_index'], d['eventID'], d['Track_p0'], d['Track_X_atVetoNu'], d['Track_Y_atVetoNu'], raw[:, 0]],
                                        names=['file', 'eventID', 'p', 'x', 'y', 'raw0'])
        quality.append(dict(sample=sample, diagnostic='exact_repeated_selected_fingerprint', module_observations=n,
                            count=n-len(np.unique(fingerprint)), with_fit_failure_flag='', without_fit_failure_flag='', finite_raw='',
                            note='Fingerprint is descriptive, not proof of full generator/flux genealogy independence'))
    write_table(out/'noise_aggregate.tsv', noise_rows)
    write_table(out/'unflagged_quality.tsv', quality)
    write_table(out/'module_association_posthoc.tsv', matrix)
    write_json(out/'noise_audit_summary.json', dict(wall_s=time.perf_counter()-tick,
             note='Noise formula was preregistered; aggregate ratios, exact fingerprints and 4x4 association are posthoc descriptive interpretation; no model/cuts changed',
             matching_module_map_independently_verified=False, calibration_or_waveform_correction_applied=False))


if __name__ == '__main__':
    main()
