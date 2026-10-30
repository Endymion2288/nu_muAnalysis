"""Fixed within-bin shape templates and internal integration for stage24."""
import numpy as np
import yaml


METHODS = ['coarse6', 'fine12', 'continuous']
ALPHAS = [-1., 0., 1.]


def config(repo):
    study = yaml.safe_load((repo / 'ml/configs/within_response.yaml').read_text())
    parent = yaml.safe_load((repo / study['parent_config']).read_text())
    return {**parent, **study}


def histograms(y, bins, gi, scores, ngroups, cfg):
    centers = np.sqrt(np.array(cfg['truth_edges_GeV'][:-1]) * cfg['truth_edges_GeV'][1:])
    log_within = np.log(y / centers[bins])
    sub = 2 * bins + (log_within >= 0)
    reco = np.searchsorted(cfg['energy_reco_internal_GeV'], scores, side='right')
    index = (gi * 12 + sub) * 10 + reco
    counts = np.stack([np.bincount(index, weights=np.exp(a * log_within), minlength=ngroups * 120).reshape(ngroups, 12, 10) for a in ALPHAS])
    log_counts = np.bincount(index, weights=log_within, minlength=ngroups * 120).reshape(ngroups, 12, 10)
    return counts, log_counts, sub


def responses(source):
    """Return alpha × method response matrices; missing fine cells are explicit."""
    nominal_sub = source[1].reshape(6, 2, 10)
    totals = nominal_sub.sum(axis=-1)
    parent = nominal_sub.sum(axis=1)
    if np.any(parent.sum(axis=-1) == 0):
        return [[None] * 3 for _ in ALPHAS]
    r0 = (parent / parent.sum(axis=-1)[:, None]).T
    fine_ok = np.all(totals > 0)
    conditional = nominal_sub / totals[:, :, None] if fine_ok else None
    output = []
    for ai in range(3):
        weighted = source[ai].reshape(6, 2, 10)
        weighted_parent = weighted.sum(axis=1)
        continuous = (weighted_parent / weighted_parent.sum(axis=-1)[:, None]).T
        fine = None
        if fine_ok:
            mix = weighted.sum(axis=-1)
            mix /= mix.sum(axis=-1)[:, None]
            fine = np.einsum('bkj,bk->jb', conditional, mix)
        if ai == 1:
            np.testing.assert_allclose(continuous, r0, rtol=0, atol=1e-14)
            if fine is not None: np.testing.assert_allclose(fine, r0, rtol=0, atol=1e-14)
            continuous = r0
            if fine is not None: fine = r0
        output.append([r0, fine, continuous])
    return output


def pseudo_shapes(pseudo):
    parent = pseudo.reshape(3, 6, 2, 10).sum(axis=2)
    nominal_totals = parent[1].sum(axis=-1)
    if np.any(nominal_totals == 0): return None, None
    fractions = nominal_totals / nominal_totals.sum()
    normalized = parent * (nominal_totals[None, :] / parent.sum(axis=-1))[:, :, None]
    np.testing.assert_allclose(normalized.sum(axis=-1), np.broadcast_to(nominal_totals, (3, 6)), rtol=1e-12)
    q = normalized.sum(axis=1) / normalized.sum(axis=(1, 2))[:, None]
    return fractions, q


def derivative(source_nominal, source_log):
    parent = source_nominal.reshape(6, 2, 10).sum(axis=1)
    log_parent = source_log.reshape(6, 2, 10).sum(axis=1)
    total = parent.sum(axis=-1)
    r0 = (parent / total[:, None]).T
    return (log_parent / total[:, None]).T - r0 * (log_parent.sum(axis=-1) / total)[None, :]


def profile_information(response, slope, fractions, cfg):
    """One common alpha, no prior: local unconstrained Fisher diagnostic only."""
    tangent = np.vstack([np.eye(5), -np.ones(5)])
    probability = response @ fractions
    design = np.column_stack([response @ tangent, slope @ fractions])
    positive = probability > 0
    x = design[positive]
    information = cfg['benchmark_selected_events'] * (x.T / probability[positive]) @ x
    eig = np.linalg.eigvalsh(information)
    condition = float(eig[-1] / eig[0]) if eig[0] > 0 else np.inf
    if eig[0] <= cfg['fisher_relative_eigenvalue_floor'] * eig[-1]:
        return None, dict(identifiable=False, condition=condition, alpha_sigma=np.nan, max_abs_correlation=np.nan)
    inverse = np.linalg.inv(information)
    covariance = tangent @ inverse[:5, :5] @ tangent.T
    cross = tangent @ inverse[:5, 5]
    sigma = np.sqrt(np.diag(covariance)) / fractions
    return sigma, dict(identifiable=True, condition=condition, alpha_sigma=float(np.sqrt(inverse[5, 5])),
                       max_abs_correlation=float(np.max(abs(cross / np.sqrt(np.diag(covariance) * inverse[5, 5])))))


def synthetic_checks(cfg):
    from closure import fit_shape
    bins = np.repeat(np.arange(6), 4)
    centers = np.sqrt(np.array(cfg['truth_edges_GeV'][:-1]) * cfg['truth_edges_GeV'][1:])
    offsets = np.tile([-.3, -.1, .1, .3], 6)
    y = centers[bins] * np.exp(offsets)
    index = 2 * bins + (offsets >= 0)
    f = np.array([.1, .2, .3, .2, .15, .05])
    results = {}
    for name, local_j in [('half_only', [0, 0, 1, 1]), ('within_half', [0, 1, 1, 2])]:
        reco = np.repeat(np.arange(6), 4) + np.tile(local_j, 6)
        source = np.stack([np.bincount(index * 10 + reco, weights=np.exp(a * offsets), minlength=120).reshape(12, 10) for a in ALPHAS])
        matrices = responses(source)
        target = matrices[2][2] @ f
        errors = []
        for r in matrices[2]:
            fitted, info = fit_shape(r, target, cfg)
            assert info['status'] == 'ok'
            errors.append(float(np.max(abs(fitted - f))))
        assert errors[2] < 2e-5 and errors[0] > 1e-4
        if name == 'half_only': assert errors[1] < 2e-5
        else: assert errors[1] > 1e-4
        hlog = np.bincount(index * 10 + reco, weights=offsets, minlength=120).reshape(12, 10)
        slope = derivative(source[1], hlog)
        step = 1e-5
        direct = []
        for a in [-step, step]:
            h = np.bincount(bins * 10 + reco, weights=np.exp(a * offsets), minlength=60).reshape(6, 10)
            direct.append((h / h.sum(axis=-1)[:, None]).T)
        slope_error = float(np.max(abs(slope - (direct[1] - direct[0]) / (2 * step))))
        assert slope_error < 1e-9
        results[name] = dict(max_fraction_errors=dict(zip(METHODS, errors)), derivative_error=slope_error)
    return results
