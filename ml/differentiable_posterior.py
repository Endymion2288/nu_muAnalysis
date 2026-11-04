"""Adaptive raw log-energy density and a CPU, first-order PyTorch VJP.

The integrated Gaussian score gives the derivative of a mixture likelihood.
Adaptive partitions are numerical devices, not model parameters. Derivatives
are integrals of analytic distribution scores, not derivatives of the solver.
Only head and shared b/T derivatives are supported; observations are fixed.
"""
import math

import numpy as np
from scipy.integrate import quad_vec
from scipy.special import expit, logsumexp, ndtr

from posterior_numerics import M, LOG2PI, decode


def value_gradient(head, log_energy, pz, b=0., T=1.):
    """Return raw log density, 15 head + b/T gradient, and error diagnostics.

    Float64, eps=1e-10, standardized s truncation >=10 sigma, and the same
    narrow-response split locations as stage88. Error estimates on integrated
    scores and the density tail bound are recorded separately: the latter is
    not claimed to bound gradient tails. Certification is empirical against
    independently perturbed stage88 integrals at the audited parameter points.
    """
    q = np.asarray(head, dtype=float).reshape(5, 3)
    weights, mr, ms, sr, ss = [a[0] for a in decode(q.reshape(1, 15), b, T)]
    sigmoid = expit(q)
    dsr = 4.95 * sigmoid[3] * (1 - sigmoid[3]) * T
    dss = 4.95 * sigmoid[4] * (1 - sigmoid[4])
    components = []
    errors = []
    tails = []
    evaluations = 0
    flags = 0
    for k in range(3):
        a, width = (0., .1) if k == 0 else (.1, .9)
        logbound = np.logaddexp(0., math.log(M / pz) - mr[k] + .5 * sr[k] ** 2) - math.log(sr[k]) - .5 * LOG2PI
        limit = 10
        while math.log(2 * ndtr(-limit)) + max(0., logbound) > math.log(1e-11):
            limit += 1
            assert limit <= 16, 'density tail bound not certified'
        tails.append(2 * ndtr(-limit) * max(1., math.exp(logbound)))
        points = []
        for r in [mr[k] + j * sr[k] for j in [-9, -5, -2, 0, 2, 5, 9]] + [-np.inf]:
            logmu = np.logaddexp(math.log(M), math.log(pz) + r)
            u = (-math.expm1(min(700., logmu - log_energy)) - a) / width
            if 0 < u < 1:
                points.append((math.log(u) - math.log1p(-u) - ms[k]) / ss[k])

        def integrand(x):
            s = ms[k] + ss[k] * x
            logone = math.log(.9 + .1 * expit(-s)) if k == 0 else math.log(.9) - np.logaddexp(0., s)
            logmu = log_energy + logone
            delta = math.exp(logmu) - M
            if delta <= 0:
                return np.zeros(6)
            r = math.log(delta / pz)
            t = (r - mr[k]) / sr[k]
            density = math.exp(-.5 * (t * t + x * x) - math.log(sr[k]) - LOG2PI + logmu - math.log(delta))
            # s is held fixed for Gaussian score differentiation. Changing
            # variables to standardized x afterwards does not add path terms.
            score = np.array([1., t / sr[k], x / ss[k],
                              (t * t - 1) / sr[k] * dsr[k],
                              (x * x - 1) / ss[k] * dss[k], (t * t - 1) / T])
            return density * score

        points = sorted(set(x for x in points if -limit < x < limit))
        value, error, info = quad_vec(integrand, -limit, limit, points=points,
            epsabs=1e-10, epsrel=1e-10, limit=400, norm='max', full_output=True)
        components.append(value)
        errors.append(float(error))
        evaluations += int(info.neval)
        flags += int(not info.success)
    values = np.asarray(components)
    density = float(weights @ values[:, 0])
    assert density > 0 and np.isfinite(values).all()
    responsibility = weights * values[:, 0] / density
    gradient = np.zeros((5, 3))
    gradient[0] = responsibility - weights
    for j in range(1, 5):
        gradient[j] = weights * values[:, j] / density
    gb = float(gradient[1].sum())
    gT = float(weights @ values[:, 5] / density)
    g = np.r_[gradient.ravel(), gb, gT]
    assert np.isfinite(g).all()
    return math.log(density), g, dict(vector_quad_error=float(weights @ errors),
        density_tail_bound=float(weights @ tails), integrand_evaluations=evaluations,
        precision_flags=flags, gradient_tail_bound='not analytically certified; two-step FD checked at audited points')


def log_energy_density(head, log_energy, pz, b, T):
    """First-order CPU float64 VJP; no observation or higher-order gradients."""
    import torch
    from torch.autograd.function import once_differentiable

    class AdaptiveDensity(torch.autograd.Function):
        @staticmethod
        def forward(ctx, v, z, p, shift, temperature):
            assert v.dtype == torch.float64 and v.device.type == 'cpu'
            assert not z.requires_grad and not p.requires_grad
            assert shift.numel() == temperature.numel() == 1
            results = [value_gradient(h, float(zz), float(pp), float(shift), float(temperature))
                       for h, zz, pp in zip(v.detach().numpy(), z.detach().numpy(), p.detach().numpy())]
            ctx.save_for_backward(torch.tensor(np.stack([r[1] for r in results]), dtype=v.dtype))
            return torch.tensor([r[0] for r in results], dtype=v.dtype)

        @staticmethod
        @once_differentiable
        def backward(ctx, upstream):
            gradient, = ctx.saved_tensors
            scaled = upstream[:, None] * gradient
            return scaled[:, :15], None, None, scaled[:, 15].sum(), scaled[:, 16].sum()

    return AdaptiveDensity.apply(head, log_energy, pz, b, T)
