"""Fixed-shape posterior-ratio inference and independently measured score information.

Curvature of a misspecified posterior likelihood is not detector Fisher information.
The empirical score calculation below uses measured class-conditional responses and
therefore keeps that distinction explicit. All fractions are selected-event fractions.
"""
import numpy as np
from scipy.linalg import helmert
from scipy.optimize import minimize


TANGENT = helmert(6, full=False).T


def fit_mixture(ratio, weights, initial):
    weights = np.asarray(weights, float); weights = weights / weights.sum()
    def objective(f):
        prob = np.maximum(ratio @ f, 1e-15)
        return -weights @ np.log(prob), -ratio.T @ (weights / prob)
    result = minimize(objective, initial, jac=True, method='SLSQP', bounds=[(0, 1)]*6,
                      constraints={'type': 'eq', 'fun': lambda f: f.sum()-1,
                                   'jac': lambda f: np.ones(6)},
                      options={'ftol': 1e-12, 'maxiter': 400})
    f = result.x; grad = objective(f)[1]; active = f > 1e-7
    lagrange = grad[active].mean()
    kkt = max(np.max(abs(grad[active]-lagrange)),
              np.max(np.maximum(lagrange-grad[~active], 0), initial=0))
    return f, dict(success=bool(result.success), iterations=int(result.nit), kkt=float(kkt),
                   boundary=bool((f < 1e-7).any()))


def invert_information(information, fractions):
    eig, vectors = np.linalg.eigh(information)
    if eig[0] <= 1e-10 * eig[-1] or eig[-1] <= 0:
        return dict(valid=False), None
    covariance = TANGENT @ np.linalg.inv(information) @ TANGENT.T
    return dict(valid=True, relative_sigma_RMS=float(np.sqrt(np.mean(np.diag(covariance)/fractions**2))),
                min_eigenvalue=float(eig[0]), condition=float(eig[-1]/eig[0]),
                weakest_direction=(TANGENT @ vectors[:, 0]).tolist(),
                relative_sigma=(np.sqrt(np.diag(covariance))/fractions).tolist()), covariance


def score_information(ratio, labels, weights, n=1000):
    weights = weights / weights.sum()
    fractions = np.bincount(labels, weights=weights, minlength=6)
    if (fractions <= 0).any(): return dict(valid=False), None
    score = (ratio @ TANGENT) / (ratio @ fractions)[:, None]
    mean = weights @ score
    covariance = (score.T * weights) @ score - np.outer(mean, mean)
    conditional = np.stack([(weights[labels == b] @ score[labels == b]) / fractions[b] for b in range(6)])
    derivative = conditional.T @ TANGENT
    if np.linalg.eigvalsh(covariance)[0] <= 1e-10*np.linalg.eigvalsh(covariance)[-1]:
        return dict(valid=False), None
    info = n * derivative.T @ np.linalg.solve(covariance, derivative)
    return invert_information(info, fractions)


def curvature_information(ratio, fractions, weights, n=1000):
    score = (ratio @ TANGENT) / np.maximum(ratio @ fractions, 1e-15)[:, None]
    information = n * (score.T * (weights/weights.sum())) @ score
    return invert_information(information, fractions)


def categorical_information(histogram, n=1000):
    """Exact known-response Fisher information of the fixed ten-category observation."""
    totals = histogram.sum(0)
    if (totals <= 0).any(): return dict(valid=False), None
    fractions = totals/totals.sum(); response = histogram/totals
    probability = response@fractions; positive = probability > 0
    derivative = response[positive]@TANGENT
    return invert_information(n*(derivative.T/probability[positive])@derivative, fractions)


def probability_metrics(q, labels):
    true_probability = q[np.arange(len(q)), labels]
    zeros = int((true_probability == 0).sum())
    clipped = float(-np.log(np.maximum(true_probability, 1e-15)).mean())
    return dict(log_score=float('inf') if zeros else clipped, clipped_log_score=clipped,
                zero_true_probability_count=zeros,
                Brier=float(np.mean(np.sum((q-np.eye(6)[labels])**2, axis=1))),
                accuracy=float((q.argmax(1) == labels).mean()),
                mean_p_high=float(q[:, 5].mean()), true_fraction_high=float((labels == 5).mean()))


def checks():
    rng = np.random.default_rng(90210)
    response = rng.uniform(.05, 1, (12, 6)) + np.vstack([np.eye(6), np.eye(6)]) * 5
    response /= response.sum(0)
    prior = np.array([.1, .15, .25, .25, .2, .05]); f = np.array([.05, .2, .3, .2, .15, .1])
    q = response * prior / (response @ prior)[:, None]; ratio = q / prior
    fitted, status = fit_mixture(ratio, response @ f, prior)
    assert status['success'] and np.max(abs(fitted-f)) < 2e-6
    labels = np.tile(np.arange(6), 12); repeated_ratio = np.repeat(ratio, 6, axis=0)
    weights = (response * f).reshape(-1)
    empirical, cov = score_information(repeated_ratio, labels, weights)
    direct, direct_cov = curvature_information(ratio, f, response @ f)
    assert empirical['valid'] and direct['valid']
    relative = float(np.max(abs(cov-direct_cov))/np.max(abs(direct_cov)))
    assert relative < 1e-10
    categorical, categorical_cov = categorical_information(response*f)
    assert categorical['valid']
    np.testing.assert_allclose(categorical_cov, direct_cov, atol=1e-14)
    assert np.max(abs(cov.sum(0))) < 1e-12
    eps = 1e-6; w = response @ f
    grad = -ratio.T @ (w/(ratio@f))
    numeric = np.array([(-w@np.log(ratio@(f+eps*t)) + w@np.log(ratio@(f-eps*t)))/(2*eps)
                        for t in TANGENT.T])
    gradient_error = float(np.max(abs(numeric-TANGENT.T@grad)))
    assert gradient_error < 1e-8
    singular = score_information(np.ones_like(repeated_ratio), labels, weights)[0]
    assert not singular['valid']
    return dict(synthetic_fraction_max_error=float(np.max(abs(fitted-f))),
                score_curvature_covariance_relative_error=relative, gradient_error=gradient_error,
                no_information_detected=True)
