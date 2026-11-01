#!/usr/bin/env python3
"""Conditional, explicitly synthetic synchronized pulses; original ADC is untouched."""
import json
import resource
import time
from pathlib import Path
import numpy as np
from report_calonu_native import crystalball
from calonu_weak_readout import template_weights

repo=Path(__file__).resolve().parents[1]; out=repo/'workbook/stage42_energy_ml'; cache=repo/'ntuples/energy_ml_stage42'
cfg=json.loads((repo/'ml/configs/calonu_information.json').read_text()); gate=json.loads((out/'C_gate.json').read_text())
assert gate['passed'],'No practical ideal signal gate: do not spend the conditional budget'
tick,cpu=time.perf_counter(),time.process_time()
with np.load(cache/'sensitive.npz') as z: energy=z['hit_energy_MeV']; rows=z['cache_row']
conditions=json.loads((repo/'workbook/stage37_energy_ml/conditions_audit.json').read_text())
digi=next(r['rows'][0]['payload'] for r in conditions['records'] if r['label']=='MC100049' and r['folder']=='/WAVE/Digitization')
pars={k:digi['cb_'+k] for k in ['norm','mean','sigma','alpha']}; pars['exponent']=digi['cb_n']
pars['mean']=cfg['synthetic_if_gate']['fixed_time_ns']
times=np.arange(760,912,2,dtype=float)
unit_ADC=crystalball(np.arange(12000)*.1,**pars).reshape(600,20).mean(1)[(times/2).astype(int)]
signal=energy[:,:,None]*unit_ADC[None,None,:]*(2/16.384)
rng=np.random.default_rng(cfg['seed']+100); noise=rng.normal(size=signal.shape)*cfg['synthetic_if_gate']['noise_ADC']*(2/16.384)
fixed,_=template_weights(times,pars)
nominal=signal+noise; pressure=signal+cfg['synthetic_if_gate']['pressure_noise_multiplier']*noise
fixed_nominal=nominal@fixed; fixed_double_noise=pressure@fixed
positive_nominal=np.maximum(nominal,0).sum(2)*2/50
legacy_zero_nominal=positive_nominal.copy(); empty=(energy==0).all(1); legacy_zero_nominal[empty]=0
values={}
for name in cfg['synthetic_if_gate']['candidates']:
    v=locals()[name]; values[name]=np.column_stack([v,v.sum(1)]).astype('float32')
metadata=dict(model='stage42 synchronized ideal integrated S plus Gaussian white noise, known pedestal; no digitization/saturation/time spread',
              events=len(rows),empty_events=int(empty.sum()),noise_ADC=cfg['synthetic_if_gate']['noise_ADC'],parameters=pars,times_ns=times.tolist(),
              signal_charge_pC_quantiles=np.quantile(signal.sum((1,2))*2/50,[0,.5,.9,.99,1]).tolist(),
              fixed_noise_RMS_pC=float((noise@fixed).std()),nominal_zero_signal_fixed_RMS_pC=float(fixed_nominal[empty].std()),
              uniform_zero_signal_nonzero=int(np.count_nonzero(fixed_nominal[empty])),replicas_per_event=1,
              no_noise_fixed_max_abs_error_pC=float(np.max(abs(signal@fixed-signal.sum(2)*2/50))),
              wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
assert metadata['no_noise_fixed_max_abs_error_pC']<1e-9
np.savez_compressed(cache/'synthetic.npz',cache_row=rows,**values,metadata_json=np.array(json.dumps(metadata)))
(out/'synthetic_response.json').write_text(json.dumps(metadata,indent=2)+'\n'); print(json.dumps(metadata))
