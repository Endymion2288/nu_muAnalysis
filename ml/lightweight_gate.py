"""One fixed 4-input, 8-hidden-unit readout gate for three frozen experts."""
import json
import time

import numpy as np
from scipy.optimize import minimize

from expert_combination import REPO, LOW, COST, masks

OUT = REPO/'workbook/stage59_energy_ml'
ART = REPO/'ml/artifacts/stage59'
INPUTS = ['pz', 'timing', 'clusters', 'calo']
NPARAM = 59  # 4*8+8+8*2+2 + a scalar F7/softmax blend


def features(d):
    """Primitive readouts only; signed charges/energies are never clipped."""
    p, timing, counts, calo = [np.asarray(d[k], dtype=float) for k in INPUTS]
    active = np.isfinite(p)&np.isfinite(timing)&np.isfinite(counts)&np.isfinite(calo)
    active &= (p>=50)&(p<250)&(counts>=0)
    out = np.zeros((len(p),4))
    out[active] = np.column_stack([np.log(p[active]), np.arcsinh(timing[active]),
                                  np.log1p(counts[active]), np.arcsinh(calo[active])])
    return out, active


def standardized(d, protocol):
    f, active = features(d)
    f[active] = (f[active]-protocol['center'])/protocol['scale']
    return f, active


def initial_parameters(seed):
    rng = np.random.default_rng(seed)
    return np.r_[rng.normal(0,.5,(4,8)).ravel(), np.zeros(8),
                 rng.normal(0,.1/np.sqrt(8),(8,2)).ravel(), [-1.,-1.], 0.]


def unpack(theta):
    return theta[:32].reshape(4,8), theta[32:40], theta[40:56].reshape(8,2), theta[56:58], theta[58]


def forward(x, theta, delta, jacobian=False):
    """Return correction to F7 and optional exact derivatives of that correction."""
    w1,b1,w2,b2,rho = unpack(theta)
    hidden=np.tanh(x@w1+b1)
    logits=np.column_stack([hidden@w2+b2,np.zeros(len(x))])
    logits-=logits.max(axis=1,keepdims=True)
    prob=np.exp(logits);prob/=prob.sum(axis=1,keepdims=True)
    mixture=np.sum(prob[:,:2]*delta,axis=1)
    correction=rho*mixture
    effective=rho*prob;effective[:,2]+=1-rho
    if not jacobian:return correction,effective
    dl=rho*prob[:,:2]*(delta-mixture[:,None])
    dh=(dl@w2.T)*(1-hidden**2)
    jac=np.column_stack([(x[:,:,None]*dh[:,None,:]).reshape(len(x),32),dh,
                         (hidden[:,:,None]*dl[:,None,:]).reshape(len(x),16),dl,mixture])
    return correction,effective,jac


def predict(d, model, protocol, return_weights=False):
    """Deployment uses only the four measured inputs and the frozen F7 prediction."""
    x,active=standardized(d,protocol)
    base=np.asarray(d['raw_F7'])+model['offset_log']
    result=base.copy();weights=np.zeros((len(base),3));weights[:,2]=1
    delta=np.column_stack([np.log(d['pz'][active])-base[active],np.log(d['pz'][active]/.8)-base[active]])
    correction,w=forward(x[active],np.asarray(model['parameters']),delta)
    result[active]+=correction;weights[active]=w
    return (result,weights) if return_weights else result


class Risks:
    """Seven empirical risk ratios and gradients, using active rows only."""
    def __init__(self,d,protocol,offset):
        x,self.active=standardized(d,protocol);self.x=x[self.active]
        self.y=np.log(d['truth_E_GeV']);self.base=d['raw_F7']+offset
        self.error=self.base-self.y
        self.delta=np.column_stack([np.log(d['pz'][self.active])-self.base[self.active],
                                    np.log(d['pz'][self.active]/.8)-self.base[self.active]])
        self.keys=LOW+list(COST);mm=masks(d)
        self.mm=mm
        self.constants=[];weights=[]
        for key in self.keys:
            m=mm[key];assert m.any(), 'Report insufficient support rather than train on eval'
            ref=np.log(d['pz']/.8) if key in LOW else self.base
            denominator=np.mean((ref[m]-self.y[m])**2)
            self.constants.append(np.mean(self.error[m]**2)/denominator)
            weights.append(m[self.active].astype(float)/(m.sum()*denominator))
        self.constants=np.asarray(self.constants);self.weights=np.asarray(weights)
        self.last=None

    def evaluate(self,theta):
        if self.last is None or not np.array_equal(theta,self.last):
            self.last=theta.copy()
            correction,_,jac=forward(self.x,theta,self.delta,True)
            e=self.error[self.active]
            self.ratios=self.constants+self.weights@(2*e*correction+correction**2)
            self.gradients=(self.weights*(2*(e+correction))[None,:])@jac
        return self.ratios,self.gradients


def fit(d,protocol):
    """One bounded nonconvex optimization; never retries or scans starts."""
    start=time.perf_counter();cpu=time.process_time()
    offset=float(np.mean(np.log(d['truth_E_GeV'])-d['raw_F7']))
    risk=Risks(d,protocol,offset);theta=initial_parameters(protocol['seed'])
    initial_ratios,_=risk.evaluate(theta)
    v0=np.r_[theta,max(initial_ratios[:2])]
    epsilon=protocol['numerical_secondary_epsilon'];limits=np.array([COST[k]**2 for k in COST])
    def objective(v):
        ratios,grad=risk.evaluate(v[:-1])
        return float(v[-1]+epsilon*ratios[2]),np.r_[epsilon*grad[2],1.]
    def constraints(v):
        ratios,_=risk.evaluate(v[:-1])
        return np.r_[v[-1]-ratios[:2],limits-ratios[2:]]
    def constraint_jac(v):
        _,grad=risk.evaluate(v[:-1])
        return np.column_stack([-grad,np.r_[np.ones(2),np.zeros(5)]])
    # The scalar blend rho=0 is an exact feasible F7 reference, even though
    # finite softmax logits alone cannot assign exactly zero non-F7 weight.
    assert np.min(constraints(v0))>=-1e-12
    best=v0.copy();best_score=objective(v0)[0];history=[];budget_stop=False
    def callback(v):
        nonlocal best,best_score
        score=objective(v)[0];con=constraints(v);ratios,_=risk.evaluate(v[:-1])
        if np.min(con)>=-protocol['feasibility_tolerance'] and score<best_score:
            best=v.copy();best_score=score
        history.append(dict(iteration=len(history)+1,max_low_ratio=float(max(ratios[:2])),
                            maximum_violation=float(max(0,-np.min(con))),elapsed_s=time.perf_counter()-start))
        if time.perf_counter()-start>protocol['per_fit_wall_budget_s']:
            raise TimeoutError('Frozen per-fit wall budget reached')
    try:
        result=minimize(lambda v:objective(v)[0],v0,jac=lambda v:objective(v)[1],method='SLSQP',
                        bounds=[(-8,8)]*58+[(0,1),(0,None)],
                        constraints={'type':'ineq','fun':constraints,'jac':constraint_jac},callback=callback,
                        options={'ftol':protocol['optimizer_ftol'],'maxiter':protocol['optimizer_maxiter']})
        converged=bool(result.success)
        if converged and np.min(constraints(result.x))>=-protocol['feasibility_tolerance']:
            selected=result.x;selection='converged_final'
        else:selected=best;selection='best_training_feasible_nonconverged'
        status=int(result.status);message=str(result.message)
    except TimeoutError as exc:
        selected=best;selection='best_training_feasible_budget_stop';converged=False
        status=-1;message=str(exc);budget_stop=True
    ratios,_=risk.evaluate(selected[:-1]);con=constraints(selected)
    assert np.min(con)>=-protocol['feasibility_tolerance']
    return dict(parameters=selected[:-1].tolist(),offset_log=offset,train_N=len(d['pz']),
                active_N=int(risk.active.sum()),train_groups=sorted(set(d['group'])),
                risk_ratios=dict(zip(risk.keys,map(float,ratios))),max_low_MSE_ratio=float(max(ratios[:2])),
                maximum_constraint_violation=float(max(0,-np.min(con))),success=converged,
                optimizer_status=status,optimizer_message=message,selection=selection,budget_stop=budget_stop,
                iterations=len(history),rho=float(selected[-2]),history=history,
                wall_s=time.perf_counter()-start,cpu_s=time.process_time()-cpu,
                global_optimality_claimed=False)
