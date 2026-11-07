"""All original toy indices, with individually saved numerical solutions."""
import argparse
import concurrent.futures
import json
import time
from pathlib import Path
import numpy as np
from stage140_solve import statistic

OUT=Path('workbook/stage140_energy_ml')
CACHE=Path('ntuples/energy_ml_stage139')
NAMES=['traditional','direct62','joint_direct62_pz0']
SCENARIOS=['nominal_empirical','unseen_cell_stress']
CRITICAL=3.841458820694124

def experiment(name,scenario):
    with np.load(CACHE/'template_counts.npz') as source:
        fraction=source['fraction'];mc=source[name+'_MC_counts']
    n=mc.sum(1);q=mc/n[:,None]
    if scenario=='unseen_cell_stress':
        for j in range(7):
            zero=q[j]==0
            if zero.any():
                mass=min(.05,3/n[j]);q[j]*=1-mass;q[j,zero]=mass/zero.sum()
    return fraction,n,q

def counts(name,scenario,index):
    fraction,n,q=experiment(name,scenario)
    rng=np.random.default_rng(202611071390+(0 if scenario=='nominal_empirical' else 100))
    for _ in range(index+1):
        aux=np.array([rng.multinomial(int(count),r) for count,r in zip(n,q)])
        observed=rng.multinomial(1000,fraction@q)
    return fraction,observed,aux

def worker(spec):
    name,scenario,index=spec;tick=time.perf_counter();cpu=time.process_time()
    fraction,observed,aux=counts(*spec)
    lr,a,b=statistic(observed,aux,fraction)
    return dict(model=name,scenario=scenario,toy=index,LR=lr,covered=bool(lr<=CRITICAL),
        true_psi=float(fraction[:2].sum()),psi_hat=float(a['fraction'][:2].sum()),
        free_LL=a['loglike'],fixed_LL=b['loglike'],
        start_LL_difference_free=a['start_LL_difference'],
        start_LL_difference_fixed=b['start_LL_difference'],
        fixed_restart_improvement=a['fixed_restart_improvement'],
        max_constraint_residual=max(a['constraint_residual'],b['constraint_residual']),
        CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('batch',type=int);args=parser.parse_args()
    batch=args.batch;assert 0<=batch<60
    name=NAMES[batch//20];scenario=SCENARIOS[(batch//10)%2];start=50*(batch%10)
    folder=OUT/f'batch_{batch}';folder.mkdir(parents=True,exist_ok=True)
    specs=[(name,scenario,i) for i in range(start,start+50)]
    missing=[s for s in specs if not (folder/f'toy_{s[2]}.json').exists()]
    tick=time.perf_counter();errors=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=8) as pool:
        futures={pool.submit(worker,s):s for s in missing}
        for future in concurrent.futures.as_completed(futures):
            spec=futures[future]
            try:
                result=future.result()
                (folder/f'toy_{spec[2]}.json').write_text(json.dumps(result)+'\n')
            except Exception as exc:
                errors.append(dict(spec=spec,error=repr(exc)))
    result=dict(batch=batch,model=name,scenario=scenario,expected=50,
                completed=len(list(folder.glob('toy_*.json'))),errors=errors,
                resumed_existing=50-len(missing),wall_s=time.perf_counter()-tick)
    (OUT/f'batch_{batch}.json').write_text(json.dumps(result,indent=2)+'\n')
    print(result,flush=True);assert not errors and result['completed']==50

if __name__=='__main__':main()
