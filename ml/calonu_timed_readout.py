"""A single event time, four signed amplitudes and four constant baselines; no truth input."""
import numpy as np
from report_calonu_native import crystalball


def design(times, parameters, shift_ns=0.):
    pars = dict(parameters, mean=parameters['mean'] + shift_ns)
    fine = crystalball(np.arange(12000)*.1, **pars).reshape(600, 20).mean(axis=1)
    shape = fine[(np.asarray(times)/2).astype(int)]
    return shape/(shape.sum()*2/50)


def derivative_weights(times, parameters, step_ns=.1):
    shape = design(times, parameters)
    derivative = (design(times, parameters, step_ns)-design(times, parameters, -step_ns))/(2*step_ns)
    return np.linalg.pinv(np.column_stack([shape, derivative, np.ones(len(times))]))[0]


def bounded_time(wave, times, parameters, center_ns=0., bound_ns=4., step_ns=.25):
    """Least squares over a fixed time grid; signed amplitudes, no peak/quality/truth cut."""
    offsets = np.arange(-bound_ns, bound_ns+step_ns/2, step_ns)+center_ns
    shapes = np.array([design(times, parameters, shift) for shift in offsets])
    shapes -= shapes.mean(axis=1, keepdims=True)
    norm = np.sum(shapes**2, axis=1)
    products = np.asarray(wave, float) @ shapes.T
    score = np.sum(products**2, axis=-2)/norm
    chosen = np.argmax(score, axis=-1)  # Earliest time breaks exact ties.
    selected = np.take_along_axis(products, chosen[..., None, None], axis=-1)[..., 0]
    amplitudes = selected/norm[chosen][..., None]
    return dict(charge=amplitudes, time_shift_ns=offsets[chosen],
                at_boundary=(chosen == 0) | (chosen == len(offsets)-1))
