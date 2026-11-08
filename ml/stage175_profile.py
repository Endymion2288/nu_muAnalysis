"""Exact original96 entries; timing decomposition and byte-content consistency only."""
from concurrent.futures import ProcessPoolExecutor
from stage175_common import *
if __name__=='__main__':
    with ProcessPoolExecutor(max_workers=3) as pool:rows=list(pool.map(read,[(i,'profile') for i in plan()['pilot_indices']]))
    for i in plan()['pilot_indices']:
        with np.load(CACHE/f'pilot_{i}.npz') as a,np.load(CACHE/f'profile_{i}.npz') as b:
            for k in a.files:np.testing.assert_array_equal(a[k],b[k])
    write('profile_summary.json',dict(passed=True,sources=rows,exact_original_pilot_N=96,new_entries=0,energy_fits=0))
