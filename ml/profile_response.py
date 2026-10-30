"""Continuous within-bin response and bounded profile-likelihood inference."""
from math import factorial

import numpy as np
import yaml
from scipy.optimize import brentq, minimize, minimize_scalar

from closure import fit_shape


METHODS = ['known_alpha', 'profile_alpha']


def config(repo):
    from within_response import config as parent_config
    study = yaml.safe_load((repo / 'ml/configs/profile_response.yaml').read_text())
    return {**parent_config(repo), **study}


def moments(y, bins, gi, scores, ngroups, cfg):
    centers = np.sqrt(np.array(cfg['truth_edges_GeV'][:-1]) * cfg['truth_edges_GeV'][1:])
    logs = np.log(y / centers[bins])
    reco = np.searchsorted(cfg['energy_reco_internal_GeV'], scores, side='right')
    index = (gi * 6 + bins) * 10 + reco
    power = np.ones(len(y)); output = []
    for k in range(cfg['moment_order'] + 1):
        output.append(np.bincount(index, weights=power, minlength=ngroups * 60).reshape(ngroups, 6, 10))
        power *= logs / (k + 1)
    return np.stack(output), logs, reco


class Response:
    def __init__(self, coefficients):
        self.coefficients = coefficients
        if np.any(coefficients[0].sum(axis=-1) == 0): raise ValueError('empty_truth')
        self.derivative_coefficients = np.arange(1, len(coefficients))[:, None, None] * coefficients[1:]
        self.cache = {}

    def at(self, alpha):
        alpha = float(alpha)
        if alpha in self.cache: return self.cache[alpha]
        h = np.polynomial.polynomial.polyval(alpha, self.coefficients)
        dh = np.polynomial.polynomial.polyval(alpha, self.derivative_coefficients)
        assert h.min() >= -1e-12
        total = h.sum(axis=-1)
        r = (h / total[:, None]).T
        slope = (dh / total[:, None]).T - r * (dh.sum(axis=-1) / total)[None, :]
        if alpha in [-3., -1., 0., 1., 3.]: self.cache[alpha] = (r, slope)
        return r, slope


def nll(response, fractions, observed):
    probability = response @ fractions
    if np.any((probability == 0) & (observed > 0)): return np.inf
    return float(-observed @ np.log(np.maximum(probability, 1e-15)))


def projected(f, b, value):
    result = f.copy(); other = np.arange(6) != b
    if result[other].sum() <= 0: result[other] = (1 - value) / 5
    else: result[other] *= (1 - value) / result[other].sum()
    result[b] = value
    return result


class Inference:
    def __init__(self, response, cfg, stats=None):
        self.response = response; self.cfg = cfg
        self.stats = stats if stats is not None else dict(solver_calls=0, solver_failures=0, iterations=0)

    def _solve(self, q, start, fixed_bin=None, value=None, known_alpha=None):
        unknown = known_alpha is None
        bounds = [(0., 1.)] * 6 + ([tuple(self.cfg['fit_alpha_bounds'])] if unknown else [])
        if fixed_bin is not None: bounds[fixed_bin] = (value, value)
        constant = None if unknown else self.response.at(known_alpha)[0]

        def objective(x):
            r, dr = self.response.at(x[6]) if unknown else (constant, None)
            probability = np.maximum(r @ x[:6], 1e-15)
            ratio = q / probability
            gradient = -r.T @ ratio
            if unknown: gradient = np.r_[gradient, -(dr @ x[:6]) @ ratio]
            return -q @ np.log(probability), gradient

        constraint_gradient = np.r_[np.ones(6), 0.] if unknown else np.ones(6)
        self.stats['solver_calls'] += 1
        result = minimize(objective, start, jac=True, method=self.cfg['optimizer']['method'], bounds=bounds,
                          constraints={'type': 'eq', 'fun': lambda x: x[:6].sum() - 1, 'jac': lambda x: constraint_gradient},
                          options={k: self.cfg['optimizer'][k] for k in ['ftol', 'maxiter']})
        self.stats['iterations'] += int(result.nit)
        x = result.x; r = self.response.at(x[6] if unknown else known_alpha)[0]
        loss = nll(r, x[:6], q)
        ok = result.success and np.isfinite(loss) and abs(x[:6].sum() - 1) < 1e-9
        if not ok: self.stats['solver_failures'] += 1
        grad = objective(x)[1]
        active = (x[:6] > 1e-7) & (x[:6] < 1 - 1e-7)
        if fixed_bin is not None: active[fixed_bin] = False
        lagrange = grad[:6][active].mean() if active.any() else 0.
        reduced = grad - lagrange * constraint_gradient
        residuals = []
        for i, (low, high) in enumerate(bounds):
            if low == high: continue
            if x[i] <= low + 1e-7: residuals.append(max(0., -reduced[i]))
            elif x[i] >= high - 1e-7: residuals.append(max(0., reduced[i]))
            else: residuals.append(abs(reduced[i]))
        return dict(f=x[:6], alpha=float(x[6] if unknown else known_alpha), nll=loss,
                    status='ok' if ok else 'optimizer', iterations=int(result.nit), kkt=float(max(residuals, default=0.)))

    def fit(self, observed, known_alpha=None):
        q = np.asarray(observed, dtype=float); q = q / q.sum()
        r0 = self.response.at(0.)[0]
        if np.any((r0.sum(axis=1) == 0) & (q > 0)):
            return dict(f=np.full(6, np.nan), alpha=np.nan, nll=np.nan, status='support', iterations=0, kkt=np.nan, start_spread=np.nan)
        if known_alpha is not None:
            self.stats['solver_calls'] += 1
            f, info = fit_shape(self.response.at(known_alpha)[0], q, self.cfg)
            self.stats['iterations'] += info['iterations']
            if f is None:
                self.stats['solver_failures'] += 1; f = np.full(6, np.nan)
            return dict(f=f, alpha=float(known_alpha), nll=nll(self.response.at(known_alpha)[0], f, q),
                        **info, start_spread=0.)
        candidates = [self._solve(q, np.r_[np.full(6, 1 / 6), a]) for a in self.cfg['global_alpha_starts']]
        valid = [r for r in candidates if r['status'] == 'ok']
        if not valid:
            return dict(f=np.full(6, np.nan), alpha=np.nan, nll=np.nan, status='optimizer', iterations=0, kkt=np.nan, start_spread=np.nan)
        best = min(valid, key=lambda r: r['nll']).copy()
        best['start_spread'] = float(max(r['nll'] for r in valid) - best['nll'])
        return best

    def conditional(self, observed, best, parameter, value, known_alpha=None):
        q = np.asarray(observed, dtype=float); q /= q.sum()
        if parameter == 6: return self.fit(q, known_alpha=value)
        if value >= 1 - 1e-14:
            f = np.eye(6)[parameter]
            if known_alpha is not None:
                return dict(f=f, alpha=known_alpha, nll=nll(self.response.at(known_alpha)[0], f, q), status='ok')
            def scalar(a): return nll(self.response.at(a)[0], f, q)
            low, high = self.cfg['fit_alpha_bounds']
            self.stats['solver_calls'] += 1
            result = minimize_scalar(scalar, bounds=(low, high), method='bounded', options={'xatol': 1e-10, 'maxiter': 500})
            choices = [(scalar(a), a) for a in [low, 0., high, float(result.x)]]
            loss, alpha = min(choices)
            return dict(f=f, alpha=alpha, nll=loss, status='ok')
        f = projected(best['f'], parameter, value)
        if known_alpha is not None: return self._solve(q, f, parameter, value, known_alpha)
        low, high = self.cfg['fit_alpha_bounds']
        opposite = low if best['alpha'] >= 0 else high
        candidates = [self._solve(q, np.r_[f, a], parameter, value) for a in [best['alpha'], opposite]]
        valid = [r for r in candidates if r['status'] == 'ok']
        if not valid: return dict(f=np.full(6, np.nan), alpha=np.nan, nll=np.nan, status='optimizer')
        return min(valid, key=lambda r: r['nll'])

    def lr(self, partial, best):
        if partial['status'] != 'ok' or best['status'] != 'ok': return np.nan, np.nan
        raw = 2 * self.cfg['benchmark_selected_events'] * (partial['nll'] - best['nll'])
        if raw < self.cfg['negative_lr_failure_threshold']: return np.nan, float(raw)
        return float(max(0., raw)), float(raw)

    def interval(self, observed, best, parameter, known_alpha=None):
        mle = best['alpha'] if parameter == 6 else float(best['f'][parameter])
        low, high = self.cfg['fit_alpha_bounds'] if parameter == 6 else (0., 1.)
        threshold = self.cfg['likelihood_ratio_threshold']; cache = {}
        def statistic(value):
            value = float(value)
            if value not in cache:
                partial = self.conditional(observed, best, parameter, value, known_alpha)
                lr, _ = self.lr(partial, best); cache[value] = lr
            return cache[value] - threshold
        result = dict(low=np.nan, high=np.nan, low_limited=False, high_limited=False,
                      scan_reentry=False, interval_status='ok')
        for name, edge in [('low', low), ('high', high)]:
            if abs(mle - edge) < 1e-9:
                result[name] = float(edge); result[name + '_limited'] = True; continue
            grid = mle + (edge - mle) * (np.arange(1, self.cfg['endpoint_scan_intervals'] + 1) / self.cfg['endpoint_scan_intervals']) ** 2
            previous, previous_value = mle, -threshold
            bracket = None; outside = False
            for value in grid:
                current = statistic(value)
                if np.isnan(current): result['interval_status'] = 'profile_failure'; break
                if bracket is None and current >= 0: bracket = (previous, value)
                if outside and current < 0: result['scan_reentry'] = True
                outside = outside or current >= 0
                previous, previous_value = value, current
            if result['interval_status'] != 'ok': continue
            if bracket is None:
                result[name] = float(edge); result[name + '_limited'] = True
            else:
                a, b = sorted(bracket)
                result[name] = float(brentq(statistic, a, b, xtol=self.cfg['endpoint_root_xtol']))
        return result


def synthetic_checks(cfg):
    rng = np.random.default_rng(314159)
    rm = rng.uniform(.1, 1, (10, 6)); rm /= rm.sum(axis=0)
    rp = rng.uniform(.1, 1, (10, 6)); rp /= rp.sum(axis=0)
    coeff = np.stack([((-.25) ** k * rm.T + .25 ** k * rp.T) / (2 * factorial(k)) for k in range(cfg['moment_order'] + 1)])
    response = Response(coeff); inference = Inference(response, cfg)
    f = np.array([.1, .2, .3, .2, .15, .05]); alpha = .7; r, dr = response.at(alpha); q = r @ f
    best = inference.fit(q)
    assert best['status'] == 'ok'
    ferror = float(np.max(abs(best['f'] - f))); aerror = abs(best['alpha'] - alpha)
    assert ferror < 2e-5 and aerror < 2e-4, (ferror, aerror)
    step = 1e-6; numeric = (response.at(alpha + step)[0] - response.at(alpha - step)[0]) / (2 * step)
    derivative_error = float(np.max(abs(numeric - dr))); assert derivative_error < 1e-8
    x = np.r_[np.full(6, 1 / 6), -.2]; prob = response.at(x[6])[0] @ x[:6]
    analytic = np.r_[-response.at(x[6])[0].T @ (q / prob), -(response.at(x[6])[1] @ x[:6]) @ (q / prob)]
    objective = lambda point: nll(response.at(point[6])[0], point[:6], q)
    numeric_gradient = np.array([(objective(x + step * e) - objective(x - step * e)) / (2 * step) for e in np.eye(7)])
    gradient_error = float(np.max(abs(numeric_gradient - analytic))); assert gradient_error < 1e-8
    partial = inference.conditional(q, best, 5, f[5]); lr, raw = inference.lr(partial, best)
    assert np.isfinite(lr) and lr < 1e-5
    interval = inference.interval(q, best, 6)
    assert interval['interval_status'] == 'ok' and interval['low'] <= alpha <= interval['high']
    return dict(fraction_error=ferror, alpha_error=aerror, derivative_error=derivative_error,
                gradient_error=gradient_error, lr_at_truth=lr, alpha_interval=interval)
