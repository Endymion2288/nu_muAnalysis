"""Stage47 same-event X87 plus saved ordinary Ecal sensitive deposits."""
import json
import numpy as np
from coarse_depth import REPO, load_inputs


def load_sensitive():
    rows,d,x=load_inputs()
    with np.load(REPO/'ntuples/energy_ml_stage47/sensitive.npz') as z:
        for key in ['run','eventID','group','fold']:
            np.testing.assert_array_equal(z[key],d[key])
        np.testing.assert_array_equal(z['cache_row'],rows)
        assert json.loads(str(z['metadata_json']))['hit_ids']==[0,8,2,10]
        sensitive=z['hit_energy_MeV'].astype(float)/1000
    assert sensitive.shape==(3703,4) and np.isfinite(sensitive).all() and (sensitive>=0).all()
    candidates=dict(ordinary_calo=np.column_stack([x,sensitive]).astype('float32'),
                    ordinary_calo_z=np.column_stack([x,sensitive,d['vertex_z_mm']]).astype('float32'))
    return rows,d,candidates
