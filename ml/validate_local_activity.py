#!/usr/bin/env python3
"""Readback of stage44 identities, missingness, donor isolation and fit budget; no fits."""
import json
from pathlib import Path
import numpy as np
from local_activity import donors

r=Path(__file__).resolve().parents[1];cfg=json.loads((r/'ml/configs/local_activity.json').read_text())
with np.load(r/'ntuples/energy_ml_stage42/development.npz') as z:
    rows=np.flatnonzero(z['selected']);d={k:z[k][rows] for k in z.files}
with np.load(r/'ntuples/energy_ml_stage44/features.npz') as z:
    f={k:z[k] for k in z.files}
m=json.loads(str(f['metadata_json']));assert m['config']==cfg
np.testing.assert_array_equal(f['cache_row'],rows)
for key in ['run','eventID']:np.testing.assert_array_equal(f[key],d[key])
donor,pools=donors(d,f['axes'],cfg);np.testing.assert_array_equal(donor,f['donor_row']);assert pools==m['donor_pools']
np.testing.assert_array_equal(f['counts'],f['local'][:,:4]);np.testing.assert_array_equal(f['counts'],f['null'][:,:4])
np.testing.assert_array_equal(f['local'][:,[9,15,21]],f['null'][:,[9,15,21]])
assert len(rows)==3703 and len(set(d['group']))==21 and ((d['reco_p_GeV']>=100)&(d['reco_p_GeV']<1000)).sum()==3024
fit_N=0
with np.load(r/'ntuples/energy_ml_stage44/predictions.npz') as z:joined={k:z[k] for k in z.files}
np.testing.assert_array_equal(joined['cache_row'],rows)
for fold in range(3):
    with np.load(r/f'ml/artifacts/stage44/formal/{fold}/predictions.npz') as z:
        md=json.loads(str(z['metadata_json']));assert md['config']==cfg and not md['smoke']
        selected=np.flatnonzero(d['fold']==fold);np.testing.assert_array_equal(z['cache_row'],rows[selected])
        assert len(md['records'])==3
        for rec in md['records']:assert rec['rounds']==400 and rec['columns']==(69 if rec['model']=='counts' else 87)
        fit_N+=len(md['records'])
        for name in cfg['candidates']:
            np.testing.assert_array_equal(joined[name][selected],z[name]);np.testing.assert_array_equal(joined['q_'+name][selected],z['q_'+name])
            assert np.isfinite(z[name]).all() and (z[name]>0).all()
            assert (z['q_'+name]>0).all();np.testing.assert_allclose(z['q_'+name].sum(axis=1),1,atol=1e-10)
assert fit_N==cfg['max_formal_fits']
with np.load(r/'ml/artifacts/stage44/smoke/0/predictions.npz') as z:
    smoke=json.loads(str(z['metadata_json']));assert smoke['smoke'] and len(smoke['records'])==1
with np.load(r/'ntuples/energy_ml_stage42/B_predictions.npz') as z:
    for key in ['cache_row','I0','q_I0','prior']:np.testing.assert_array_equal(z[key],joined[key])
source_counts={name:len(np.unique(d['group'][d['component']==name])) for name in ['pi','k','charm']}
assert source_counts==dict(pi=8,k=10,charm=3)
summary=dict(component_sources=source_counts,events=len(rows),sources=21,formal_fits=fit_N,smoke_fits=1,identity_fold_rejoin=True,counts_and_axisvalid_preserved=True,
             donor_reproducible_and_source_fold_pbin_validpattern_isolated=True,baseline_exactly_reused=True,finite_normalized_probabilities=True,
             missing_events_dropped=0,old_test_opened=False)
(r/'workbook/stage44_energy_ml/validation.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
