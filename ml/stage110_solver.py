"""Finite analytic solution of the frozen one-dimensional convex risk problem."""
import math
import sys

FEASIBILITY_TOL = 1e-10
TIE_TOL = 1e-12


def value(poly, x):
    a, b, c = poly
    return (a*x+b)*x+c


def roots(poly):
    a, b, c = poly
    if a == 0:
        return [] if b == 0 else [-c/b]
    disc = b*b-4*a*c
    rounding = 16*sys.float_info.epsilon*(b*b+abs(4*a*c))
    if disc < -rounding:
        return []
    disc = max(0., disc)
    q = -.5*(b+math.copysign(math.sqrt(disc), b))
    return [-b/(2*a)] if q == 0 else sorted(set([q/a, c/q]))


def sublevel(poly, bounds=(0., 1.)):
    """Intersect a convex quadratic <=0 with bounds, including exact degeneracy."""
    a, b, c = poly
    assert a >= 0
    lo, hi = bounds
    if a == 0:
        if b == 0:
            return (lo, hi) if c <= 0 else None
        root = -c/b
        lo, hi = (lo, min(hi, root)) if b > 0 else (max(lo, root), hi)
    else:
        rr = roots(poly)
        if not rr:
            return None
        lo, hi = max(lo, rr[0]), min(hi, rr[-1])
    return (lo, hi) if lo <= hi else None


def solve(objectives, constraints):
    interval = (0., 1.)
    intervals = {}
    for name, poly in constraints.items():
        intervals[name] = sublevel(poly)
        assert intervals[name] is not None, name
        interval = sublevel(poly, interval)
        assert interval is not None, name
    lo, hi = interval
    candidates = {lo, hi}
    for a, b, c in objectives:
        if a > 0 and lo <= -b/(2*a) <= hi:
            candidates.add(-b/(2*a))
    cross = roots(tuple(x-y for x, y in zip(*objectives)))
    candidates.update(x for x in cross if lo <= x <= hi)
    rows = [dict(alpha=x, objective=max(value(p, x) for p in objectives),
                 normalized_risks=[value(p, x) for p in objectives]) for x in sorted(candidates)]
    best = min(r['objective'] for r in rows)
    chosen = next(r for r in rows if r['objective'] <= best+TIE_TOL)
    assert all(value(p, chosen['alpha']) <= FEASIBILITY_TOL for p in constraints.values())
    return dict(alpha=chosen['alpha'], objective=chosen['objective'],
                feasible_interval=list(interval), constraint_intervals=intervals,
                candidates=rows, intersection_roots=cross)


def analytic_qa():
    cases = [
        ('crossing', [(1., -.5, 1.0625), (1., -1.5, 1.5625)], {}, .5),
        ('tangent', [(1., -1., 1.25), (0., 0., 1.)], {}, .5),
        ('no_improvement', [(1., 0., 1.), (0., 1., 1.)], {}, 0.),
        ('linear', [(0., -1., 1.), (0., -1., 1.)], {}, 1.),
        ('constant', [(0., 0., 1.), (0., 0., 1.)], {}, 0.),
        ('active_protection', [(1., -1., 1.), (1., -1., 1.)], {'cap': (0., 1., -.2)}, .2),
        ('quadratic_protection', [(1., -1., 1.), (1., -1., 1.)], {'cap': (1., 0., -.04)}, .2),
    ]
    rows = []
    for name, obj, con, expected in cases:
        result = solve(obj, con)
        error = abs(result['alpha']-expected)
        assert error <= FEASIBILITY_TOL
        rows.append(dict(case=name, expected_alpha=expected, actual_alpha=result['alpha'], error=error))
    assert sublevel((1., -1., .25)) == (.5, .5)
    assert sublevel((0., 0., 1.)) is None
    assert sublevel((1., 0., 1.)) is None
    assert sublevel((0., -1., .25)) == (.25, 1.)
    # Cancellation-sensitive positive root has a directly verifiable residual.
    root = roots((1., 1e8, -1.))[-1]
    residual = abs(value((1., 1e8, -1.), root))
    assert residual <= FEASIBILITY_TOL
    return dict(cases=rows, tangent_interval=True, empty_intervals=True,
                linear_lower_bound=True, stable_root_residual=residual)
