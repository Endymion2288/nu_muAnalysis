"""Verify identical preprocessing definitions with float64 roundoff tolerance."""
import numpy as np


def compare_preprocessing(reference, candidate):
    assert reference.keys() == candidate.keys()
    assert reference['features'] == candidate['features']
    for key in ['target_center', 'target_spread']:
        assert reference[key] == candidate[key]
    assert reference['preprocessor'].keys() == candidate['preprocessor'].keys()
    result = {}
    for key, values in reference['preprocessor'].items():
        a = np.asarray(values)
        b = np.asarray(candidate['preprocessor'][key])
        assert np.isfinite(a).all() and np.isfinite(b).all()
        np.testing.assert_allclose(a, b, rtol=1e-14, atol=1e-14)
        result[key + '_max_abs_difference'] = float(np.max(abs(a - b)))
    return result
