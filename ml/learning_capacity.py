"""Stage50 full existing F6 development support, fixed source roles and candidates."""
import json
from pathlib import Path
import numpy as np

REPO=Path(__file__).resolve().parents[1]
CACHE=REPO/'ntuples/energy_ml_stage50'
OUT=REPO/'workbook/stage50_energy_ml'


def configuration():return json.loads((REPO/'ml/configs/learning_capacity.json').read_text())


def load_inputs():
    with np.load(REPO/'ntuples/energy_ml_stage42/development.npz') as z:d={k:z[k] for k in z.files}
    assert d['x'].shape==(14309,65) and d['selected'].sum()==3703 and len(set(d['group']))==81
    x=d['x'].astype('float32').copy();x[~np.isfinite(x)]=np.nan
    assert np.isfinite(d['truth_E_GeV']).all() and (d['truth_E_GeV']>0).all() and np.isfinite(d['vertex_z_mm']).all()
    return d,x


def candidates(x,d):
    z=np.column_stack([x,d['vertex_z_mm']]).astype('float32')
    return dict(L3_F6z=(z,3),L5_F6=(x,5),L5_F6z=(z,5))


def formal_output(f,d):
    """Use a live fold shard or its archived metadata and single merged prediction copy."""
    path=REPO/f'ml/artifacts/stage50/formal/{f}'
    if (path/'predictions.npz').exists():
        with np.load(path/'predictions.npz') as z:return {k:z[k] for k in z.files}
    md=json.loads((path/'metadata.json').read_text());record=md['records'][0]
    roles={key:np.flatnonzero(np.isin(d['group'],record[role+'_sources'])) for key,role in
           [('cache_row','evaluation'),('train_cache_row','train'),('cal_cache_row','calibration')]}
    with np.load(CACHE/'predictions.npz') as z:
        values={r['model']:z[r['model']][roles['cache_row']] for r in md['records']}
    return dict(roles,**values,metadata_json=np.array(json.dumps(md)))
