"""Constrained gradient optimizer can revive faces that multiplicative EM loses."""
import numpy as np
from scipy.optimize import minimize,LinearConstraint,Bounds
from stage139_likelihood import loglike

def polish(data,mc,em,psi=None):
    data=np.asarray(data,float);mc=np.asarray(mc,float)
    k=mc.shape[1];n=7+7*k;scale=float(data.sum()+mc.sum())
    count=8+(psi is not None);a=np.zeros((count,n));a[0,:7]=1
    for j in range(7):a[j+1,7+j*k:7+(j+1)*k]=1
    rhs=np.ones(count)
    if psi is not None:a[-1,:2]=1;rhs[-1]=psi
    lower=np.zeros(n);lower[7:][mc.ravel()>0]=1e-14
    def fun(x):return -loglike(data,mc,x[:7],x[7:].reshape(7,k))/scale
    def jac(x):
        f=x[:7];q=x[7:].reshape(7,k);mix=f@q
        rat=np.divide(data,mix,out=np.zeros_like(data),where=mix>0)
        aux=np.divide(mc,q,out=np.zeros_like(q),where=q>0)
        return -np.r_[q@rat,(aux+f[:,None]*rat).ravel()]/scale
    start=np.r_[em['fraction'],em['response'].ravel()]
    result=minimize(fun,start,jac=jac,method='SLSQP',bounds=Bounds(lower,np.ones(n)),
        constraints=[LinearConstraint(a,rhs,rhs)],options=dict(ftol=1e-12,maxiter=2000))
    value=-result.fun*scale
    assert result.success,(result.message,value-em['loglike'])
    assert np.max(abs(a@result.x-rhs))<1e-7
    assert value>=em['loglike']-1e-5,(value,em['loglike'])
    return dict(loglike=value,fraction=result.x[:7],response=result.x[7:].reshape(7,k),
                converged=True,iterations=int(result.nit),SLSQP_delta=value-em['loglike'])
