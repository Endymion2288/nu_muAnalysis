#!/usr/bin/env python3
"""Bounded real-data offpulse extraction and isolated MC signal injection."""
import argparse
import json
import resource
import subprocess
import time
from pathlib import Path
import numpy as np
from calonu_weak_readout import template_weights
from report_calonu_native import crystalball
from train_bdt import write_table

REPO = Path(__file__).resolve().parents[1]
OUT = REPO/'workbook/stage43_energy_ml'
CACHE = REPO/'ntuples/energy_ml_stage43'


def extract(reader, smoke):
    cfg = json.loads((REPO/'ml/configs/calonu_data_noise.json').read_text())
    manifest = json.loads((OUT/'raw_manifest.json').read_text())
    if smoke:
        manifest = [next(r for r in manifest if r['run'] == 16000 and r['file'] == 0)]
    for row in manifest:
        tick, cpu = time.perf_counter(), time.process_time()
        count = 2 if smoke else cfg['data_noise']['physics_events_per_file']
        run = subprocess.run([str(reader), row['input'], str(count), str(row['run'])],
                             text=True, capture_output=True, check=True, timeout=120)
        cases = [json.loads(line) for line in run.stdout.splitlines()]
        assert len(cases) == count
        adc = np.array([c.pop('adc') for c in cases], dtype=np.uint16)
        assert adc.shape == (count, 4, 280), adc.shape
        used_board = 1 if row['run'] == 15838 else 0
        assert all(c['board_valid'][used_board] == 1 for c in cases)
        data = {k: np.array([c[k] for c in cases]) for k in cases[0]}
        data.update(adc=adc, noise_fold=np.full(count, row['noise_fold']), file_index=np.full(count, row['index']))
        metadata = dict(**row, events=count, smoke=smoke, wall_s=time.perf_counter()-tick,
                        cpu_s=time.process_time()-cpu, decoder_cumulative_user_s=resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime,
                        peak_rss_MiB=max(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                                         resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)/1024,
                        bytes_read=cases[-1]['bytes_through'], frozen_utc=cfg['frozen_utc'])
        target = CACHE/('smoke.npz' if smoke else f'shards/{row["index"]}.npz')
        target.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(target, **data, metadata_json=np.array(json.dumps(metadata)))
        print(json.dumps(metadata), flush=True)


def build():
    tick, cpu = time.perf_counter(), time.process_time()
    cfg = json.loads((REPO/'ml/configs/calonu_data_noise.json').read_text()); noise_cfg = cfg['data_noise']
    manifest = json.loads((OUT/'raw_manifest.json').read_text()); pieces = []; resources = []
    for row in manifest:
        with np.load(CACHE/f'shards/{row["index"]}.npz') as z:
            m = json.loads(str(z['metadata_json']))
            assert not m['smoke'] and m['frozen_utc'] == cfg['frozen_utc'] and m['events'] == 56
            if 'decoder_cpu_s' in m: m['decoder_cumulative_user_s'] = m.pop('decoder_cpu_s')
            resources.append(m); pieces.append({k: z[k] for k in z.files if k != 'metadata_json'})
    data = {k: np.concatenate([p[k] for p in pieces]) for k in pieces[0]}
    assert len(data['run']) == 504 <= noise_cfg['max_data_events']
    assert len(set(zip(data['run'], data['eventID']))) == 504
    adc = data['adc'].astype(float); lo, hi = noise_cfg['pedestal_samples']; a, b = noise_cfg['offpulse_samples']
    pedestal = adc[:, :, lo:hi].mean(2)
    residual = (pedestal[:, :, None]-adc[:, :, a:b])*noise_cfg['ADC_mV']
    with np.load(REPO/'ntuples/energy_ml_stage42/development.npz') as z:
        chosen = np.flatnonzero(z['selected']); fold = z['fold'][chosen]; event_id = z['eventID'][chosen]
    with np.load(REPO/'ntuples/energy_ml_stage42/sensitive.npz') as z:
        np.testing.assert_array_equal(z['cache_row'], chosen); energy = z['hit_energy_MeV']
        np.testing.assert_array_equal(z['eventID'], event_id)
    # Allocation is independent of the neutrino labels and truth signal.
    rng = np.random.default_rng(noise_cfg['assignment_seed']); assignment = np.empty(len(chosen), int)
    for f in range(3):
        ids = np.flatnonzero(data['noise_fold'] == f); nu_ids = np.flatnonzero(fold == f)
        assignment[nu_ids] = np.concatenate([rng.permutation(ids) for _ in range((len(nu_ids)+len(ids)-1)//len(ids))])[:len(nu_ids)]
    np.testing.assert_array_equal(data['noise_fold'][assignment], fold)
    condition = json.loads((REPO/'workbook/stage37_energy_ml/conditions_audit.json').read_text())
    digi = next(r['rows'][0]['payload'] for r in condition['records'] if r['label'] == 'MC100049' and r['folder'] == '/WAVE/Digitization')
    pars = {k: digi['cb_'+k] for k in ['norm', 'sigma', 'alpha']}; pars.update(mean=noise_cfg['fixed_time_ns'], exponent=digi['cb_n'])
    times = np.arange(760, 912, 2, dtype=float)
    kernel = crystalball(np.arange(12000)*.1, **pars).reshape(600, 20).mean(1)[(times/2).astype(int)]
    signal = energy[:, :, None]*kernel[None, None, :]*noise_cfg['ADC_mV']
    weights, _ = template_weights(times, pars)
    noise_charge = residual@weights; signal_charge = signal@weights
    np.testing.assert_allclose(signal_charge, signal.sum(2)*2/50, atol=1e-9, rtol=1e-12)
    outputs = {'ideal_sum': np.column_stack([energy, energy.sum(1)]).astype('float32')}
    for name, gain in [('data_noise_nominal', noise_cfg['gain_nominal']), ('data_noise_half_gain', noise_cfg['gain_pressure'])]:
        value = gain*signal_charge+noise_charge[assignment]
        outputs[name] = np.column_stack([value, value.sum(1)]).astype('float32')
    np.savez_compressed(CACHE/'response.npz', cache_row=chosen, eventID=event_id, noise_row=assignment, **outputs)
    np.savez_compressed(CACHE/'data_noise.npz', **data, residual_mV=residual.astype('float32'))
    rows = []
    for index in range(9):
        mask = data['file_index'] == index; d = adc[mask]; n = residual[mask]; q = noise_charge[mask]
        centered = n-n.mean(2, keepdims=True)
        cl, ch = noise_cfg['comparison_samples']; before = d[:, :, cl:ch]-d[:, :, cl:ch].mean(2, keepdims=True)
        corr = np.corrcoef(centered.transpose(1, 0, 2).reshape(4, -1))
        for module in range(4):
            x = centered[:, module]; rho = float(np.sum(x[:, :-1]*x[:, 1:])/np.sqrt(np.sum(x[:, :-1]**2)*np.sum(x[:, 1:]**2)))
            rows.append(dict(file_index=index, run=manifest[index]['run'], file=manifest[index]['file'], noise_fold=manifest[index]['noise_fold'],
                             module=module, events=int(mask.sum()), sample_RMS_mV=float(np.sqrt(np.mean(x*x))), lag1_correlation=rho,
                             before_RMS_mV=float(np.sqrt(np.mean(before[:, module]**2))*noise_cfg['ADC_mV']),
                             pedestal_drift_mV=float(n[:, module].mean()), block_mean_RMS_mV=float(np.sqrt(np.mean(n[:, module].mean(1)**2))),
                             fixed_noise_mean_pC=float(q[:, module].mean()), fixed_noise_SD_pC=float(q[:, module].std()),
                             fixed_noise_RMS_pC=float(np.sqrt(np.mean(q[:, module]**2))),
                             fixed_noise_q01_pC=float(np.quantile(q[:, module], .01)), fixed_noise_q99_pC=float(np.quantile(q[:, module], .99)),
                             maximum_offdiagonal_correlation=float(np.max(abs(corr-np.eye(4))))))
    write_table(OUT/'noise_by_file_module.tsv', rows)
    previous_decoder_user = 0.
    for record in resources:
        cumulative = record['decoder_cumulative_user_s']
        record['decoder_user_s'] = cumulative-previous_decoder_user
        previous_decoder_user = cumulative
    write_table(OUT/'extraction_resources.tsv', resources)
    counts = np.bincount(assignment, minlength=504)
    summary = dict(data_events=504, files=9, runs=noise_cfg['runs'], nu_events=len(chosen), empty_signal_events=int((energy == 0).all(1).sum()),
                   nu_folds=np.bincount(fold).tolist(), noise_events_per_fold=np.bincount(data['noise_fold']).tolist(),
                   noise_reuse_min=int(counts.min()), noise_reuse_max=int(counts.max()), cross_fold_noise_reuse=False,
                   fixed_noise_RMS_pC_by_module=np.sqrt(np.mean(noise_charge**2, axis=0)).tolist(),
                   fixed_noise_mean_pC_by_module=noise_charge.mean(0).tolist(),
                   finite_outputs=all(np.isfinite(v).all() for v in outputs.values()),
                   zero_signal_all_receive_noise=bool(np.all(np.any(outputs['data_noise_nominal'][(energy == 0).all(1)] != 0, axis=1))),
                   no_noise_max_charge_error_pC=float(np.max(abs(signal_charge-signal.sum(2)*2/50))),
                   signal_charge_total_quantiles_pC=np.quantile(signal_charge.sum(1), [0, .5, .9, .99, 1]).tolist(),
                   event_status_counts={str(v): int(np.sum(data['status'] == v)) for v in np.unique(data['status'])},
                   trigger_bits_counts={str(v): int(np.sum(data['trigger_bits'] == v)) for v in np.unique(data['trigger_bits'])},
                   time_tag_difference_counts={str(v): int(np.sum((data['board_time_tag'][:,1]-data['board_time_tag'][:,0]) == v)) for v in np.unique(data['board_time_tag'][:,1]-data['board_time_tag'][:,0])},
                   bytes_read=sum(r['bytes_read'] for r in resources), wall_s=time.perf_counter()-tick, cpu_s=time.process_time()-cpu,
                   peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024, configuration=cfg)
    assert summary['finite_outputs'] and summary['zero_signal_all_receive_noise']
    (OUT/'response_audit.json').write_text(json.dumps(summary, indent=2)+'\n'); print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('mode', choices=['extract', 'build']); p.add_argument('--reader', type=Path)
    p.add_argument('--smoke', action='store_true'); a = p.parse_args()
    if a.mode == 'extract': extract(a.reader, a.smoke)
    else: build()
