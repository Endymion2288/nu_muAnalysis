"""Actual bounded calibration-input sentinel check; no retuning or new fit."""
import json
from pathlib import Path
import awkward as ak
import numpy as np
import uproot
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage177_energy_ml'
def check():
    p=json.loads((ROOT/'workbook/stage174_energy_ml/protocol.json').read_text());rows=[]
    for i,s in enumerate(p['sources']):
        keys=['longTracks','Track_pz0','Track_Chi2','Track_nDoF','Track_nLayers','Track_X_atTrig','Track_Y_atTrig','Track_ThetaX_atTrig','Track_ThetaY_atTrig']
        with uproot.open(s['path'],array_cache=None) as f:
            a=f['nt'].arrays(keys,entry_stop=4096);lead=ak.argmax(a.Track_pz0,axis=1,keepdims=True,mask_identity=True)
            def get(k):return ak.to_numpy(ak.fill_none(ak.firsts(a[k][lead]),np.nan))
            chi=get('Track_Chi2');x=get('Track_X_atTrig');y=get('Track_Y_atTrig')
            with np.load(ROOT/f'ntuples/energy_ml_stage174/full_{i}.npz') as old:
                control=old['control'];bad=control&(~np.isfinite(chi)|(chi<0)|(x==-999)|(y==-999))
                rows.append(dict(label=s['label'],original_N=len(control),original_control_N=int(control.sum()),negative_Chi2_N=int((chi<0).sum()),nonfinite_Chi2_N=int((~np.isfinite(chi)).sum()),
                    position_minus999_N=int(((x==-999)|(y==-999)).sum()),invalid_original_controls_N=int(bad.sum()),ROOT_read_bytes=int(f.file.source.num_requested_bytes)))
                assert not bad.any(),'Calibration controls contain nonphysical placeholders; suspend interpretation and correct calibration in separate frozen experiment'
    (OUT/'control_sentinel_validation.json').write_text(json.dumps(dict(passed=True,actual_sources=rows,calibrations_unchanged=True,no_global_negative_to_missing_rule=True,no_new_fits=True),indent=2)+'\n')
