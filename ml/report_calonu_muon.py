#!/usr/bin/env python3
"""CaloNu response control; block intervals include run variability, not full systematics."""
import csv
import json
import resource
import time
from pathlib import Path

import numpy as np

from audit_calonu_geometry import intersection, rotation
from calonu_muon_control import cache_dir, config, manifest, output_dir, write_json


def write_table(path, rows):
    with path.open('w') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter='\t', lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def weights(data, sample, rng, repeats):
    groups, gid = np.unique(data['group_index'], return_inverse=True)
    runs = np.array([data['run'][np.flatnonzero(gid == i)[0]] for i in range(len(groups))])
    result = np.zeros((repeats, len(groups)), int)
    if sample == 'MC':
        for run in np.unique(runs):
            idx = np.flatnonzero(runs == run)
            result[:, idx] = rng.multinomial(len(idx), np.ones(len(idx))/len(idx), size=repeats)
    else:
        unique = np.unique(runs)
        for b in range(repeats):
            for run in rng.choice(unique, len(unique)):
                idx = np.flatnonzero(runs == run)
                result[b, idx] += rng.multinomial(len(idx), np.ones(len(idx))/len(idx))
    return gid, result


def boot_quantiles(value, gid, multiplicity, probabilities):
    """Exact np.quantile of integer-replicated blocks, via group CDF rank search."""
    if not len(value):
        return np.full((len(multiplicity), len(probabilities)), np.nan)
    order = np.argsort(value)
    v, g = value[order], gid[order]
    ng = multiplicity.shape[1]
    cdf = np.cumsum(np.arange(ng)[:, None] == g[None, :], axis=1, dtype=np.int32)
    n = multiplicity @ cdf[:, -1]
    ranks = (np.maximum(n, 1)[:, None] - 1)*np.asarray(probabilities)

    def search(target):
        target = np.where(n[:, None] > 0, target, 0)
        lo = np.zeros_like(target, dtype=int)
        hi = np.full_like(target, len(v)-1, dtype=int)
        while (lo < hi).any():
            mid = (lo + hi)//2
            count = np.sum(multiplicity[:, :, None]*cdf[:, mid].transpose(1, 0, 2), axis=1)
            upper = count >= target
            hi = np.where(upper, mid, hi)
            lo = np.where(upper, lo, mid+1)
        return v[lo]

    lower = np.floor(ranks).astype(int)
    upper = np.ceil(ranks).astype(int)
    a, b = search(lower+1), search(upper+1)
    result = a + (ranks-lower)*(b-a)
    result[n == 0] = np.nan
    return result


def interval(value):
    valid = np.isfinite(value)
    if not valid.any():
        return [np.nan, np.nan, len(value)]
    q = np.quantile(value[valid], [.025, .975])
    return [float(q[0]), float(q[1]), int((~valid).sum())]


def describe(values, mask, gid, draws, context, quantiles=True):
    finite = mask & np.isfinite(values)
    v, g = values[finite].astype(float), gid[finite]
    row = dict(**context, N=int(mask.sum()), finite=int(finite.sum()), nonfinite=int((mask & ~finite).sum()),
               groups=len(np.unique(g)), mean=np.nan, q16=np.nan, median=np.nan, q84=np.nan)
    if len(v):
        row.update(mean=float(np.mean(v)))
        if quantiles:
            row.update(zip(['q16', 'median', 'q84'], np.quantile(v, [.16, .5, .84])))
        count = draws @ np.bincount(g, minlength=draws.shape[1])
        with np.errstate(invalid='ignore', divide='ignore'):
            bootmean = (draws @ np.bincount(g, weights=v, minlength=draws.shape[1]))/count
        boots = {'mean': bootmean}
        if quantiles:
            q = boot_quantiles(v, g, draws, [.16, .5, .84])
            boots.update(q16=q[:, 0], median=q[:, 1], q84=q[:, 2])
    else:
        boots = {k: np.full(len(draws), np.nan) for k in ['mean', 'q16', 'median', 'q84'] if quantiles or k == 'mean'}
    for key in ['mean', 'q16', 'median', 'q84']:
        lo, hi, invalid = interval(boots[key]) if key in boots else [np.nan, np.nan, len(draws)]
        row.update({key+'_lo': lo, key+'_hi': hi, key+'_invalid_boot': invalid})
    return row


def geometry(data, audit):
    center = np.array(audit['calonu_box_center_global_mm'])
    nominal = np.array(audit['nominal_core_centers_global_mm'])
    local = (nominal-center) @ rotation(.05)
    result = {}
    for label, angle in [('nominal', .05), ('opposite', -.05)]:
        r = rotation(angle)
        centers = center + local @ r.T
        length, interior = intersection(*[data['Track_'+k] for k in ['X_atVetoNu', 'Y_atVetoNu', 'ThetaX_atVetoNu', 'ThetaY_atVetoNu']],
                                        centers, r, audit['core_half_sizes_mm'])
        result[label+'_path_mm'] = length
        result[label+'_interior'] = interior
        result[label+'_off'] = length == 0
    result['robust_off'] = result['nominal_off'] & result['opposite_off']
    result['robust_interior'] = result['nominal_interior'] & result['opposite_interior']
    return result


def main():
    repo = Path(__file__).resolve().parents[1]
    cfg, out = config(repo), output_dir(repo)
    tick, cpu = time.perf_counter(), time.process_time()
    audit = json.loads((out/'geometry_audit.json').read_text())
    rng = np.random.default_rng(cfg['bootstrap_seed'])
    rows, quality, coverage, paired, totals = [], [], [], [], []
    for sample in ['MC', 'data']:
        with np.load(cache_dir(repo)/f'{sample}.npz') as z:
            data = {k: z[k] for k in z.files}
        gid, draws = weights(data, sample, rng, cfg['bootstrap_replicates'])
        geo = geometry(data, audit)
        allmask = np.ones(len(gid), bool)
        p = data['Track_p0']/1000
        subsets = dict(all=allmask, p100_250=p < 250, p250_1000=p >= 250)
        subsets.update({f'run_{r}': data['run'] == r for r in np.unique(data['run'])})
        statuses = np.column_stack([data[f'CaloNu{i}_status'] for i in range(4)]).astype(int)
        subsets['all_four_threshold_failed'] = (statuses & 1 != 0).all(axis=1)
        for subset, mask in subsets.items():
            for kind in ['E_EM', 'fit_E_EM', 'raw_E_EM']:
                totals.append(describe(data['CaloNu_total_'+kind]/1000, mask, gid, draws,
                                       dict(sample=sample, subset=subset, observable='total_'+kind, unit='GeV EM scale')))
            coverage.append(dict(sample=sample, subset=subset, N=int(mask.sum()),
                                 unique_nominal_interior=int((mask & (geo['nominal_interior'].sum(axis=1) == 1)).sum()),
                                 unique_robust_interior=int((mask & (geo['robust_interior'].sum(axis=1) == 1)).sum()),
                                 nominal_all_off=int((mask & geo['nominal_off'].all(axis=1)).sum()),
                                 robust_all_off=int((mask & geo['robust_off'].all(axis=1)).sum()),
                                 modules_with_changed_interior=int((mask[:, None] & (geo['nominal_interior'] != geo['opposite_interior'])).sum())))
        for i in range(4):
            status = statuses[:, i]
            fit = data[f'CaloNu{i}_charge'].astype(float)
            raw = data[f'CaloNu{i}_raw_charge'].astype(float)
            mip = data[f'CaloNu{i}_nMIP'].astype(float)
            em = data[f'CaloNu{i}_E_EM'].astype(float)/1000
            noise = 2*cfg['raw_noise_samples']*data[f'CaloNu{i}_baseline_rms'].astype(float)/(50*np.sqrt(2*np.pi))
            with np.errstate(divide='ignore', invalid='ignore'):
                effective = np.where(np.isfinite(mip) & (mip != 0), fit/mip, np.nan)
                ratio = np.where(noise > 0, raw/noise, np.nan)
                peak_snr = data[f'CaloNu{i}_raw_peak']/data[f'CaloNu{i}_baseline_rms']
            observables = dict(raw_charge=(raw, 'pC'), fit_charge=(fit, 'pC'), nMIP=(mip, 'MIP'),
                               E_EM=(em, 'GeV EM scale'), noise_expected_charge=(noise, 'pC'),
                               raw_over_noise=(ratio, 'dimensionless'), effective_charge_per_MIP=(effective, 'pC/MIP'),
                               baseline_rms=(data[f'CaloNu{i}_baseline_rms'], 'mV'), raw_peak_snr=(peak_snr, 'dimensionless'),
                               path_proxy=(geo['nominal_path_mm'][:, i], 'mm'))
            roles = dict(all=allmask, nominal_interior=geo['nominal_interior'][:, i], nominal_off=geo['nominal_off'][:, i],
                         nominal_edge=(geo['nominal_path_mm'][:, i] > 0) & ~geo['nominal_interior'][:, i],
                         robust_off=geo['robust_off'][:, i], robust_interior=geo['robust_interior'][:, i],
                         threshold_failed=(status & 1) != 0, robust_off_threshold_failed=geo['robust_off'][:, i] & (status & 1 != 0),
                         fit_failed=status & 48 != 0)
            roles.update({f'status_{s}': status == s for s in np.unique(status)})
            for subset, smask in subsets.items():
                # Keep the full crossing/geometry audit for all; run/p controls use all modules and robust off.
                selected_roles = roles if subset == 'all' else {k: roles[k] for k in ['all', 'robust_off', 'robust_interior']}
                for role, rmask in selected_roles.items():
                    mask = smask & rmask
                    context = dict(sample=sample, subset=subset, module=i, role=role)
                    for observable, (value, unit) in observables.items():
                        rows.append(describe(value, mask, gid, draws, dict(**context, observable=observable, unit=unit)))
                    extreme = ~np.isfinite(em) | (abs(em) > cfg['thresholds']['extreme_abs_E_EM_GeV'])
                    fitflag = status & 48 != 0
                    flags = dict(zero_EM=em == 0, negative_EM=np.isfinite(em) & (em < 0), nonfinite_EM=~np.isfinite(em),
                                 threshold_failed=status & 1 != 0, fit_failed=fitflag, overflow=status & 4 != 0,
                                 waveform_missing=status & 128 != 0, waveform_invalid=status & 256 != 0,
                                 extreme_EM=extreme, extreme_and_fitflag=extreme & fitflag,
                                 finite_raw=np.isfinite(raw), fit_equals_raw=np.isclose(fit, raw, rtol=3e-6, atol=1e-7))
                    for flag, value in flags.items():
                        quality.append(describe(value.astype(float), mask, gid, draws, dict(**context, flag=flag, unit='fraction'), quantiles=False))
            # Event-paired contrast, including finite cases only; no truncation of large fits.
            off = geo['robust_off'].copy()
            off[:, i] = False
            raw4 = np.column_stack([data[f'CaloNu{j}_raw_charge'] for j in range(4)])
            off_count = off.sum(axis=1)
            with np.errstate(divide='ignore', invalid='ignore'):
                off_mean = np.where(off_count > 0, np.where(off, raw4, 0).sum(axis=1)/off_count, np.nan)
            mask = geo['robust_interior'][:, i] & (off_count > 0)
            paired.append(describe(raw-off_mean, mask, gid, draws,
                                   dict(sample=sample, module=i, observable='nominal_branch_interior_minus_other_robust_off_raw_charge', unit='pC')))
    for name, table in [('response_metrics.tsv', rows), ('response_quality.tsv', quality), ('geometry_coverage.tsv', coverage),
                        ('paired_channel_response.tsv', paired), ('total_response.tsv', totals)]:
        write_table(out/name, table)
    # Validate exact block quantiles against explicit replication on a nontrivial small example.
    x, gid = np.array([8., -4., 3., 7., 1., 2.]), np.array([0, 1, 2, 0, 1, 2])
    w = np.array([[1, 1, 1], [2, 1, 0], [0, 1, 3], [0, 0, 0]])
    obtained = boot_quantiles(x, gid, w, [.16, .5, .84])
    for i in range(3):
        explicit = np.repeat(x, w[i, gid])
        np.testing.assert_allclose(obtained[i], np.quantile(explicit, [.16, .5, .84]), atol=1e-12)
    assert np.isnan(obtained[3]).all()
    write_json(out/'response_summary.json', dict(
        frozen_utc=cfg['frozen_utc'], bootstrap_replicates=cfg['bootstrap_replicates'],
        bootstrap='MC sign-stratified file blocks; data run then file blocks', exact_rank_bootstrap_check=True,
        new_fits=0, data_MC_physics_closure=False, geometry_proxy_and_channel_order_limitations=True,
        wall_s=time.perf_counter()-tick, cpu_s=time.process_time()-cpu,
        peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
        response_rows=len(rows), quality_rows=len(quality)))


if __name__ == '__main__':
    main()
