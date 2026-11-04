"""Deterministic integration of saved stage87 muon/transfer heads; no fitting."""
import math
import time

import numpy as np
from scipy.integrate import quad_vec
from scipy.optimize import brentq
from scipy.special import expit, logsumexp, ndtr

M = .1056583755
LOG2PI = math.log(2*math.pi)
PROBS = np.array([.05, .16, .5, .84, .95])
EDGES = np.array([0., 50., 100., 200., 400., 800., 1600., 3200., 6400., np.inf])


def decode(head, b, T):
    q = np.asarray(head, dtype=float).reshape(-1, 5, 3)
    return (np.exp(q[:, 0]-logsumexp(q[:, 0], axis=1)[:, None]),
            q[:, 1]+b, q[:, 2], (.05+4.95*expit(q[:, 3]))*T,
            .05+4.95*expit(q[:, 4]))


class FixedGH:
    """Cache the latent nodes/mixture; evaluate several energies per event."""
    def __init__(self, head, pz, b, T, order):
        self.w, self.mr, ms, self.sr, ss = decode(head, b, T)
        self.pz = np.asarray(pz)
        x, w = np.polynomial.hermite.hermgauss(order)
        s = ms[:, :, None]+ss[:, :, None]*x[None, None, :]*math.sqrt(2)
        self.log_onef = np.concatenate([np.log(.9+.1*expit(-s[:, :1])),
                                       math.log(.9)-np.logaddexp(0., s[:, 1:])], axis=1)
        self.weights = self.w[:, :, None]*w[None, None, :]/math.sqrt(math.pi)
        self.calls = 0

    def evaluate(self, z, density=False):
        z = np.asarray(z).reshape(len(self.pz), -1)
        self.calls += 1
        logmu = z[:, :, None, None]+self.log_onef[:, None]
        delta = np.exp(logmu)-M
        good = delta > 0
        safe = np.maximum(delta, np.finfo(float).tiny)
        r = np.log(safe/self.pz[:, None, None, None])
        t = (r-self.mr[:, None, :, None])/self.sr[:, None, :, None]
        c = (np.where(good, ndtr(t), 0.)*self.weights[:, None]).sum((2, 3))
        if not density:
            return c
        ld = -.5*t*t-np.log(self.sr[:, None, :, None])-.5*LOG2PI+logmu-np.log(safe)
        d = (np.where(good, np.exp(ld), 0.)*self.weights[:, None]).sum((2, 3))
        return c, d

    def summary(self, truth, ratios):
        n = len(self.pz)
        F = np.column_stack([np.zeros(n), self.evaluate(np.broadcast_to(np.log(EDGES[1:-1]), (n, 8))), np.ones(n)])
        result = {}
        raw_targets = []
        for name, ratio in ratios.items():
            mass = np.diff(F)*ratio
            norm = mass.sum(1)
            prefix = np.column_stack([np.zeros(n), mass.cumsum(1)])
            q = PROBS[None]*norm[:, None]
            bins = (q[:, :, None] >= prefix[:, None, 1:]).sum(2).clip(0, 8)
            idx = np.arange(n)[:, None]
            targets = F[idx, bins]+(q-prefix[idx, bins])/ratio[bins]
            raw_targets.append(targets)
            result[name] = dict(F=F, norm=norm, prefix=prefix, ratio=ratio)
        target = np.column_stack(raw_targets)
        lo = np.full(target.shape, math.log(M)+1e-12)
        hi = np.broadcast_to(np.log(self.pz)[:, None]+40., target.shape).copy()
        for _ in range(40):
            mid = (lo+hi)/2
            above = self.evaluate(mid) >= target
            hi = np.where(above, mid, hi)
            lo = np.where(above, lo, mid)
        quantiles = (lo+hi)/2
        c, d = self.evaluate(np.log(truth), density=True)
        bins = np.searchsorted(EDGES, truth, side='right')-1
        for j, (name, ratio) in enumerate(ratios.items()):
            a = result[name]; ids = np.arange(n)
            a.update(quantiles=quantiles[:, 5*j:5*(j+1)],
                     PIT=(a['prefix'][ids, bins]+ratio[bins]*(c[:, 0]-F[ids, bins]))/a['norm'],
                     log_density=np.log(d[:, 0])+np.log(ratio[bins])-np.log(a['norm']))
        return result


class Reference:
    """Adaptive integration in s and independently in r, both with tail bounds."""
    def __init__(self, head, pz, b, T, direction='s', eps=1e-10):
        self.w, self.mr, self.ms, self.sr, self.ss = [a[0] for a in decode(np.asarray(head)[None], b, T)]
        self.pz = float(pz); self.direction = direction; self.eps = eps
        self.cache = {}; self.calls = 0; self.neval = 0; self.max_error = 0.; self.max_tail = 0.
        self.precision_flags = 0
        self.derivative_step_error = 0.

    def _component(self, z, k):
        mr, ms, sr, ss = self.mr[k], self.ms[k], self.sr[k], self.ss[k]
        a, width = (0., .1) if k == 0 else (.1, .9)
        if self.direction == 's':
            logbound = np.logaddexp(0., math.log(M/self.pz)-mr+.5*sr*sr)-math.log(sr)-.5*LOG2PI
        else:
            logbound = (math.log(10)+logsumexp([math.log(2), ms+.5*ss*ss, -ms+.5*ss*ss])
                        if k == 0 else np.logaddexp(0., -ms+.5*ss*ss))-math.log(ss)-.5*LOG2PI
        L = 10
        while math.log(2*ndtr(-L))+max(0., logbound) > math.log(self.eps/10):
            L += 1
            assert L <= 16, 'tail bound not certified'
        tail = 2*ndtr(-L)*max(1., math.exp(logbound))
        points = []
        if self.direction == 's':
            # Resolve narrow r likelihood peaks and the muon mass boundary in s.
            for r in [mr+j*sr for j in [-9, -5, -2, 0, 2, 5, 9]] + [-np.inf]:
                logmu = np.logaddexp(math.log(M), math.log(self.pz)+r)
                u = (-math.expm1(min(700., logmu-z))-a)/width
                if 0 < u < 1:
                    points.append((math.log(u)-math.log1p(-u)-ms)/ss)
            def integrand(x):
                s = ms+ss*x
                logone = math.log(.9+.1*expit(-s)) if k == 0 else math.log(.9)-np.logaddexp(0., s)
                logmu = z+logone; delta = math.exp(logmu)-M
                if delta <= 0:
                    return np.zeros(2)
                r = math.log(delta/self.pz); t = (r-mr)/sr
                density = math.exp(-.5*t*t-math.log(sr)-.5*LOG2PI+logmu-math.log(delta))
                return math.exp(-.5*x*x-.5*LOG2PI)*np.array([ndtr(t), density])
        else:
            for s in [ms+j*ss for j in [-9, -5, -2, 0, 2, 5, 9]] + [-np.inf, np.inf]:
                f = a+width*expit(s); delta = math.exp(z)*(1-f)-M
                if delta > 0:
                    points.append((math.log(delta/self.pz)-mr)/sr)
            def integrand(x):
                r = mr+sr*x
                logmu = np.logaddexp(math.log(M), math.log(self.pz)+r)
                logratio = logmu-z
                if k == 0:
                    if logratio >= 0:
                        return np.zeros(2)
                    if logratio <= math.log(.9):
                        return np.array([math.exp(-.5*x*x-.5*LOG2PI), 0.])
                    logu = math.log(-math.expm1(logratio)/.1)
                    logv = math.log(.9*math.expm1(logratio-math.log(.9))/.1)
                    jac = logratio-math.log(.1)-logu-logv
                else:
                    logv = logratio-math.log(.9)
                    if logv >= 0:
                        return np.zeros(2)
                    logu = math.log(-math.expm1(logv))
                    jac = -logu
                s = logu-logv; t = (s-ms)/ss
                # Density in this direction becomes ill conditioned when a
                # logistic component concentrates near f=.1. Differentiate the
                # bounded, integrated CDF instead, with two fixed step sizes.
                return math.exp(-.5*x*x-.5*LOG2PI)*np.array([ndtr(t), 0.])
        points = sorted(set(p for p in points if -L < p < L))
        val, err, info = quad_vec(integrand, -L, L, epsabs=self.eps, epsrel=self.eps,
                                  points=points, limit=400, norm='max', full_output=True)
        # QUADPACK-style error estimates have a finite precision floor. Keep
        # flagged estimates only under a separate absolute reference error cap;
        # independent reverse integration must still pass the reported checks.
        if not info.success:
            self.precision_flags += 1
        assert err < 1e-9, (self.direction, z, k, float(err), info.message)
        self.neval += int(info.neval)
        return val, float(err+tail), float(tail), L

    def evaluate(self, z, density=True):
        z = float(z)
        if z not in self.cache:
            values = [self._component(z, k) for k in range(3)]
            v = sum(w*t[0] for w, t in zip(self.w, values))
            err = sum(w*t[1] for w, t in zip(self.w, values))
            tail = sum(w*t[2] for w, t in zip(self.w, values))
            self.max_error = max(self.max_error, err); self.max_tail = max(self.max_tail, tail)
            self.cache[z] = (float(v[0]), float(v[1]), err)
            self.calls += 1
        value = self.cache[z]
        if self.direction == 'r' and density:
            derivatives = [];bounds = []
            for h in [1e-3, 5e-4]:
                points = [self.evaluate(z+j*h, density=False) for j in [-2, -1, 1, 2]]
                coeff = np.array([1., -8., 8., -1.])/(12*h)
                derivatives.append(float(coeff@np.array([p[0] for p in points])))
                bounds.append(float(abs(coeff)@np.array([p[2] for p in points])))
            diff = abs(derivatives[1]-derivatives[0])
            self.derivative_step_error = max(self.derivative_step_error, diff)
            return value[0], derivatives[1], value[2]+max(bounds)+diff
        return value

    def summary(self, truth, ratio, guesses):
        F = np.r_[0., [self.evaluate(math.log(e))[0] for e in EDGES[1:-1]], 1.]
        assert np.diff(F).min() >= -1e-9
        mass = np.diff(F)*ratio; norm = mass.sum(); prefix = np.r_[0., mass.cumsum()]
        quantiles = []; residuals = []
        for prob, guess in zip(PROBS, guesses):
            k = min(8, np.searchsorted(prefix[1:], prob*norm, side='right'))
            target = F[k]+(prob*norm-prefix[k])/ratio[k]
            lo = math.log(M)+1e-12 if k == 0 else math.log(EDGES[k])
            hi = math.log(self.pz)+40 if k == 8 else math.log(EDGES[k+1])
            # Newton uses the exact adaptive density, with a maintained bracket.
            z = float(np.clip(guess, lo, hi))
            for _ in range(40):
                c, density, _ = self.evaluate(z); delta = c-target
                if abs(delta) < 2e-10:
                    break
                if delta > 0:hi = z
                else:lo = z
                step = z-delta/density if density > 1e-15 else np.inf
                z = step if lo < step < hi else (lo+hi)/2
            else:
                z = brentq(lambda zz:self.evaluate(zz)[0]-target, lo, hi, xtol=1e-8)
            quantiles.append(z); residuals.append(abs(self.evaluate(z)[0]-target))
        c, d, _ = self.evaluate(math.log(truth)); k = np.searchsorted(EDGES, truth, side='right')-1
        return dict(F=F, norm=float(norm), quantiles=np.array(quantiles),
                    PIT=float((prefix[k]+ratio[k]*(c-F[k]))/norm),
                    log_density=float(math.log(d)+math.log(ratio[k])-math.log(norm)),
                    root_residual=max(residuals))
