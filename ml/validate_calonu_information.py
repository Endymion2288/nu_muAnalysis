#!/usr/bin/env python3
"""Read back the joined summaries, independent fold roles and finite predictions."""
import json
from pathlib import Path
import numpy as np

repo=Path(__file__).resolve().parents[1]; out=repo/'workbook/stage42_energy_ml'; cache=repo/'ntuples/energy_ml_stage42'
cfg=json.loads((repo/'ml/configs/calonu_information.json').read_text())
with np.load(cache/'development.npz') as z: d={k:z[k] for k in z.files}
assert d['x'].shape==(14309,65) and d['selected'].sum()==3703
assert len(np.unique(d['group']))==81 and len(np.unique(d['group'][d['selected']]))==21
feature_names=json.loads((out/'preparation.json').read_text())['feature_names']
assert len(feature_names)==65 and not any('truth' in k.lower() or k in ['run','eventID','group','component'] for k in feature_names)
for g in np.unique(d['group']): assert len(np.unique(d['fold'][d['group']==g]))==1
with np.load(cache/'sensitive.npz') as z:
    np.testing.assert_array_equal(z['cache_row'],np.flatnonzero(d['selected']))
    assert np.isfinite(z['hit_energy_MeV']).all() and (z['hit_energy_MeV']>=0).all()
    np.testing.assert_array_equal(z['eventID'],d['eventID'][d['selected']])
fits=0; models={}; gate=json.loads((out/'C_gate.json').read_text())
for part in ['A','B']+(['C'] if gate['passed'] else []):
    with np.load(cache/f'{part}_predictions.npz') as z:
        expected=np.arange(len(d['x'])) if part=='A' else np.flatnonzero(d['selected'])
        np.testing.assert_array_equal(z['cache_row'],expected)
        for k in ['run','eventID','group','truth_E_GeV']: np.testing.assert_array_equal(z[k],d[k][expected])
        for k in z.files:
            if k.startswith('q_'): assert np.isfinite(z[k]).all() and (z[k]>0).all(); np.testing.assert_allclose(z[k].sum(1),1,atol=1e-10)
    measured=[]
    for f in range(3):
        with np.load(repo/f'ml/artifacts/stage42/{part}/{f}/predictions.npz') as z: m=json.loads(str(z['metadata_json']))
        assert m['config']==cfg and not m['smoke'] and m['fold']==f
        select=np.ones(len(d['x']),bool) if part=='A' else d['selected']
        counts=[int(((d['fold']==j)&select).sum()) for j in range(3)]
        for r in m['records']:
            assert r['columns']=={'A0':65,'A_zero':66,'A_readout':70,'I0':65,'Iz':66,'Is':69,'Isz':70}.get(r['model'],70)
            with np.load(cache/f'{part}_predictions.npz') as z:
                assert np.isfinite(z[r['model']]).all() and (z[r['model']]>0).all()
            assert r['rounds']==cfg['rounds'] and r['train_N']==counts[(f+1)%3] and r['calibration_N']==counts[(f+2)%3] and r['evaluation_N']==counts[f]
            assert r['scalar_mapping_measured'] and r['wall_s']<cfg['fit_wall_limit_s']
            measured.append(r['model']); fits+=1
    models[part]=sorted(set(measured))
assert fits<=cfg['max_formal_fits']
summary=dict(valid=True,A_events=14309,B_events=3703,B_sources=21,F6_columns=65,formal_fits=fits,smoke_fits=2,
             C_triggered=gate['passed'],models=models,source_roles_disjoint=True,all_predictions_finite=True,
             compact_summaries_readback=True,old_test_read=False,no_new_G4=True)
(out/'final_validation.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
