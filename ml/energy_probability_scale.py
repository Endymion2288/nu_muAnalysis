"""Apply a frozen scalar scale to a log-energy Normal mixture.

The saved point prediction is authoritative: decoding float32 heads in float64
can change its last bits. Return that saved point unchanged, while preserving
the analytic mixture mean plus its previously fitted offset.
"""
import numpy as np


def mean_preserving_log_scale(weights, means, scales, offset, temperature,
                              saved_log_point):
    if not 0.5 <= temperature <= 3.0:
        raise ValueError('The Stage99 temperature contract is [0.5, 3].')
    center = np.sum(weights * means, axis=1)
    transformed_means = (center[:, None] + offset
                         + temperature * (means - center[:, None]))
    return (transformed_means, temperature * scales,
            np.array(saved_log_point, copy=True))
