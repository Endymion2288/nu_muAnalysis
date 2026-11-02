"""Analytic feasible rho profile for the unchanged stage59 gate family."""
import time

import numpy as np
from scipy.optimize import minimize

from expert_combination import REPO,LOW,COST
from lightweight_gate import Risks,forward,initial_parameters

OUT=REPO/'workbook/stage60_energy_ml'
ART=REPO/'ml/artifacts/stage60'


def polynomial_roots(a,b,c):
    """Real roots, scaled and cancellation-safe; negligible coefficients only."""
    scale=max(abs(a),abs(b),abs(c))
    if scale==0:return []
    a,b,c=a/scale,b/scale,c/scale
    if abs(a)<1e-14:
        return [-c/b] if abs(b)>=1e-14 else []
    discriminant=b*b-4*a*c
    tolerance=16*np.finfo(float).eps*(b*b+abs(4*a*c))
    if discriminant < -tolerance:return []
    root=np.sqrt(max(0.,discriminant))
    q=-.5*(b+np.copysign(root,b))
    return [q/a,c/q] if q!=0 else [0.]


def feasible_cap(coefficients,limits):
    """Each cost quadratic starts feasible at rho=0, hence one feasible interval."""
    caps=[]
    for (a,b,c),limit in zip(coefficients,limits):
        assert a>=0 and c<=limit+1e-12
        if a+b+c<=limit:
            cap=1.
        else:
            slack=max(0.,limit-c)
            if a==0:cap=slack/b
            elif b>=0:cap=2*slack/(b+np.sqrt(b*b+4*a*slack))
            else:cap=(-b+np.sqrt(b*b+4*a*slack))/(2*a)
            cap=float(np.nextafter(min(1.,max(0.,cap)),0.))
        caps.append(cap)
    return float(min(caps)),caps


def profile(coefficients,epsilon):
    """Exact 1D minimax candidates: ends, active quadratic minima, intersections."""
    limits=np.array([COST[k]**2 for k in COST])
    cap,caps=feasible_cap(coefficients[2:],limits)
    effective=coefficients[:2]+epsilon*coefficients[2]
    candidates=[0.,cap]
    for a,b,_ in effective:
        if a>0:
            vertex=-b/(2*a)
            if 0<=vertex<=cap:candidates.append(float(vertex))
    for root in polynomial_roots(*(coefficients[0]-coefficients[1])):
        if -1e-14<=root<=cap+1e-14:candidates.append(float(np.clip(root,0,cap)))
    candidates=np.unique(candidates)
    values=np.array([np.max(effective@np.array([r*r,r,1.])) for r in candidates])
    chosen=int(np.argmin(values));rho=float(candidates[chosen])
    ratios=coefficients@np.array([rho*rho,rho,1.])
    assert np.max(ratios[2:]-limits)<1e-10
    return dict(rho=rho,rho_max=cap,individual_cost_caps=dict(zip(COST,map(float,caps))),
                objective=float(values[chosen]),risk_ratios=dict(zip(LOW+list(COST),map(float,ratios))),
                max_low_MSE_ratio=float(max(ratios[:2])),
                cost_slacks=dict(zip(COST,map(float,limits-ratios[2:]))),
                maximum_constraint_violation=float(max(0.,np.max(ratios[2:]-limits))),
                inner_candidate_count=len(candidates))


class ProfiledRisk:
    def __init__(self,d,protocol,offset):
        self.risk=Risks(d,protocol,offset)
        self.epsilon=protocol['numerical_secondary_epsilon']
        self.last=None;self.evaluations=0

    def evaluate(self,theta):
        if self.last is None or not np.array_equal(theta,self.last):
            self.last=np.asarray(theta).copy();self.evaluations+=1
            delta=forward(self.risk.x,np.r_[theta,1.],self.risk.delta)[0]
            A=self.risk.weights@(delta*delta)
            B=2*self.risk.weights@(self.risk.error[self.risk.active]*delta)
            self.coefficients=np.column_stack([A,B,self.risk.constants])
            self.details=profile(self.coefficients,self.epsilon)
        return self.details


def projected_gradient(theta,gradient):
    g=np.asarray(gradient).copy()
    g[theta<=-8+1e-8]=np.minimum(g[theta<=-8+1e-8],0)
    g[theta>=8-1e-8]=np.maximum(g[theta>=8-1e-8],0)
    return g


def fit(d,p):
    start=time.perf_counter();cpu=time.process_time()
    offset=float(np.mean(np.log(d['truth_E_GeV'])-d['raw_F7']))
    risk=ProfiledRisk(d,p,offset);initial=initial_parameters(p['seed'])[:-1]
    initial_details=risk.evaluate(initial).copy()
    best=initial.copy();best_value=initial_details['objective'];trace=[];last=initial.copy()
    def objective(theta):
        nonlocal last
        if time.perf_counter()-start>p['per_fit_wall_budget_s']:
            raise TimeoutError('Frozen per-fit wall budget reached')
        last=theta.copy()
        return risk.evaluate(theta)['objective']
    def callback(theta):
        nonlocal best,best_value
        detail=risk.evaluate(theta)
        if detail['objective']<best_value:best=theta.copy();best_value=detail['objective']
        trace.append(dict(iteration=len(trace)+1,objective=detail['objective'],
                          max_low_MSE_ratio=detail['max_low_MSE_ratio'],rho=detail['rho'],rho_max=detail['rho_max'],
                          maximum_constraint_violation=detail['maximum_constraint_violation'],elapsed_s=time.perf_counter()-start))
    try:
        result=minimize(objective,initial,method='L-BFGS-B',jac='2-point',bounds=[(-8,8)]*58,callback=callback,
            options={'maxiter':p['optimizer_maxiter'],'maxfun':p['optimizer_maxfun'],'ftol':p['optimizer_ftol'],
                     'gtol':p['optimizer_gtol'],'finite_diff_rel_step':p['finite_difference_rel_step'],'maxls':20})
        terminal=result.x.copy();terminal_details=risk.evaluate(terminal).copy()
        success=bool(result.success);message=str(result.message);status=int(result.status)
        selected=terminal if success else best
        grad=np.asarray(result.jac).tolist();pg=float(np.max(abs(projected_gradient(terminal,result.jac))))
        nit=int(result.nit);nfev=int(result.nfev)
    except TimeoutError as exc:
        terminal=last.copy();terminal_details=risk.evaluate(terminal).copy()
        selected=best;success=False;message=str(exc);status=-1;grad=None;pg=None
        nit=len(trace);nfev=risk.evaluations
    detail=risk.evaluate(selected).copy()
    # Independent coordinate probes report local directional decreases even
    # when the profiled objective is nonsmooth. They are diagnostics, no refit.
    base=terminal_details['objective'];drops={}
    for step in p['stationarity_probe_steps']:
        maximum=0.
        for j in range(58):
            for sign in [-1,1]:
                probe=terminal.copy();probe[j]=np.clip(probe[j]+sign*step,-8,8)
                maximum=max(maximum,base-risk.evaluate(probe)['objective'])
        drops[str(step)]=float(maximum)
    selected_parameters=np.r_[selected,detail['rho']].tolist()
    return dict(parameters=selected_parameters,offset_log=offset,train_N=len(d['pz']),active_N=int(risk.risk.active.sum()),
        train_groups=sorted(set(d['group'])),success=success,optimizer_status=status,optimizer_message=message,
        iterations=nit,function_evaluations=nfev,selection='converged_terminal' if success else 'best_training_profiled_callback',
        risk_ratios=detail['risk_ratios'],max_low_MSE_ratio=detail['max_low_MSE_ratio'],rho=detail['rho'],rho_max=detail['rho_max'],
        cost_slacks=detail['cost_slacks'],maximum_constraint_violation=detail['maximum_constraint_violation'],
        initial_profile=initial_details,selected_profile=detail,
        terminal_parameters=np.r_[terminal,terminal_details['rho']].tolist(),terminal_profile=terminal_details,
        terminal_optimizer_gradient=grad,terminal_projected_gradient_max_abs=pg,
        terminal_coordinate_objective_decreases=drops,history=trace,
        wall_s=time.perf_counter()-start,cpu_s=time.process_time()-cpu,
        global_optimality_claimed=False,stationarity_note='forward finite-difference gradient and coordinate probes; nonsmooth profile, no general local/global optimality certificate')
