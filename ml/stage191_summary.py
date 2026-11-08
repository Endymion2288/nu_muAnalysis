"""Fixed all-candidate IFT summaries; no truth, nearest hit, or fitted charge."""
import math

A_NAMES = ['IFT_original_matched_start'] + [f'IFT_layer{k}_valid_wafer_N' for k in range(3)]
V_NAMES = [f'IFT_layer{k}_mean_log_sigma_mm' for k in range(3)]
C_NAMES = [f'IFT_layer{k}_{q}' for k in range(3) for q in
           ['log1p_candidate_N', 'log1p_compatible3_N', 'log1p_kernel_sum', 'signed_kernel_moment']]


def summarize(m, matched):
    supported = bool(matched and m['start_supported'])
    a, v, c = [float(supported)], [], []
    for layer in range(3):
        wafers = []
        if supported:
            assert 0 not in m['leading']['fitted_stations']
            for w in m['wafers']:
                if w['layer'] != layer or not w['success'] or not w['inside_geometric_bounds']:
                    continue
                cov = w.get('covariance')
                if not cov or cov[0][0] is None or cov[0][0] <= 0:
                    continue
                if any(x.get('pull') is None or not math.isfinite(x['pull']) for x in w['candidates']):
                    continue
                wafers.append(w)
        a.append(float(len(wafers)))
        if not wafers:
            v.append(None); c.extend([None]*4)
            continue
        v.append(math.fsum(math.log(math.sqrt(w['covariance'][0][0])) for w in wafers)/len(wafers))
        pulls = [q['pull'] for w in wafers for q in w['candidates']]
        kernels = [math.exp(-.5*q*q) for q in pulls]
        total = math.fsum(kernels)
        c.extend([math.log1p(len(pulls)), math.log1p(sum(abs(q)<=3 for q in pulls)),
                  math.log1p(total), math.fsum(q*k for q,k in zip(pulls,kernels))/(1+total)])
    return dict(availability=a, sigma=v, content=c)
