"""Fixed joint raw-response control; no neutrino risk or timing input."""
import concurrent.futures
import csv
import json
import math
import resource
import time
from pathlib import Path

import awkward as ak
import numpy as np
import uproot

OUT = Path('workbook/stage145_energy_ml')
SCINT = ['VetoNu0', 'VetoNu1', 'Veto10', 'Veto20', 'Veto21',
         'Timing0', 'Timing1', 'Timing2', 'Timing3', 'Preshower0', 'Preshower1']
CHANNELS = SCINT+[f'Calo{j}' for j in range(4)]
INVALID = 8 | 128 | 256


def clean(values):
    result = np.asarray(values, dtype=float).copy()
    result[~np.isfinite(result) | np.isin(result, [-999., -9999., -99999.])] = np.nan
    return result


def extract(source, stop):
    start, cpu = time.perf_counter(), time.thread_time()
    branches = ['run', 'eventID', 'longTracks', 'Track_pz0', 'Track_px0', 'Track_py0',
                'Track_Chi2', 'Track_nDoF', 'Track_nLayers', 'Track_X_atVetoStation1', 'Track_Y_atVetoStation1']
    branches += [channel+'_'+field for channel in CHANNELS for field in ['raw_charge', 'raw_peak', 'baseline_rms', 'status']]
    with uproot.open(source['input'], array_cache=None) as root:
        tree = root['nt']
        missing = sorted(set(branches)-set(tree.keys()))
        if missing:
            return None, dict(source=source, missing=missing, input_N=0, scope='No fake replacement for missing readout')
        truth_present = source['kind'].startswith('MC') and 'truth_pdg' in tree
        if truth_present:
            branches.append('truth_pdg')
        values = tree.arrays(branches, entry_stop=stop)
        leading = ak.argmax(values.Track_pz0, axis=1, keepdims=True, mask_identity=True)

        def get(name):
            return clean(ak.to_numpy(ak.fill_none(ak.firsts(values[name][leading]), np.nan)))

        pz = get('Track_pz0')/1000
        ndof, chi = get('Track_nDoF'), get('Track_Chi2')
        invalid_chi2 = int(np.count_nonzero(np.isfinite(chi) & (chi < 0)))
        chi[chi < 0] = np.nan
        good = ((ak.to_numpy(values.longTracks) == 1) & np.isfinite(pz) & (pz > 50) & (pz < 2000)
                & (ndof > 0) & (chi/np.maximum(ndof, 1) < 10) & (get('Track_nLayers') >= 7))
        q = np.column_stack([clean(ak.to_numpy(values[channel+'_raw_charge'])) for channel in CHANNELS])
        peak = np.column_stack([clean(ak.to_numpy(values[channel+'_raw_peak'])) for channel in CHANNELS])
        rms = np.column_stack([clean(ak.to_numpy(values[channel+'_baseline_rms'])) for channel in CHANNELS])
        status = np.column_stack([ak.to_numpy(values[channel+'_status']) for channel in CHANNELS]).astype(np.int64)
        present = np.isfinite(rms) & (rms > 0) & ((status & INVALID) == 0)
        q[~present] = np.nan
        peak[~present | (peak <= 0)] = np.nan
        with np.errstate(divide='ignore', invalid='ignore'):
            point = np.column_stack([np.log(pz), get('Track_X_atVetoStation1'), get('Track_Y_atVetoStation1'),
                                     get('Track_px0')/get('Track_pz0'), get('Track_py0')/get('Track_pz0')])
            shape = 50*q/peak  # Q[pC]/peak[mV] *50 ohm -> ns; signed for noise-only raw Q.
        if truth_present:
            pdg = values.truth_pdg
            pure = ak.to_numpy((ak.num(pdg, axis=1) > 0) & ak.all(abs(pdg) == 13, axis=1))
            pure_count = int(np.count_nonzero(pure & good))
        else:
            pure_count = None
        result = dict(entry=np.flatnonzero(good), point=point[good], charge=q[good], shape=shape[good], status=status[good], pz=pz[good])
        report = dict(source=source, missing=[], input_N=len(values), selected_muon_N=int(good.sum()), negative_chi2_placeholder_N=invalid_chi2,
                      selected_pz50_100_N=int(np.count_nonzero(good & (pz < 100))),
                      MC_truth_mu_only_N=pure_count, selected_signed_charge_minus1_N=int(np.count_nonzero(q[good] == -1)),
                      raw_presence_rule='finite positive baselineRMS plus noninvalid waveform; no-hit defaults excluded from measurement',
                      read_bytes=int(root.file.source.num_requested_bytes), thread_CPU_s=time.thread_time()-cpu,
                      wall_s=time.perf_counter()-start, RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return result, report


def wilson(k, n):
    if n == 0:
        return None, None
    z = 1.959963984540054
    p = k/n
    denominator = 1+z*z/n
    centre = (p+z*z/(2*n))/denominator
    half = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/denominator
    return centre-half, centre+half


def evaluate(index, data, report):
    rows, models = [], {}
    if data is None:
        return rows, models
    entry, point = data['entry'], data['point']
    split = entry % 4
    fit, calibration, test = split < 2, split == 2, split == 3
    for policy in ['Q15', 'Qshape30']:
        y = np.arcsinh(data['charge'])
        if policy == 'Qshape30':
            y = np.column_stack([y, np.arcsinh(data['shape']/10)])
        available = np.all(np.isfinite(point), axis=1) & np.all(np.isfinite(y), axis=1)
        train = fit & available
        base = dict(source_index=index, policy=policy, fit_N=int(train.sum()),
                    selected_N=len(entry), missing_readout_or_state_N=int((~available).sum()),
                    dimension=y.shape[1])
        if train.sum() < y.shape[1]+10:
            models[policy] = dict(base, supported=False, reason='Too few complete fit controls; no feature dropping or imputation')
            continue
        lo, hi = point[train].min(axis=0), point[train].max(axis=0)
        in_range = np.all((point >= lo) & (point <= hi), axis=1)
        mean, sd = point[train].mean(axis=0), point[train].std(axis=0)
        sd[sd == 0] = 1
        design = np.column_stack([np.ones(len(point)), (point-mean)/sd])
        beta, _, rank, singular = np.linalg.lstsq(design[train], y[train], rcond=None)
        residual = y-design@beta
        covariance = np.atleast_2d(np.cov(residual[train], rowvar=False))
        sigma = .9*covariance+.1*np.diag(np.diag(covariance))
        eigen = np.linalg.eigvalsh(sigma)
        if eigen[0] <= 0:
            models[policy] = dict(base, supported=False, reason='Singular measured response covariance; no extra regularization scan', eigenvalues=eigen.tolist())
            continue
        inverse = np.linalg.inv(sigma)
        score = np.einsum('ni,ij,nj->n', residual, inverse, residual)
        cal = calibration & available & in_range
        ncal = int(cal.sum())
        k = math.ceil(.95*(ncal+1))
        if ncal < 25 or k > ncal:
            models[policy] = dict(base, supported=False, reason='Too few in-support calibration controls', calibration_N=ncal)
            continue
        threshold = float(np.sort(score[cal])[k-1])
        total_charge = data['charge'].sum(axis=1)
        tail_threshold = float(np.quantile(total_charge[train], .99))
        overflow = np.any((data['status'] & 4) != 0, axis=1)
        groups = dict(all=np.ones(len(entry), bool), overflow=overflow,
                      high_activity=total_charge > tail_threshold,
                      pz50_100=data['pz'] < 100)
        for group, mask in groups.items():
            denominator = test & mask
            use = denominator & available & in_range
            n = int(use.sum())
            alerts = int(np.count_nonzero((score > threshold) & use))
            low, high = wilson(alerts, n)
            pure = report['MC_truth_mu_only_N'] == report['selected_muon_N'] and report['source']['kind'].startswith('MC')
            rows.append(dict(source_index=index, policy=policy, group=group,
                             original_heldout_N=int(denominator.sum()), scored_N=n, alerts=alerts,
                             alert_fraction=alerts/n if n else None, Wilson95_low=low, Wilson95_high=high,
                             missing_N=int(np.count_nonzero(denominator & ~available)),
                             outside_fit_state_range_N=int(np.count_nonzero(denominator & available & ~in_range)),
                             interpretation='mu-only MC empirical false alarm fraction' if pure else 'control alert fraction, not certified false positive rate'))
        models[policy] = dict(base, supported=True, calibration_N=ncal, design_rank=int(rank),
                              design_columns=design.shape[1], design_singular_values=singular.tolist(),
                              state_mean=mean.tolist(), state_scale=sd.tolist(), state_lo=lo.tolist(), state_hi=hi.tolist(),
                              beta=beta.tolist(), covariance=sigma.tolist(), covariance_min_eigenvalue=float(eigen[0]),
                              threshold=threshold, conformal_order_statistic=k,
                              high_activity_train_sum_raw_charge99_pC=tail_threshold,
                              max_abs_offdiagonal_correlation=float(np.max(np.abs(covariance/np.sqrt(np.outer(np.diag(covariance), np.diag(covariance)))-np.eye(y.shape[1])))),
                              support='Point conditioning; no track covariance; split within one file, not independent producer confirmation')
    return rows, models


def main():
    tick, cpu = time.perf_counter(), time.process_time()
    plan = json.loads((OUT/'protocol.json').read_text())
    preflight = []
    for source in plan['sources']:
        _, report = extract(source, plan['preflight_entries'])
        preflight.append(report)
    (OUT/'preflight.json').write_text(json.dumps(preflight, indent=2)+'\n')
    assert all(not row['missing'] for row in preflight), preflight
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        extracted = list(pool.map(lambda source: extract(source, plan['entry_stop']), plan['sources']))
    rows, reports, models = [], [], {}
    for index, (data, report) in enumerate(extracted):
        reports.append(report)
        measured, model = evaluate(index, data, report)
        rows.extend(measured)
        models[str(index)] = model
    (OUT/'source_audit.json').write_text(json.dumps(reports, indent=2)+'\n')
    (OUT/'models.json').write_text(json.dumps(models, indent=2, allow_nan=False)+'\n')
    if rows:
        with (OUT/'heldout.tsv').open('w') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter='\t', lineterminator='\n')
            writer.writeheader()
            writer.writerows(rows)
    report = dict(passed=True, source_N=len(reports), measured_score_group_rows=len(rows),
                  sources=reports, CPU_s=time.process_time()-cpu, wall_s=time.perf_counter()-tick,
                  RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  local_point_conditional_control=True, track_covariance_certified=False,
                  current_d32_nu_calibration_transfer=False, data_purity_or_background_certified=False,
                  radiation_process_labels_measured=False, natural_nu_forward=0, new_energy_fits=0, reserved_forward=0,
                  scope=plan['limits'])
    (OUT/'summary.json').write_text(json.dumps(report, indent=2)+'\n')
    print(report, flush=True)


if __name__ == '__main__':
    main()
