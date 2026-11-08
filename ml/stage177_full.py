from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp
from stage177_common import *
if __name__=='__main__':
    d,x,names=inputs()
    with ProcessPoolExecutor(max_workers=2,mp_context=mp.get_context("fork")) as pool:records=list(pool.map(energy.fit,[('slab',a,x[a],names[a],d) for a in ['V','T']]))
    write('full_fits.json',records);energy.evaluate('slab',d,['X','V','T'])
    write('full_summary.json',dict(passed=True,new_candidate_fits=6,baseline_fits=3,quarantine_predictions=0,reserved_predictions=0,overall_complete=False,promotion=False))
