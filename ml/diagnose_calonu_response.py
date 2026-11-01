#!/usr/bin/env python3
"""Describe frozen fit boundaries and time-fit cost; do not change the chosen estimator."""
import json
import resource
import time
from pathlib import Path
import numpy as np
from calonu_timed_readout import bounded_time
from calonu_weak_readout import template_weights
from report_calonu_native import table
repo=Path(__file__).resolve().parents[1];out=repo/'workbook/stage40_energy_ml'
cfg=json.loads((repo/'ml/configs/calonu_response.json').read_text());tick,cpu=time.perf_counter(),time.process_time()
with np.load(repo/'ntuples/energy_ml_stage40/response.npz') as saved:d={k:saved[k] for k in saved.files}
cases=json.loads(str(d['cases_json']));regular=np.array([c['role']=='regular' for c in cases]);common=d['common_waveform'];signal=d['nominal_window_charge_pC']
rows=[]
for label,mask in [('regular_weak',regular&common&(signal<1)),('regular_high',regular&common&(signal>=1)),
                   ('diagnostic_weak',~regular&common&(signal<1)),('diagnostic_high',~regular&common&(signal>=1))]:
    shift=d['time_shift_bounded_time'][mask];charge=d['readout_bounded_time'][mask]
    rows.append(dict(subset=label,N=int(mask.sum()),time_on_boundary=int((abs(shift)==cfg['bound_ns']).sum()),
                     negative_total_readout=int((charge<0).sum()),median_time_ns=float(np.median(shift)),
                     max_abs_time_ns=float(abs(shift).max())))
table(out/'time_fit_diagnostics.tsv',rows)
wave=d['saved_wave'][common];times=d['saved_time'][common][0,0];weights=template_weights(times,cfg['template_parameters'])[1]
bench=[]
for method in ['fixed','bounded_time']:
    # Fixed number of batch repeats, used only to measure compute cost on the same retained support.
    start=time.perf_counter();startcpu=time.process_time()
    for repeat in range(10):
        charge=(wave@weights if method=='fixed' else bounded_time(wave,times,cfg['template_parameters'],bound_ns=cfg['bound_ns'],step_ns=cfg['step_ns'])['charge'])
    elapsed=time.perf_counter()-start;CPU=time.process_time()-startcpu
    bench.append(dict(method=method,batch_events=len(wave),repeats=10,total_event_evaluations=10*len(wave),wall_s=elapsed,CPU_s=CPU,
                      wall_us_per_event=elapsed/(10*len(wave))*1e6,finite=bool(np.isfinite(charge).all()),
                      note='Fixed weights precomputed; bounded implementation includes 33 template designs per batch; single CPU thread'))
table(out/'inference_cost.tsv',bench)
(out/'diagnostics_summary.json').write_text(json.dumps(dict(wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,
    peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,post_confirmation_descriptive_only=True,
    truth_used_for_estimator=False,estimator_changed=False),indent=2)+'\n')
print(rows);print(bench)
