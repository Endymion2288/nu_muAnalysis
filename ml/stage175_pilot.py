from concurrent.futures import ProcessPoolExecutor
from stage175_common import *
if __name__=='__main__':
    with ProcessPoolExecutor(max_workers=3) as pool:rows=list(pool.map(read,[(i,'pilot') for i in plan()['pilot_indices']]))
    support=[]
    for i in plan()['pilot_indices']:
        with np.load(CACHE/f'pilot_{i}.npz') as z:d={k:z[k] for k in z.files}
        flags,value=means(d);support.append(dict(index=i,N=len(d['row']),strict_and_supported_N=flags.sum(0).tolist(),derived_finite_N=np.isfinite(value).sum(0).tolist()))
    write('pilot_summary.json',dict(passed=all(r['schema_supported'] and r['leading_match_N']==r['N'] for r in rows),sources=rows,support=support,energy_fits=0,overall_complete=False))
