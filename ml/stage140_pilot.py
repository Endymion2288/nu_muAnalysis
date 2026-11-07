"""Cost and agreement before completing every unchanged Stage139 toy."""
import concurrent.futures
import json
import time
from pathlib import Path
import numpy as np
from stage140_solve import statistic
OUT=Path('workbook/stage140_energy_ml');CACHE=Path('ntuples/energy_ml_stage139')

def worker(spec):
    name,scenario,index=spec;tick=time.perf_counter();cpu=time.process_time()
    with np.load(CACHE/'template_counts.npz') as source:
        fraction=source['fraction'];mc=source[name+'_MC_counts']
    n=mc.sum(1);q=mc/n[:,None]
    if scenario=='unseen_cell_stress':
        for j in range(7):
            zero=q[j]==0
            if zero.any():
                mass=min(.05,3/n[j]);q[j]*=1-mass;q[j,zero]=mass/zero.sum()
    rng=np.random.default_rng(202611071390+(0 if scenario=='nominal_empirical' else 100))
    for i in range(index+1):
        aux=np.array([rng.multinomial(int(count),r) for count,r in zip(n,q)])
        observed=rng.multinomial(1000,fraction@q)
    value,a,b=statistic(observed,aux,fraction)
    return dict(model=name,scenario=scenario,toy=index,LR=value,psi_hat=float(a['fraction'][:2].sum()),
        start_LL_difference_fixed=b['start_LL_difference'],CPU_s=time.process_time()-cpu,
        wall_s=time.perf_counter()-tick)

def main():
    tick=time.perf_counter()
    specs=[(name,scenario,i) for name in ['traditional','direct62','joint_direct62_pz0']
           for scenario in ['nominal_empirical','unseen_cell_stress'] for i in [0,150,487]]
    with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:results=list(pool.map(worker,specs))
    # Same original failure, same counts/seed, independent corrected algorithm.
    case=next(r for r in results if r['model']=='direct62' and r['scenario']=='unseen_cell_stress' and r['toy']==150)
    assert abs(case['LR']-.21983083997838548)<1e-3,case
    result=dict(results=results,CPU_s=sum(r['CPU_s'] for r in results),wall_s=time.perf_counter()-tick,
        scope='numerical/cost pilot18 fixedtoys only; no formal coverage or actualdata certification')
    (OUT/'pilot_results.json').write_text(json.dumps(result,indent=2)+'\n');print(result,flush=True)

if __name__=='__main__':main()
