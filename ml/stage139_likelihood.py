"""Conditional multinomial data+MC likelihood, including zero-count MC cells.

The positive initialization is computational only: there are no pseudocounts in
the likelihood. Response rows and truth fractions stay on their full simplexes.
"""
import numpy as np

def loglike(data,mc,fraction,response):
    mix=fraction@response
    if np.any(mix[data>0]<=0) or np.any(response[mc>0]<=0):return -np.inf
    return float(data[data>0]@np.log(mix[data>0])+
                 mc[mc>0]@np.log(response[mc>0]))

def fit(data,mc,start_fraction,psi=None,tolerance=1e-8,max_iterations=20000):
    mc=np.asarray(mc,float);data=np.asarray(data,float)
    q=(mc+.1)/(mc.sum(1)[:,None]+.1*mc.shape[1])
    f=np.array(start_fraction,float).copy();f/=f.sum()
    if psi is not None:
        f[:2]*=psi/f[:2].sum();f[2:]*=(1-psi)/f[2:].sum()
    value=loglike(data,mc,f,q)
    for iteration in range(max_iterations):
        mix=f@q
        ratio=np.divide(data,mix,out=np.zeros_like(data),where=mix>0)
        assigned=f[:,None]*q*ratio
        n=assigned.sum(1)
        if psi is None:f=n/n.sum()
        else:
            f[:2]=psi*n[:2]/n[:2].sum() if n[:2].sum()>0 else psi/2
            f[2:]=(1-psi)*n[2:]/n[2:].sum() if n[2:].sum()>0 else (1-psi)/len(n[2:])
        q=(mc+assigned)/(mc.sum(1)+n)[:,None]
        current=loglike(data,mc,f,q)
        assert current>=value-1e-7,(iteration,value,current)
        if current-value<tolerance:
            return dict(loglike=current,fraction=f,response=q,iterations=iteration+1,converged=True)
        value=current
    return dict(loglike=value,fraction=f,response=q,iterations=max_iterations,converged=False)

def lr(data,mc,fraction):
    free=fit(data,mc,fraction)
    fixed=fit(data,mc,fraction,psi=float(fraction[:2].sum()))
    assert free['converged'] and fixed['converged'],(free['iterations'],fixed['iterations'])
    # Optimizers approach boundary solutions; differences below1e-6 are numeric.
    assert free['loglike']>=fixed['loglike']-1e-6
    return max(0.,2*(free['loglike']-fixed['loglike'])),free,fixed
