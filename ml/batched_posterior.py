"""Stage91 fixed segmented GL32 score likelihood, CPU/CUDA float64 integral.

Nodes are numerical partitions of the same standardized-s integral as stage90.
The VJP uses integrated analytic distribution scores; no derivative of adaptive
partition construction, no observation derivatives, and no higher derivatives.
"""
import math
from functools import lru_cache

import numpy as np
import torch
from torch.autograd.function import once_differentiable
from scipy.special import log_ndtr

M = .1056583755
LOG2PI = math.log(2 * math.pi)


@lru_cache(maxsize=8)
def constants(device):
    x, w = np.polynomial.legendre.leggauss(32)
    make = lambda v: torch.as_tensor(v, dtype=torch.float64, device=device)
    return make(x), make(w), make(np.arange(10, 17)), make(math.log(2) + log_ndtr(-np.arange(10, 17)))


def value_gradient(head, log_energy, pz, b, T):
    """All inputs on one device; b/T may be scalar or length N. Returns N, Nx17.

    No autograd graph is built: custom VJP below carries the integrated score.
    Head float32 is upcast before parameter decoding; outputs remain float64.
    The small per-event diagnostics contain density tail estimates and count
    of intervals, not a certified bound on fixed quadrature or gradient tails.
    """
    device = head.device
    with torch.no_grad():
        q = head.to(torch.float64).reshape(-1, 5, 3)
        n = len(q)
        z = log_energy.to(device=device, dtype=torch.float64).reshape(n, 1)
        p = pz.to(device=device, dtype=torch.float64).reshape(n, 1)
        b = torch.as_tensor(b, dtype=torch.float64, device=device).reshape(-1, 1)
        T = torch.as_tensor(T, dtype=torch.float64, device=device).reshape(-1, 1)
        weights = q[:, 0].softmax(1)
        mr, ms = q[:, 1] + b, q[:, 2]
        sig = q.sigmoid()
        sr = (.05 + 4.95 * sig[:, 3]) * T
        ss = .05 + 4.95 * sig[:, 4]
        dsr = 4.95 * sig[:, 3] * (1 - sig[:, 3]) * T
        dss = 4.95 * sig[:, 4] * (1 - sig[:, 4])
        gx, gw, limits, logtails = constants(str(device))
        logbound = torch.logaddexp(torch.zeros_like(mr), (M / p).log() - mr + .5 * sr.square()) - sr.log() - .5 * LOG2PI
        tailtest = logtails + logbound.clamp_min(0)[..., None]
        admissible = tailtest <= math.log(1e-11)
        # No host sync in the numerical path; invalid tail admission yields NaN.
        idx = admissible.to(torch.int64).argmax(-1)
        limit = limits[idx]
        valid_tail = admissible.any(-1)
        tail = (logtails[idx] + logbound.clamp_min(0)).exp()
        r = mr[..., None] + sr[..., None] * q.new_tensor([-9., -5., -2., 0., 2., 5., 9.])
        r = torch.cat([r, torch.full_like(r[..., :1], -torch.inf)], -1)
        logmu = torch.logaddexp(q.new_tensor(math.log(M)), p.log()[..., None] + r)
        a = q.new_tensor([0., .1, .1])[None, :, None]
        width = q.new_tensor([.1, .9, .9])[None, :, None]
        u = (-torch.expm1((logmu - z[..., None]).clamp_max(700)) - a) / width
        inside = (u > 0) & (u < 1)
        safe_u = torch.where(inside, u, .5)
        split = ((safe_u.log() - torch.log1p(-safe_u)) - ms[..., None]) / ss[..., None]
        split = torch.where(inside & (split > -limit[..., None]) & (split < limit[..., None]), split, limit[..., None])
        # Response-derived points can leave almost the whole normal envelope
        # in one interval. Resolve its unit standardized scale independently
        # of response widths; retain every original response/mass boundary.
        envelope = q.new_tensor(np.arange(-16., 17.))[None, None, :].expand(n, 3, -1)
        envelope = torch.maximum(torch.minimum(envelope, limit[..., None]), -limit[..., None])
        edges = torch.cat([-limit[..., None], split, envelope, limit[..., None]], -1).sort(-1).values
        half = (edges[..., 1:] - edges[..., :-1]) / 2
        midpoint = (edges[..., 1:] + edges[..., :-1]) / 2
        x = midpoint[..., None] + half[..., None] * gx
        s = ms[..., None, None] + ss[..., None, None] * x
        low = (.9 + .1 * torch.sigmoid(-s[:, :1])).log()
        high = math.log(.9) - torch.nn.functional.softplus(s[:, 1:])
        logone = torch.cat([low, high], 1)
        logmu = z[..., None, None] + logone
        delta = logmu.exp() - M
        good = delta > 0
        safe = torch.where(good, delta, 1.)
        r = (safe / p[..., None, None]).log()
        t = (r - mr[..., None, None]) / sr[..., None, None]
        ld = -.5 * (t.square() + x.square()) - sr.log()[..., None, None] - LOG2PI + logmu - safe.log()
        density = torch.where(good, ld.exp(), 0.) * half[..., None] * gw
        total = density.sum((-1, -2))
        norm = (weights * total).sum(1)
        responsibility = weights * total / norm[:, None]
        def integrate(score):
            return weights * (density * score).sum((-1, -2)) / norm[:, None]
        gmr = integrate(t / sr[..., None, None])
        gms = integrate(x / ss[..., None, None])
        gsr = integrate((t.square() - 1) / sr[..., None, None] * dsr[..., None, None])
        gss = integrate((x.square() - 1) / ss[..., None, None] * dss[..., None, None])
        gt = integrate((t.square() - 1) / T[..., None, None]).sum(1)
        gradient = torch.cat([responsibility - weights, gmr, gms, gsr, gss,
                              gmr.sum(1, keepdim=True), gt[:, None]], 1)
        valid = valid_tail.all(1) & (norm > 0) & torch.isfinite(gradient).all(1)
        value = torch.where(valid, norm.log(), torch.nan)
        gradient = torch.where(valid[:, None], gradient, torch.nan)
        diagnostics = dict(density_tail_bound=(weights * tail).sum(1),
                           nonempty_intervals=(half > 0).sum((1, 2)), tail_admitted=valid_tail.all(1))
    return value, gradient, diagnostics


class SegmentedDensity(torch.autograd.Function):
    @staticmethod
    def forward(ctx, head, log_energy, pz, b, T):
        assert not log_energy.requires_grad and not pz.requires_grad
        assert b.numel() == T.numel() == 1
        value, gradient, _ = value_gradient(head, log_energy, pz, b, T)
        ctx.save_for_backward(gradient)
        ctx.input_dtypes = head.dtype, b.dtype, T.dtype
        return value

    @staticmethod
    @once_differentiable
    def backward(ctx, upstream):
        gradient, = ctx.saved_tensors
        scaled = upstream[:, None] * gradient
        hd, bd, td = ctx.input_dtypes
        return scaled[:, :15].to(hd), None, None, scaled[:, 15].sum().to(bd), scaled[:, 16].sum().to(td)


def log_energy_density(head, log_energy, pz, b, T):
    return SegmentedDensity.apply(head, log_energy, pz, b, T)
