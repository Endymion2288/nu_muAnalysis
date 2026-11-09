"""Fixed all-flux schema, text products and energy bins."""
import csv
import json
import os
import resource
import time
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
DATA_ROOT=Path(os.environ.get('NU_MU_STAGE199_DATA_ROOT',str(ROOT)))
OUT=ROOT/'workbook/stage199_energy_ml'
CACHE=ROOT/'ntuples/energy_ml_stage199'
ART=ROOT/'ml/artifacts/stage199'


def load(path):
    with np.load(path) as z:return {k:z[k] for k in z.files if k!='metadata_json'}


def save(name,value):
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def table(name,rows):
    with (OUT/name).open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)),delimiter='\t',lineterminator='\n')
        w.writeheader();w.writerows(rows)


def resources(tick,cpu):
    return dict(CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,
                peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


def bins(e):
    edges=json.loads((OUT/'protocol.json').read_text())['weights']['edges_GeV']
    b=np.searchsorted(edges,np.asarray(e),side='right')-1
    assert ((b>=0)&(b<8)).all()
    return b


def masks(d):
    e,p,y=d['truth_E_GeV'],d['pz'],d['y_lepton']
    valid=d['primary_valid']&np.isfinite(y)&(y>=0)&(y<1)
    out=dict(all=np.ones(len(e),bool),E50_100=(e>=50)&(e<100),E100_200=(e>=100)&(e<200),
        E200_inf=e>=200,pz50_100=(p>=50)&(p<100),pz50_100_trueE200=(p<100)&(e>=200),
        high_y=valid&(y>=.8),unconfirmed=~d['confirmed'],input_missing=d['input_missing'],
        fit_failure=d['fit_failure'],negative_valid_raw=d['negative_valid_raw'])
    for lo,hi in [(200,400),(400,800),(800,1600),(1600,3200),(3200,6400)]:out[f'E{lo}_{hi}']=(e>=lo)&(e<hi)
    out['E6400_inf']=e>=6400
    return out
