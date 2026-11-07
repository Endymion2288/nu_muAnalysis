"""Local Stage131 tabular I/O; all event arrays remain ignored."""
import csv
import json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage131_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage131';ART=ROOT/'ml/artifacts/stage131'
def load(path):
    with np.load(ROOT/path) as z:return {k:z[k] for k in z.files if k!='metadata_json'}
def table(name,rows):
    if not rows:return
    with (OUT/name).open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)),restval='NA',delimiter='\t',lineterminator='\n');w.writeheader();w.writerows({k:('NA' if v is None or v=='' else v) for k,v in r.items()} for r in rows)
def protocol():return json.loads((OUT/'production_contract.json').read_text())

def evaluation_masks(data):
    from stage119_curve_common import masks
    result=masks(data)
    for name,key in [('scint','status'),('calo','calo_status')]:
        status=data[key];known=np.isfinite(status)&(status>=0)
        result[name+'_nonzero_status']=np.any(known&(status!=0),axis=1)
        result[name+'_status_unknown']=np.any(~known,axis=1)
    return result
