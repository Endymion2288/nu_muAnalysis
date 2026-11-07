"""Asimov interval and independent long-EM checks, with original bins."""
import argparse
import json
import time
import numpy as np
from scipy.optimize import brentq
from stage139_likelihood import fit,loglike
from stage139_optimizer import polish
from stage140_solve import solve,statistic
from stage140_batch import OUT,NAMES,SCENARIOS,experiment,counts,CRITICAL

def main():
    parser=argparse.ArgumentParser();parser.add_argument('index',type=int);args=parser.parse_args()
    index=args.index;name=NAMES[index//2];scenario=SCENARIOS[index%2]
    tick=time.perf_counter();cpu=time.process_time()
    fraction,n,q=experiment(name,scenario);psi=float(fraction[:2].sum())
    data=1000*(fraction@q);mc=n[:,None]*q
    free=solve(data,mc,fraction);exact=loglike(data,mc,fraction,q)
    assert abs(free['loglike']-exact)<1e-3
    checkpoint=OUT/f'profile_{index}_points.json'
    evaluated=json.loads(checkpoint.read_text()) if checkpoint.exists() else {}
    def profile(value):
        key=str(float(value))
        if key not in evaluated:
            result=solve(data,mc,fraction,psi=float(value))
            assert free['loglike']>=result['loglike']-1e-5
            evaluated[key]=dict(psi=float(value),LR=max(0.,2*(free['loglike']-result['loglike'])),
                start_LL_difference=result['start_LL_difference'])
            checkpoint.write_text(json.dumps(evaluated,indent=2)+'\n')
        return evaluated[key]['LR']
    for value in np.linspace(max(0.,psi-.06),min(1.,psi+.06),21):profile(value)
    low=brentq(lambda v:profile(v)-CRITICAL,0,psi,xtol=1e-7) if profile(0)>CRITICAL else 0.
    high=brentq(lambda v:profile(v)-CRITICAL,psi,1,xtol=1e-7) if profile(1)>CRITICAL else 1.
    validation=[]
    # Prespecified indices are numerical checks, never estimator selection.
    for toy in [0,150,487]:
        frac,observed,aux=counts(name,scenario,toy)
        _,short_free,short_fixed=statistic(observed,aux,frac)
        long_fits={}
        for fixed in [False,True]:
            value=psi if fixed else None
            long=[]
            for initial in [frac,np.full(7,1/7)]:
                em=fit(observed,aux,initial,psi=value,max_iterations=100000)
                assert em['converged']
                long.append(polish(observed,aux,em,psi=value))
            long_fits[fixed]=max(long,key=lambda r:r['loglike'])
        restart=polish(observed,aux,long_fits[True])
        long_fits[False]=max([long_fits[False],restart],key=lambda r:r['loglike'])
        for fixed in [False,True]:
            gradient=short_fixed if fixed else short_free
            best=long_fits[fixed]
            delta=gradient['loglike']-best['loglike']
            # If starts reach distinct faces, preserve both objectives rather
            # than calling convergence proof of equal/global maxima.
            validation.append(dict(toy=toy,fixed=fixed,gradient_LL=gradient['loglike'],
                long_EM_gradient_LL=best['loglike'],delta=delta,
                agreement_abs_below_001=bool(abs(delta)<.001)))
    result=dict(model=name,scenario=scenario,true_psi=psi,Asimov_exact_LL_delta=free['loglike']-exact,
        Asimov_low95_pp=100*low,Asimov_high95_pp=100*high,Asimov_width95_pp=100*(high-low),
        profile=sorted(evaluated.values(),key=lambda r:r['psi']),numerical_validation=validation,
        CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick)
    (OUT/f'profile_{index}.json').write_text(json.dumps(result,indent=2)+'\n');print(result,flush=True)

if __name__=='__main__':main()
