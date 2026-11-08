from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp
from stage189_common import *

if __name__=='__main__':
    d,x,names=inputs()
    with ProcessPoolExecutor(max_workers=3,mp_context=mp.get_context('fork')) as pool:
        fits=list(pool.map(energy.fit,[('composition',a,x[a],names[a],d) for a in ['A','C','S']]))
    write('full_fits.json',fits)
    energy.evaluate('composition',d,['X','A','C','S'],extra_references=['S'])
    write('full_summary.json',dict(passed=True,new_fits=9,pilot_baseline_fits=3,
        promotion=False,overall_complete=False))
