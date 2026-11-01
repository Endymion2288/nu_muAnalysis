#!/usr/bin/env python3
"""Read back original identities, source/noise roles, responses and fit budget."""
import json
from pathlib import Path
import numpy as np


repo = Path(__file__).resolve().parents[1]; out = repo/'workbook/stage43_energy_ml'; cache = repo/'ntuples/energy_ml_stage43'
cfg = json.loads((repo/'ml/configs/calonu_data_noise.json').read_text())
with np.load(repo/'ntuples/energy_ml_stage42/development.npz') as z: d = {k: z[k] for k in z.files}
with np.load(cache/'data_noise.npz') as z: noise = {k: z[k] for k in z.files}
with np.load(cache/'response.npz') as z: response = {k: z[k] for k in z.files}
chosen = np.flatnonzero(d['selected']); folds = d['fold'][chosen]
assert d['x'].shape == (14309, 65) and len(chosen) == 3703
assert len(np.unique(d['group'][chosen])) == 21
assert len(noise['run']) == 504 and len(np.unique(noise['file_index'])) == 9
np.testing.assert_array_equal(response['cache_row'], chosen)
np.testing.assert_array_equal(response['eventID'], d['eventID'][chosen])
np.testing.assert_array_equal(noise['noise_fold'][response['noise_row']], folds)
for f in range(3):
    for other in range(f):
        assert not set(response['noise_row'][folds == f]) & set(response['noise_row'][folds == other])
for name in cfg['candidates']: assert response[name].shape == (3703, 5) and np.isfinite(response[name]).all()
with np.load(repo/'ntuples/energy_ml_stage42/sensitive.npz') as z: energy = z['hit_energy_MeV']
np.testing.assert_array_equal(response['ideal_sum'][:, :4], energy.astype('float32'))
np.testing.assert_array_equal(response['ideal_sum'][:, 4], energy.sum(1).astype('float32'))
empty = (energy == 0).all(1); assert empty.sum() == 644
np.testing.assert_array_equal(response['data_noise_nominal'][empty], response['data_noise_half_gain'][empty])
assert np.all(np.any(response['data_noise_nominal'][empty] != 0, axis=1))
fits = 0
for f in range(3):
    with np.load(repo/f'ml/artifacts/stage43/formal/{f}/predictions.npz') as z:
        m = json.loads(str(z['metadata_json']))
        assert m['config'] == cfg and m['fold'] == f and not m['smoke']
        np.testing.assert_array_equal(z['cache_row'], chosen[folds == f])
        assert len(m['records']) == 3 and [r['model'] for r in m['records']] == cfg['candidates']
        for r in m['records']:
            assert r['train_N'] == np.sum(folds == (f+1)%3) and r['calibration_N'] == np.sum(folds == (f+2)%3)
            assert r['evaluation_N'] == np.sum(folds == f) and r['columns'] == 70 and r['rounds'] == 400
            assert r['mapping_iterations'] is not None and r['wall_s'] < cfg['fit_wall_limit_s']
            for g in [f, (f+1)%3, (f+2)%3]:
                for h in range(g): assert not set(d['group'][chosen[folds == g]]) & set(d['group'][chosen[folds == h]])
            assert np.isfinite(z[r['model']]).all() and (z[r['model']] > 0).all()
            q = z['q_'+r['model']]; assert np.isfinite(q).all() and (q > 0).all()
            np.testing.assert_allclose(q.sum(1), 1, atol=1e-10); fits += 1
with np.load(cache/'predictions.npz') as z:
    np.testing.assert_array_equal(z['cache_row'], chosen)
    for k in ['eventID', 'run', 'group', 'truth_E_GeV']: np.testing.assert_array_equal(z[k], d[k][chosen])
with np.load(repo/'ml/artifacts/stage43/smoke/0/predictions.npz') as z:
    smoke = json.loads(str(z['metadata_json'])); assert smoke['smoke'] and len(smoke['records']) == 1
assert fits == 9 <= cfg['max_formal_fits']
assert json.loads((out/'native_pilot_validation.json').read_text())['valid']
summary = dict(valid=True, formal_completed_fits=fits, completed_smoke_fits=1, original_nu_events=3703, focus_events=int(((d['reco_p_GeV'][chosen] >= 100) & (d['reco_p_GeV'][chosen] < 1000)).sum()),
               F6_columns=65, retained_empty_signal_events=644, data_events=504, files=9, noise_cross_fold_reuse=False,
               source_roles_disjoint=True, original_event_identity_readback=True, all_predictions_finite=True,
               native_RAW_xAOD_algebra_valid=True, old_test_read=False, new_G4=False, new_Athena_reconstruction=False,
               aborted_startup='see submissions.json; migrated job raced allocation, no model/prediction output recovered; not counted as a completed fit')
(out/'final_validation.json').write_text(json.dumps(summary, indent=2)+'\n'); print(json.dumps(summary))
