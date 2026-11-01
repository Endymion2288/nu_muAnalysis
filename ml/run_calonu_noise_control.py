#!/usr/bin/env python3
"""Run synthetic source-function noise controls; never fill missing observed ADCs."""
import argparse
import json
import resource
import time
from pathlib import Path
import numpy as np
import ROOT
from calonu_timed_readout import bounded_time
from calonu_weak_readout import template_weights

p=argparse.ArgumentParser(); p.add_argument('--smoke',action='store_true');p.add_argument('--output',type=Path,required=True)
a=p.parse_args(); repo=Path(__file__).resolve().parents[1]
cfg=json.loads((repo/'ml/configs/calonu_response.json').read_text())
tick,cpu=time.perf_counter(),time.process_time()
ROOT.gErrorIgnoreLevel=ROOT.kError
ROOT.TH1.AddDirectory(False)
assert ROOT.gInterpreter.Declare((repo/'workbook/stage40_energy_ml/source_control.cxx').read_text())
events=8 if a.smoke else cfg['source_noise_events'];pairs=2 if a.smoke else cfg['source_zero_hist_pairs']
adc=np.asarray(list(ROOT.Stage40NoiseEvents(events,cfg['source_noise_seed'])),dtype=np.uint16).reshape(events,4,600)
mismatches=int(ROOT.Stage40ZeroHistogramPairs(pairs,cfg['source_noise_seed']))
times=np.arange(780,932,2); wave=(15650-adc[:,:,390:466].astype(float))*(2/16.384)
fixed=template_weights(times,cfg['template_parameters'])[1]
readouts=dict(signed=wave.sum(axis=(1,2))*2/50, fixed=(wave@fixed).sum(1),
              bounded=bounded_time(wave,times,cfg['template_parameters'],bound_ns=cfg['bound_ns'],step_ns=cfg['step_ns'])['charge'].sum(1),
              positive=np.maximum(wave,0).sum(axis=(1,2))*2/50)
expected_rms=float(np.sqrt(3**2+1/12))
record=dict(scope='Synthetic source-function fixture; not observed missing events or full Athena production',
            events=events,channels=4,samples_per_channel=600,ADC_samples=int(adc.size),seed=cfg['source_noise_seed'],
            ROOT_version=ROOT.gROOT.GetVersion(),ADC_mean=float(adc.mean()),ADC_RMS=float(adc.std()),
            ADC_expected_mean=15650.,ADC_expected_RMS=expected_rms,
            zero_histogram_pairs=pairs,zero_histogram_channel_mismatches=mismatches,
            exact_ideal_zero_events=int(np.sum(np.all(adc==15650,axis=(1,2)))),
            readouts={k:dict(bias_pC=float(v.mean()),RMS_pC=float(np.sqrt(np.mean(v**2))),
                            R68_pC=float((np.quantile(v,.84)-np.quantile(v,.16))/2)) for k,v in readouts.items()},
            source_noise_gate=bool(mismatches==0 and abs(adc.mean()-15650)<cfg['gates']['source_noise_ADC_mean_tolerance']
                and abs(adc.std()/expected_rms-1)<cfg['gates']['source_noise_ADC_RMS_relative_tolerance']),
            wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,
            peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
a.output.parent.mkdir(parents=True,exist_ok=True)
a.output.with_suffix('.json').write_text(json.dumps(record,indent=2)+'\n')
np.savez_compressed(a.output,**readouts)
with np.load(a.output) as z:
    for k,v in readouts.items():np.testing.assert_array_equal(z[k],v)
print(json.dumps(record))
