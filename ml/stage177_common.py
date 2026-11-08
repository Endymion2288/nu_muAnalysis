"""Reuse the original fixed trainer and exact original evaluator without changing policy."""
import json
from pathlib import Path
import numpy as np
import stage129_energy as energy
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage177_energy_ml';ART=ROOT/'ml/artifacts/stage177'
energy.OUT=OUT;energy.ART=ART
load=energy.load

def inputs():
    d=load(ROOT/'ntuples/energy_ml_stage119/old_input.npz');a=load(ROOT/'ntuples/energy_ml_stage175/cohort.npz')
    np.testing.assert_array_equal(a['row'],np.arange(len(d['role'])));np.testing.assert_array_equal(a['role'],d['role'])
    assert not np.isfinite(a['relative_mean_ns'][~a['flags'][:,1],0]).any() and not np.isfinite(a['relative_mean_ns'][~a['flags'][:,3],1]).any()
    base=energy.configuration()['features'];flags=['Timing01_reference_strict','Timing01_mu_range','Timing23_reference_strict','Timing23_mu_range'];names=base+flags
    arrays=dict(X=d['x'],V=np.column_stack([d['x'],a['flags']]).astype('float32'),T=np.column_stack([d['x'],a['flags'],a['relative_mean_ns']]).astype('float32'))
    labels=dict(X=base,V=names,T=names+['Timing01_calibrated_relative_mean_ns','Timing23_calibrated_relative_mean_ns'])
    return d,arrays,labels

def write(name,obj):(OUT/name).write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')
