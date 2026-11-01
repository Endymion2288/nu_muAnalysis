#!/usr/bin/env python3
"""Develop on already used stage39 controls, before freezing new native sources."""
import json
import resource
import time
from pathlib import Path
import numpy as np
from calonu_weak_readout import template_weights
from calonu_timed_readout import bounded_time, derivative_weights
from report_calonu_native import table

repo = Path(__file__).resolve().parents[1]
out = repo/'workbook/stage40_energy_ml/development'
out.mkdir(parents=True, exist_ok=True)
tick, cpu = time.perf_counter(), time.process_time()
cfg = json.loads((repo/'ml/configs/calonu_cc_waveform.json').read_text())
with np.load(repo/'ntuples/energy_ml_stage39/cc_waveform.npz') as z:
    d = {k:z[k] for k in z.files}
common = d['common_waveform']
cases = json.loads(str(d['cases_json']))
regular = np.array([c['role']=='regular' for c in cases])[common]
times = d['saved_time'][common][0, 0]
np.testing.assert_array_equal(d['saved_time'][common], np.broadcast_to(times, d['saved_time'][common].shape))
samples = np.broadcast_to((times/2).astype(int), d['saved_wave'][common].shape)
model = np.take_along_axis(d['signal_nominal_ADC'][common], samples, axis=2).astype(float)*(2/16.384)
target = model.sum(axis=(1, 2))*2/50
wave = d['saved_wave'][common]
off = d['baseline_mean'][common, :, None]-d['adc'][common, :, 100:176]*(2/16.384)
rows = []
for method in ['fixed', 'derivative', 'bounded_time']:
    for shift in [-2., 0., 2.]:
        pars = dict(cfg['template_parameters'], mean=cfg['template_parameters']['mean']+shift)
        def read(value):
            if method == 'bounded_time':
                return bounded_time(value, times, cfg['template_parameters'], center_ns=shift)['charge'].sum(axis=1)
            weights = (derivative_weights(times, pars) if method == 'derivative'
                       else template_weights(times, cfg['template_parameters'], shift)[1])
            return (value@weights).sum(axis=1)
        error = read(wave)-target
        high = regular & (target>=1)
        rel = (read(model)[high]-target[high])/target[high]
        rows.append(dict(method=method, center_shift_ns=shift, N=int(regular.sum()),
                         rmse_pC=float(np.sqrt(np.mean(error[regular]**2))), bias_pC=float(error[regular].mean()),
                         offpulse_RMS_pC=float(np.sqrt(np.mean(read(off)[regular]**2))), high_N=int(high.sum()),
                         model_high_relative_RMSE=float(np.sqrt(np.mean(rel**2))),
                         model_high_max_abs_relative_error=float(abs(rel).max()), high_bad_5pct=int(np.sum(abs(rel)>.05))))
table(out/'timing_methods.tsv', rows)
record = dict(input='stage39 already used controls; development only', selected_method='bounded_time',
              derivative_step_ns=.1, bound_ns=4., step_ns=.25,
              reason='Amplitude is almost orthogonal to a first time derivative: it does not correct the measured second-order amplitude loss; bounded waveform-residual fit addresses that loss.',
              methods_tried=3, further_method_scan=False, truth_used_for_fit=False,
              wall_s=time.perf_counter()-tick, cpu_s=time.process_time()-cpu,
              peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
(out/'summary.json').write_text(json.dumps(record, indent=2)+'\n')
print(json.dumps(record))
