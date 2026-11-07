"""EM is only a short warm start; constrained gradients revive zero faces."""
import numpy as np
from stage139_likelihood import fit
from stage139_optimizer import polish

def solve(data,mc,fraction,psi=None):
    results=[]
    for start in [fraction,np.full(7,1/7)]:
        warm=fit(data,mc,start,psi=psi,max_iterations=100)
        results.append(polish(data,mc,warm,psi=psi))
    best=max(results,key=lambda r:r['loglike'])
    best['start_LL_difference']=abs(results[0]['loglike']-results[1]['loglike'])
    return best

def statistic(data,mc,fraction):
    fixed=solve(data,mc,fraction,psi=float(fraction[:2].sum()))
    free=solve(data,mc,fraction)
    # Every constrained optimum is feasible for the free problem. This start
    # also lets the gradient optimizer move back off faces that EM had killed.
    warm=polish(data,mc,fixed)
    best=max([free,warm],key=lambda r:r['loglike'])
    assert best['loglike']>=fixed['loglike']-1e-5
    best['start_LL_difference']=free['start_LL_difference']
    best['fixed_restart_improvement']=best['loglike']-free['loglike']
    for result,value in [(best,None),(fixed,float(fraction[:2].sum()))]:
        f=result['fraction'];q=result['response']
        residual=max(abs(f.sum()-1),float(np.max(abs(q.sum(1)-1))),
                     max(0.,-float(f.min())),max(0.,-float(q.min())))
        if value is not None:residual=max(residual,abs(f[:2].sum()-value))
        assert residual<1e-7
        result['constraint_residual']=float(residual)
    return max(0.,2*(best['loglike']-fixed['loglike'])),best,fixed
