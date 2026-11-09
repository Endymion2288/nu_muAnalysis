"""Check relaxed Python selections against native C++ and audit all residual inputs."""
import json
import tempfile
import time

import awkward as ak
import numpy as np
import yaml

from stage200_vertex import ROOT, OUT, CACHE, box, masks, native, save


def main():
    start = time.perf_counter()
    with np.load(CACHE / 'vertices.npz') as z:
        d = {k: z[k] for k in z.files}
    protocol = json.loads((OUT / 'protocol.json').read_text())
    source = next(s for s in protocol['sources'] if s['index'] == 4)
    checks = []
    for truth in [100, np.inf]:
        config = yaml.safe_load((OUT / 'standard_cuts.yaml').read_text())
        config['Cuts']['Track R at max radius < 95 mm']['expression'] = 'LeadTrack_r_atMaxRadius < 110'
        config['Cuts']['Track R at IFT < 95 mm']['expression'] = 'LeadTrack_rIFT < 110'
        config['Cuts']['Track rVetoNu < 120 mm']['expression'] = 'LeadTrack_rVetoNu < 140'
        if np.isinf(truth):
            config['Cuts']['Truth dec r < 100 mm']['expression'] = 'std::isfinite(truth_dec_r)'
        with tempfile.TemporaryDirectory(prefix='vertex200_qa_') as name:
            from pathlib import Path
            tmp = Path(name)
            cuts = tmp / 'relaxed.yaml'
            cuts.write_text(yaml.safe_dump(config, sort_keys=False))
            a, command = native(source, tmp, cuts, ['run', 'eventID'])
            expected = d['eventID'][(d['source'] == 4) & masks(d, truth=truth, rmax=110, ift=110, vetonu=140)]
            np.testing.assert_array_equal(np.sort(ak.to_numpy(a.eventID)), np.sort(expected))
            checks.append(dict(truth_r_mm=100 if truth == 100 else 'none', native_N=len(a),
                               event_sets_exact=True, command=command))
    selected = masks(d)
    coords = ['vetonu_x', 'vetonu_y', 'veto1_x', 'veto1_y']
    invalid = {k: int((selected & (~np.isfinite(d[k]) | (d[k] == 999999))).sum()) for k in coords}
    assert not any(invalid.values()), invalid
    for axis in 'xy':
        avg = (d['vetonu_' + axis] + d['veto1_' + axis]) / 2 - d[axis]
        separate = ((d['vetonu_' + axis] - d[axis]) + (d['veto1_' + axis] - d[axis])) / 2
        np.testing.assert_allclose(avg[selected], separate[selected], atol=3e-14, rtol=1e-12)
    assert np.all(d['raw_xy'].sum(axis=1) == d['raw_x'])
    assert np.all(d['raw_xy'].sum(axis=0) == d['raw_y'])
    assert np.all(d['raw_zx'].sum(axis=1) == d['raw_z'])
    assert np.all(d['raw_zy'].sum(axis=1) == d['raw_z'])
    groups = {}
    for name, m in [('box', selected & box(d['x'], d['y'], d['z'])), ('box_or_lead', selected)]:
        groups[name] = dict(selected_N=int(m.sum()), primary_valid_N=int((m & (d['primary_candidates'] == 1)).sum()),
                            confirmed_N=int((m & d['confirmed']).sum()),
                            theta_below_minus30_mrad_N=int((m & (d['theta'] - d['truth_theta'] < -30)).sum()),
                            theta_above30_mrad_N=int((m & (d['theta'] - d['truth_theta'] > 30)).sum()),
                            unique_source_event_N=len(np.unique(np.column_stack([d['source'][m], d['eventID'][m]]), axis=0)))
    save(OUT / 'independent_validation.json', dict(passed=True, relaxed_native=checks,
         invalid_or_sentinel_standard_position_N=invalid, groups=groups,
         raw_projection_conservation=True, average_residual_identity=True, wall_s=time.perf_counter()-start,
         geometry_source='Calypso d32b0ff3, PhysicsAnalysis/NtupleDumper/src/NtupleDumperAlg.cxx:1909,1923',
         plane_z_mm=dict(VetoNu=-3112, Veto1=-1769.65, average=-2440.825)))
    print(json.dumps(groups), flush=True)


if __name__ == '__main__':
    main()
