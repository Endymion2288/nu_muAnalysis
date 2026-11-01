#!/usr/bin/env python3
"""Fixed linear waveform readouts. HITS are deliberately absent from this interface."""
import numpy as np

from report_calonu_native import crystalball


def template_weights(times, parameters, shift_ns=0.):
    p = dict(parameters)
    p['mean'] += shift_ns
    fine = crystalball(np.arange(12000)*.1, **p).reshape(600,20).mean(axis=1)
    shape = fine[(np.asarray(times)/2).astype(int)]
    # Waveform is in mV; template amplitude is charge in pC within this window.
    shape = shape/(shape.sum()*2/50)
    fixed = shape/np.dot(shape,shape)
    centered = shape-shape.mean()
    free_baseline = centered/np.dot(centered,shape)
    assert abs(free_baseline.sum()) < 1e-13
    return fixed, free_baseline


def evaluate(wave, adc, baseline, rms, times, parameters):
    fixed, free = template_weights(times, parameters)
    off = baseline[:,None]-adc[:,100:176]*(2/16.384)
    outputs = {}
    for name, weights in [('signed_saved', np.full(76,2/50)),
                          ('template_fixed_baseline',fixed), ('template_plus_constant',free)]:
        outputs[name] = dict(charge=wave@weights, offpulse=off@weights,
                             shifted_plus=(wave+rms[:,None])@weights,
                             shifted_minus=(wave-rms[:,None])@weights)
    outputs['positive_raw'] = dict(charge=np.maximum(wave,0).sum(axis=1)*2/50,
                                   offpulse=np.maximum(off,0).sum(axis=1)*2/50,
                                   shifted_plus=np.maximum(wave+rms[:,None],0).sum(axis=1)*2/50,
                                   shifted_minus=np.maximum(wave-rms[:,None],0).sum(axis=1)*2/50)
    for shift in [-2.,2.]:
        _, weight = template_weights(times,parameters,shift)
        outputs[f'template_time_{int(shift):+d}ns'] = dict(charge=wave@weight,offpulse=off@weight,
                                                       shifted_plus=(wave+rms[:,None])@weight,
                                                       shifted_minus=(wave-rms[:,None])@weight)
    return outputs
