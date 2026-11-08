"""Independent scalar/basis checks and overlap validation, in a batch worker."""
import gzip
import json
import math
from fractions import Fraction
from pathlib import Path

import numpy as np
from stage188_review import summarize, write

ROOT = Path.cwd()
OUT = ROOT / 'workbook/stage188_energy_ml'
CACHE = ROOT / 'ntuples/energy_ml_stage188'
P = json.loads((OUT / 'protocol.json').read_text())


def read(phase):
    with gzip.open(CACHE / f'{phase}_native.json.gz', 'rt') as f:
        return json.load(f)


def main():
    phases = [phase for phase in ['pilot', 'full'] if (CACHE / f'{phase}_native.json.gz').exists()]
    assert phases
    checks, rows, source_roundtrip, propagated_roundtrip = 0, [], [], []
    for phase in phases:
        data, summary = summarize(phase)
        assert len(data['records']) == sum(min(P['pilot_per_source'], len(s['cases'])) if phase=='pilot' else len(s['cases']) for s in P['sources'])
        for r in data['records']:
            m, case = r['measurement'], r['case']
            source = next(s for s in P['sources'] if s['label']==case['label'])
            expected = next(c for c in source['cases'] if c['entry']==case['entry'])
            assert all(case[k]==v for k,v in expected.items())
            if source['index']>=0:
                assert case['role']==1
            if not m['start_supported']:
                continue
            lead, basis = m['leading'], m['source']
            assert 0 not in lead['fitted_stations']
            cov = np.asarray(lead['stored_covariance'])
            acts_cov = np.asarray(basis['ACTS_covariance'])
            scale = np.diag([1.,1.,1.,1.,1000.])
            np.testing.assert_allclose(acts_cov[:5,:5], scale@cov@scale, rtol=3e-16, atol=0.)
            tr = np.asarray(basis['ACTS_transform'])
            native_tr = np.asarray(basis['Trk_measurement_transform'])
            np.testing.assert_allclose(tr, native_tr, rtol=0, atol=1e-8)
            original = np.asarray(lead['position_mm'])
            reconstructed = tr@np.r_[basis['local_mm'],0.,1.]
            error = float(np.linalg.norm(reconstructed[:3]-original))
            assert error<=1e-6
            par = np.asarray(basis['ACTS_parameters']).ravel()
            if basis.get('propagation_roundtrip_success'):
                propagated = np.asarray(basis['propagation_roundtrip_parameters']).ravel()
                propagated_roundtrip.append(float(np.max(abs(propagated[:5]-par[:5]))))
            phi, theta = par[2:4]
            mom = np.asarray(lead['momentum_MeV'])
            expected_mom = abs(1000./par[4])*np.array([math.cos(phi)*math.sin(theta),math.sin(phi)*math.sin(theta),math.cos(theta)])
            np.testing.assert_allclose(expected_mom,mom,rtol=1e-12,atol=1e-8)
            source_roundtrip.append(error)
            for w in m['wafers']:
                assert w['layer'] in [0,1,2] and w['side'] in [0,1]
                for c in w['candidates']:
                    assert c['strips']
                    if 'residual_mm' not in c:
                        continue
                    if c['residual_mm'] is None or c['innovation_variance_mm2'] is None:
                        assert c.get('pull') is None
                        continue
                    u = Fraction(c['u_mm'])
                    pred = Fraction(w['parameters'][0][0])
                    v = Fraction(c['variance_mm2'])
                    C = Fraction(w['covariance'][0][0])
                    assert float(u-pred)==c['residual_mm']
                    assert float(v+C)==c['innovation_variance_mm2']
                    S = c['innovation_variance_mm2']
                    if 'pull' in c:
                        p = c['residual_mm']/math.sqrt(S)
                        assert p==c['pull']
                    checks += 1
            rows.append(dict(phase=phase,label=case['label'],entry=case['entry'],source_representation_roundtrip_mm=error))
    prefix_exact = None
    if 'full' in phases:
        p = read('pilot')['records']
        full = {(r['case']['label'],r['case']['entry']):r for r in read('full')['records']}
        for r in p:
            other = full[(r['case']['label'],r['case']['entry'])]
            assert r['measurement']==other['measurement']
            assert r['original_leading_match']==other['original_leading_match']
        prefix_exact = len(p)
    write('independent_validation.json',dict(passed=True,phases=phases,scalar_residual_variance_pull_checks_N=checks,
        source_representation_checks_N=len(rows),max_source_roundtrip_mm=max(source_roundtrip,default=None),
        pilot_full_exact_N=prefix_exact,source_covariance_inverse_units_checked=True,
        actual_ACTS_native_measurement_frames_checked=True,all_candidates_retained=True,
        source_propagation_roundtrip_success_N=len(propagated_roundtrip),
        source_propagation_roundtrip_max_abs_parameter_difference=max(propagated_roundtrip,default=None),
        source_propagation_roundtrip_note='Mixed-unit diagnostic only; source representation closure is separately checked. Empty propagation is retained, not replaced by an identity.',
        calibrated_association_error_rate=None,independent_real_data_pull_coverage=None,
        limits='Scalar audit does not independently certify the ACTS transport algorithm or producer covariance coverage; no smoothed residual labeled independent pull.',
        overall_complete=False,promotion=False))
    print('AUDIT',len(rows),checks,prefix_exact,flush=True)


if __name__=='__main__':
    main()
