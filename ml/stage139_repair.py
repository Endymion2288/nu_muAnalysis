"""Cost and objective checks on exact failed/large-start-discrepancy toy cases."""
import csv
import json
import time
from pathlib import Path
import numpy as np
from stage139_coverage import solve
from stage139_optimizer import polish

OUT=Path('workbook/stage139_energy_ml');CACHE=Path('ntuples/energy_ml_stage139')

def main():
    tick=time.perf_counter();cpu=time.process_time();specs=[]
    for name in ['direct62','joint_direct62_pz0']:
        rows=list(csv.DictReader((OUT/f'{name}_nominal_empirical_toys.tsv').open(),delimiter='\t'))
        top=sorted(rows,key=lambda r:float(r['max_start_LL_difference']),reverse=True)[:2]
        specs += [(name,'nominal_empirical',int(r['toy'])) for r in top]
    specs += [('direct62','unseen_cell_stress',150)]
    results=[]
    for name,scenario,index in specs:
        with np.load(CACHE/'template_counts.npz') as source:
            fraction=source['fraction'];mc=source[name+'_MC_counts']
        n=mc.sum(1);q=mc/n[:,None];psi=float(fraction[:2].sum())
        if scenario=='unseen_cell_stress':
            for j in range(7):
                zero=q[j]==0
                if zero.any():
                    mass=min(.05,3/n[j]);q[j]*=1-mass;q[j,zero]=mass/zero.sum()
        rng=np.random.default_rng(202611071390+(0 if scenario=='nominal_empirical' else 100))
        for toy in range(index+1):
            aux=np.array([rng.multinomial(int(count),r) for count,r in zip(n,q)])
            observed=rng.multinomial(1000,fraction@q)
        start=time.process_time()
        free=solve(observed,aux,fraction);fixed=solve(observed,aux,fraction,psi=psi)
        a=polish(observed,aux,free);b=polish(observed,aux,fixed,psi=psi)
        # A constrained optimum is a feasible starting point for the free fit.
        warm=polish(observed,aux,b)
        a=max([a,warm],key=lambda r:r['loglike'])
        assert a['loglike']>=b['loglike']-1e-5
        results.append(dict(model=name,scenario=scenario,toy=index,
            EM_LR=2*(free['loglike']-fixed['loglike']),
            SLSQP_LR=max(0.,2*(a['loglike']-b['loglike'])),
            free_LL_improvement=a['loglike']-free['loglike'],
            fixed_LL_improvement=b['loglike']-fixed['loglike'],
            CPU_s=time.process_time()-start,
            iterations=[a['iterations'],b['iterations'],warm['iterations']]))
    (OUT/'optimizer_repair.json').write_text(json.dumps(dict(results=results,
        CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,
        scope='numerical repair diagnostic only; no valid final coverage until every frozen toy is reevaluated'),indent=2)+'\n')
    print(results,flush=True)

if __name__=='__main__':main()
