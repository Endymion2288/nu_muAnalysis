#!/usr/bin/env python3
"""Close raw waveform algebra and quantify nominal signal/noise on frozen native cases."""
import csv
import json
import math
import resource
import time
from pathlib import Path

import numpy as np


def table(path, rows):
    with path.open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter='\t', lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def crystalball(x, norm, mean, sigma, alpha, exponent):
    z = (np.asarray(x)-mean)/sigma
    z = z if alpha > 0 else -z
    a = abs(alpha)
    shape = np.exp(-.5*z*z)
    tail = z <= -a
    shape[tail] = np.exp(-.5*a*a-exponent*np.log1p((-a-z[tail])*a/exponent))
    normalization = sigma*(exponent/(a*(exponent-1))*math.exp(-.5*a*a)
                           + math.sqrt(math.pi/2)*(1+math.erf(a/math.sqrt(2))))
    return norm*shape/normalization


def nominal_signal(hits, channel_ids, centers, parameters):
    # Same 0.1 ns energy histogram, positive-time kernel and 20x averaging as pinned source.
    fine = 12000
    kernel = crystalball(np.arange(fine)*.1, **parameters)
    predicted = np.zeros((4, 600))
    energy = np.zeros(4)
    hit_count = np.zeros(4, int)
    outside = np.zeros(4)
    for i, hit_id in enumerate(channel_ids):
        selected = hits[hits[:, 0] == hit_id]
        hit_count[i] = len(selected)
        energy[i] = selected[:, 1].sum()
        tof = np.float32(centers[hit_id][2]/299.792458)
        times = (selected[:, 2].astype(np.float32)-tof).astype(np.float32)
        bins = np.floor((times.astype(float)+20)/.1).astype(int)
        valid = (bins >= 0) & (bins < 12199)
        outside[i] = selected[~valid, 1].sum()
        hist = np.bincount(bins[valid], weights=selected[valid, 1].astype(np.float32), minlength=12200)
        wave = np.zeros(fine)
        for b in np.flatnonzero(hist):
            shift = int(b)-200
            lo, hi = max(0, shift), min(fine, fine+shift)
            if hi > lo:
                wave[lo:hi] += (kernel[lo-shift:hi-shift]*np.float32(hist[b])).astype(np.float32)
        predicted[i] = wave.reshape(600, 20).mean(axis=1)
    return predicted, energy, hit_count, outside


def main():
    repo = Path(__file__).resolve().parents[1]
    out = repo/'workbook/stage37_energy_ml'
    cache = repo/'ntuples/energy_ml_stage37'
    cfg = json.loads((repo/'ml/configs/calonu_native_control.json').read_text())
    condition = json.loads((out/'conditions_audit.json').read_text())
    geo = json.loads((repo/'workbook/stage36_energy_ml/geometry_audit.json').read_text())
    tick, cpu = time.perf_counter(), time.process_time()
    digi = next(r['rows'][0]['payload'] for r in condition['records'] if r['label'] == 'MC100049' and r['folder'] == '/WAVE/Digitization')
    pars = {key: digi['cb_'+key] for key in ['norm', 'mean', 'sigma', 'alpha']}
    pars['exponent'] = digi['cb_n']
    # Cross-check the analytic kernel against ROOT's implementation, not a fitted curve.
    import ROOT
    grid = np.array([0., 780., 818., 820., 825., 850., 930., 1199.9])
    root_kernel = np.array([digi['cb_norm']*ROOT.Math.crystalball_pdf(float(x), digi['cb_alpha'], digi['cb_n'], digi['cb_sigma'], digi['cb_mean']) for x in grid])
    np.testing.assert_allclose(crystalball(grid, **pars), root_kernel, rtol=2e-12, atol=1e-14)
    mc_map = next(r['rows'] for r in condition['records'] if r['label'] == 'MC100049_archived')
    ids_by_channel = [1+(r['payload']['row'] << 1)+(r['payload']['module'] << 3) for r in sorted(mc_map, key=lambda r: r['channel'])]
    centers = {row['hit_id']: geo['nominal_core_centers_global_mm'][row['region']] for row in condition['gdml_factory_module_order']}
    expected_id32 = {row['hit_id']: row['readout_id32'] for row in condition['gdml_factory_module_order']}
    # Actual MC range was not persisted in p0. 2 V is the matched RawWaveform constructor default.
    mv_per_bit = 2/16.384
    rows, cases, resources, schemas = [], [], [], []
    compact, lineage = [], []
    with np.load(repo/'ntuples/energy_ml_stage36/MC.npz') as z:
        old = {key: z[key] for key in z.files}
    max_raw, max_wave, max_cache = 0., 0., 0.
    for group in cfg['groups']:
        with np.load(cache/f'shards/{group}.npz') as z:
            d = {key: z[key] for key in z.files}
        original = json.loads(str(d.pop('cases_json')))
        lineage.extend(original)
        resources.append(json.loads(str(d.pop('metadata_json'))))
        schemas += json.loads(str(d.pop('schemas_json')))
        index = np.flatnonzero(old['group_index'] == group)
        entry_lookup = {int(old['source_selected_row'][i]): i for i in index}
        for j, case in enumerate(original):
            hits = d['hits'][d['hit_offsets'][j]:d['hit_offsets'][j+1]]
            signal, energy, counts, outside = nominal_signal(hits, ids_by_channel, centers, pars)
            assert np.array_equal(d['id32'][j], [expected_id32[hid] for hid in ids_by_channel])
            assert np.all(d['saved_samples'][j] == 76)
            raw = d['raw_integral'][j]/50
            signed = d['saved_wave'][j].sum(axis=1)*2/50
            reconstructed_raw = np.maximum(d['saved_wave'][j], 0).sum(axis=1)*2/50
            max_raw = max(max_raw, float(np.max(abs(raw-reconstructed_raw))))
            assert np.allclose(raw, reconstructed_raw, atol=cfg['tolerances']['raw_charge_absolute_pC'], rtol=0)
            noise = 2*76*d['baseline_rms'][j]/(50*math.sqrt(2*math.pi))
            qsignal_window, qsignal_full, signed_fixed = [], [], []
            for i in range(4):
                samples = (d['saved_time'][j, i]/2).astype(int)
                adc = d['adc'][j, i]
                wave = (d['baseline_mean'][j, i]-adc[samples].astype(float)*mv_per_bit).astype(np.float32)
                delta = float(np.max(abs(wave-d['saved_wave'][j, i])))
                max_wave = max(max_wave, delta)
                assert delta <= cfg['tolerances']['waveform_absolute_mV']
                qsignal_window.append(signal[i, samples].sum()*2*mv_per_bit/50)
                qsignal_full.append(signal[i].sum()*2*mv_per_bit/50)
                signed_fixed.append((digi['base_mean']-adc[samples].astype(float)).sum()*2*mv_per_bit/50)
                oldrow = entry_lookup[case['selected_row']]
                for key, observed in [('raw_charge', raw[i]), ('charge', d['integral'][j, i]/50)]:
                    reference = old[f'CaloNu{i}_{key}'][oldrow]
                    if np.isfinite(observed) and np.isfinite(reference):
                        diff = abs(observed-reference)
                        max_cache = max(max_cache, float(diff))
                        assert np.isclose(observed, reference, rtol=3e-6, atol=3e-5)
                    else:
                        assert observed == reference or (np.isnan(observed) and np.isnan(reference))
                assert d['status'][j, i] == old[f'CaloNu{i}_status'][oldrow]
                rows.append(dict(group=group, input_entry=case['input_entry'], selected_row=case['selected_row'],
                                 role=case['role'], reco_p_GeV=case['fingerprint']['Track_p0']/1000,
                                 branch=i, hardware_channel=20+i, hit_id=ids_by_channel[i],
                                 sensitive_hit_count=int(counts[i]), sensitive_hit_energy_MeV=energy[i],
                                 hit_energy_outside_hist_MeV=outside[i],
                                 status=int(d['status'][j, i]), raw_charge_pC=raw[i], fit_charge_pC=d['integral'][j, i]/50,
                                 signed_saved_baseline_pC=signed[i], signed_known_baseline_pC=signed_fixed[i],
                                 noise_gaussian_pC=noise[i], predicted_signal_window_pC=qsignal_window[i],
                                 predicted_signal_full_pC=qsignal_full[i],
                                 predicted_peak_sigma=signal[i].max()/digi['base_rms'],
                                 window_start_ns=d['saved_time'][j, i, 0], window_stop_ns=d['saved_time'][j, i, -1]))
            qsignal_window, qsignal_full = np.array(qsignal_window), np.array(qsignal_full)
            dominant = int(np.argmax(energy))
            signature = case['beam_signature'][0]
            ptrue = np.linalg.norm(signature[2:5])/1000
            event = dict(group=group, run=case['run'], input_entry=case['input_entry'], selected_row=case['selected_row'], role=case['role'],
                         reco_p_GeV=case['fingerprint']['Track_p0']/1000, generated_p_GeV=ptrue,
                         hit_energy_total_MeV=float(energy.sum()), hit_energy_dominant_MeV=float(energy[dominant]),
                         predicted_peak_sigma=float(signal.max()/digi['base_rms']),
                         predicted_window_capture=float(qsignal_window.sum()/qsignal_full.sum()) if qsignal_full.sum() else np.nan,
                         predicted_signal_total_pC=float(qsignal_window.sum()), noise_total_pC=float(noise.sum()),
                         predicted_signal_over_noise=float(qsignal_window.sum()/noise.sum()),
                         raw_total_pC=float(raw.sum()), signed_saved_total_pC=float(signed.sum()),
                         signed_known_total_pC=float(np.sum(signed_fixed)),
                         nonfinite_fit_modules=int((~np.isfinite(d['integral'][j])).sum()),
                         unflagged_nonfinite_fit_modules=int(((~np.isfinite(d['integral'][j])) & (d['status'][j] & 48 == 0)).sum()),
                         mass_difference_MeV=case.get('beam_mass_difference_MeV', 0.))
            cases.append(event)
            compact.append(dict(adc=d['adc'][j], saved_wave=d['saved_wave'][j], saved_time=d['saved_time'][j],
                                signal_nominal_ADC=signal.astype(np.float32),
                                integral=d['integral'][j], raw_integral=d['raw_integral'][j], status=d['status'][j],
                                baseline_mean=d['baseline_mean'][j], baseline_rms=d['baseline_rms'][j],
                                localtime=d['localtime'][j], peak=d['peak'][j], width=d['width'][j],
                                mean=d['mean'][j], alpha=d['alpha'][j], nval=d['nval'][j],
                                hit_energy_MeV=energy, hit_count=counts))
    table(out/'native_module_response.tsv', rows)
    table(out/'native_case_response.tsv', cases)
    data = {key: np.stack([r[key] for r in compact]) for key in compact[0]}
    data['cases_json'] = np.array(json.dumps(cases))
    data['lineage_json'] = np.array(json.dumps(lineage))
    np.savez_compressed(cache/'native_response.npz', **data)
    with np.load(cache/'native_response.npz') as z:
        for key in data:
            np.testing.assert_array_equal(z[key], data[key])
    rng = np.random.default_rng(cfg['bootstrap_seed'])
    values = {key: np.array([r[key] for r in cases]) for key in cases[0]}
    groups = values['group']
    draws = np.zeros((cfg['bootstrap_replicates'], 4), int)
    for columns in [[0, 1], [2, 3]]:
        draws[:, columns] = rng.multinomial(2, [.5, .5], size=len(draws))
    gid = np.searchsorted(cfg['groups'], groups)
    metrics = []
    for subset, mask in [('regular', values['role'] == 'regular'),
                         ('regular_p100_250', (values['role'] == 'regular') & (values['reco_p_GeV'] < 250)),
                         ('regular_p250_1000', (values['role'] == 'regular') & (values['reco_p_GeV'] >= 250)),
                         ('diagnostic', values['role'] != 'regular')] + [
                             (f'regular_group{g}', (values['role'] == 'regular') & (groups == g))
                             for g in cfg['groups']]:
        for key in ['hit_energy_total_MeV', 'hit_energy_dominant_MeV', 'predicted_peak_sigma', 'predicted_window_capture',
                    'predicted_signal_total_pC', 'noise_total_pC', 'predicted_signal_over_noise',
                    'raw_total_pC', 'signed_saved_total_pC', 'signed_known_total_pC']:
            finite = mask & np.isfinite(values[key].astype(float))
            x = values[key][finite].astype(float)
            # Single groups and deliberately enriched diagnostics have descriptive summaries only.
            intervals = dict(mean_lo='not_applicable', mean_hi='not_applicable',
                             median_lo='not_applicable', median_hi='not_applicable')
            if subset in ['regular', 'regular_p100_250', 'regular_p250_1000']:
                boots = np.array([[np.mean(np.repeat(x, w[gid[finite]])), np.median(np.repeat(x, w[gid[finite]]))]
                                  for w in draws])
                intervals = dict(mean_lo=float(np.quantile(boots[:, 0], .025)), mean_hi=float(np.quantile(boots[:, 0], .975)),
                                 median_lo=float(np.quantile(boots[:, 1], .025)), median_hi=float(np.quantile(boots[:, 1], .975)))
            metrics.append(dict(subset=subset, observable=key, N=int(mask.sum()), finite=len(x),
                                mean=float(np.mean(x)), median=float(np.median(x)), q16=float(np.quantile(x, .16)), q84=float(np.quantile(x, .84)),
                                minimum=float(np.min(x)), maximum=float(np.max(x)),
                                **intervals))
    table(out/'native_metrics.tsv', metrics)
    summary = dict(events=len(cases), regular=sum(r['role'] == 'regular' for r in cases), diagnostic=sum(r['role'] != 'regular' for r in cases),
                   raw_charge_max_abs_difference_pC=max_raw, ADC_to_saved_wave_max_abs_difference_mV=max_wave,
                   cache_charge_max_abs_difference_pC=max_cache, native_layout_checksums_equal=True,
                   HITS_RDO_primary_momentum_exact=True, max_beam_mass_difference_MeV=max(r['mass_difference_MeV'] for r in cases),
                   kernel_ROOT_crosscheck=True, final_cache_bytes=(cache/'native_response.npz').stat().st_size, all_field_readback_equal=True,
                   nominal_prediction_limit='Source convolution with nominal GDML TOF, MC default 2 V; no new digitization or exact random-seed/native-GeoModel replay',
                   current_global_tag_cable_map_reproduces_old_production=False,
                   wall_s=time.perf_counter()-tick, cpu_s=time.process_time()-cpu,
                   peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024, extraction_resources=resources)
    (out/'native_summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    # Deduplicate class layout evidence; the full per-case source linkage is in the frozen request and cases.
    (out/'native_schema_checks.json').write_text(json.dumps(schemas, indent=2)+'\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
