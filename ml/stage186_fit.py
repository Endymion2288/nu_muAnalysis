"""Exactly nine from-scratch fixed fits on unchanged original incoming-weighted roles."""
from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp
from stage186_common import *
from stage186_evaluate import evaluate
if __name__=='__main__':
 d,x,names=inputs(write_cohort=True);ART.mkdir(parents=True,exist_ok=True)
 with ProcessPoolExecutor(max_workers=3,mp_context=mp.get_context('fork')) as pool:records=list(pool.map(energy.fit,[('energy',arm,x[arm],names[arm],d) for arm in ['A','R','I']]))
 write('energy_fits.json',records);evaluate('energy',d,['A','R','I'])
 write('fit_summary.json',dict(passed=True,new_fits=9,rounds_total=3600,dimensions={k:v.shape[1] for k,v in x.items()},original_N=len(d['role']),active_N=int((d['role']>0).sum()),Stage87_refits=0,quarantine_predictions=0,reserved_predictions=0,new_G4=0,overall_complete=False,promotion=False))

 import subprocess,sys
 assert subprocess.run([sys.executable,"ml/stage186_plot.py"]).returncode==0
