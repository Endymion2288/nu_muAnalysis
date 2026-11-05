"""Matched ordinary / risk-driven dictionaries and protected convex heads."""
import json
import time

import numpy as np
from scipy.optimize import minimize

from stage115_head import RiskHead
from stage117_common import ART, LAYERS, OUT, PROTECT, masks, save, table


def risk_terms(error, groups, weight, traditional, reference):
    """Gradient of smooth low-risk max plus squared protection violations.

    Trees use a positive diagonal curvature surrogate, omitting the nonlocal
    derivative of group multipliers. Exact group gradients drive every split;
    the subsequent common constrained solve is independent of this surrogate.
    """
    losses = []; parts = []; diag = []
    for name in LAYERS:
        m = groups[name]; ww = weight[m] / weight[m].sum()
        mse = float(ww @ error[m]**2); original = float(ww @ reference[m]**2)
        if name in LAYERS[:2]:
            scale = max(float(ww @ traditional[m]**2), 1e-4)
            losses.append(mse / scale); parts.append((name, m, ww, scale))
    temperature = .1
    soft = np.exp((np.array(losses)-max(losses))/temperature); soft /= soft.sum()
    grad = np.zeros(len(error)); hess = np.zeros(len(error))
    for multiplier, (name, m, ww, scale), loss in zip(soft, parts, losses):
        a = multiplier * ww / scale
        grad[m] += 2*a*error[m]; hess[m] += 2*a
        diag.append(dict(group=name, term='low_MSE_over_traditional', value=loss,
                         multiplier=float(multiplier), gradient_L1=float(np.sum(abs(2*a*error[m])))))
    for name in LAYERS:
        m=groups[name]; ww=weight[m]/weight[m].sum()
        for term in ['MSE','positive','negative']:
            if term == 'MSE':
                if name not in PROTECT: continue
                val=error[m]; old=reference[m]; derivative=np.ones(m.sum())
                scale=max(float(ww@old**2),1e-4); limit=PROTECT[name]**2
            elif term == 'positive':
                val=np.maximum(error[m]-np.log(1.5),0); old=np.maximum(reference[m]-np.log(1.5),0)
                derivative=(val>0).astype(float);scale=max(float(ww@old**2),1e-4);limit=float(ww@old**2)/scale
            else:
                val=np.maximum(np.log(.5)-error[m],0); old=np.maximum(np.log(.5)-reference[m],0)
                derivative=-(val>0).astype(float);scale=max(float(ww@old**2),1e-4);limit=float(ww@old**2)/scale
            risk=float(ww@val**2)/scale; multiplier=20*max(risk-limit,0)
            g=2*multiplier*ww*val*derivative/scale
            grad[m]+=g; hess[m]+=2*multiplier*ww*derivative**2/scale
            diag.append(dict(group=name,term=term,value=risk,limit=limit,multiplier=multiplier,
                             gradient_L1=float(np.sum(abs(g)))))
    return grad, hess, diag


def qa(x, d):
    ids=np.flatnonzero(d['role']==1)[:40]
    assert x.shape==(71376,110) and np.isfinite(d['base_raw']).all()
    # Analytic risk gradient checked independently using objective integrals.
    rng=np.random.default_rng(2026110517);n=40;e=rng.normal(0,.4,n);ref=e*.9
    groups={k:np.arange(n)%2==0 if k==LAYERS[0] else np.arange(n)%2==1 if k==LAYERS[1] else np.ones(n,bool) for k in LAYERS}
    w=np.ones(n);trad=rng.normal(0,.3,n)
    def value(v):
        low=[];penalty=0.
        for k,m in groups.items():
            mse=np.mean(v[m]**2);old=np.mean(ref[m]**2)
            if k in LAYERS[:2]:low.append(mse/max(np.mean(trad[m]**2),1e-4))
            if k in PROTECT:penalty+=10*max(mse/max(old,1e-4)-PROTECT[k]**2,0)**2
            for sign in [1,-1]:
                h=lambda a:np.maximum(a-np.log(1.5),0)**2 if sign==1 else np.maximum(np.log(.5)-a,0)**2
                b=np.mean(h(ref[m]));penalty+=10*(max((np.mean(h(v[m]))-b)/max(b,1e-4),0))**2
        z=np.array(low);return max(z)+.1*np.log(np.exp((z-max(z))/.1).sum())+penalty
    analytic,_,_=risk_terms(e,groups,w,trad,ref);numeric=[]
    for j in range(n):
        v=np.zeros(n);v[j]=1e-6;numeric.append((value(e+v)-value(e-v))/2e-6)
    delta=float(max(abs(analytic-numeric)));assert delta<1e-5
    # Reuse a small finite-difference check of all common head constraints.
    phi=rng.normal(size=(n,3));head=RiskHead(phi,e,trad,w,groups);v=np.r_[.01,-.02,.03,2.]
    jac=head.evaluate(v)[1];err=0.
    for j in range(4):
        step=np.zeros(4);step[j]=1e-6
        err=max(err,float(max(abs((head.evaluate(v+step)[0]-head.evaluate(v-step)[0])/2e-6-jac[:,j]))))
    assert err<1e-5
    save('QA.json',dict(passed=True,train_identities=d['row'][ids],new_QA_fits=0,
                       risk_gradient_max_abs=delta,head_gradient_max_abs=err,
                       pz0_raw110_typed_missing_checked_by_cached_inputs=True))


def dictionary(x, d, ids, base, weight, kind, name, params):
    import xgboost as xgb
    y=np.log(d['truth_E_GeV'][ids]);target=y-base
    dm=xgb.DMatrix(x[ids],label=target,weight=weight,nthread=1)
    cfg=dict(params,max_depth=3,min_child_weight=200,seed=2026110517,base_score=0.,boost_from_average=0)
    groups=masks({k:v[ids] for k,v in d.items()});ref=base-y;trad=np.log(d['pz'][ids]/.8)-y
    records=[]
    def obj(pred, matrix):
        g,h,diag=risk_terms(pred+ref,groups,weight,trad,ref)
        scale=weight.sum()/h.sum()
        for row in diag: row.update(round=len(records)//24+1,normalization_scale=scale)
        # There are 2 low + 6 MSE + 16 tail terms per round.
        records.extend(diag)
        return g*scale,np.maximum(h*scale,1e-12)
    model=xgb.train(cfg,dm,num_boost_round=8,obj=obj if kind=='stratified' else None)
    ART.mkdir(parents=True,exist_ok=True);model.save_model(ART/f'{name}_rules.ubj')
    reloaded=xgb.Booster(params={'nthread':1});reloaded.load_model(ART/f'{name}_rules.ubj')
    leaves=model.predict(dm,pred_leaf=True).astype(int)
    np.testing.assert_array_equal(leaves,reloaded.predict(dm,pred_leaf=True).astype(int))
    features=[]
    for j,text in enumerate(model.get_dump(dump_format='json',with_stats=True)):
        stack=[json.loads(text)]
        while stack:
            node=stack.pop()
            if 'split' in node:
                features.append(dict(tree=j,feature=node['split'],gain=node['gain'],cover=node['cover']))
                stack.extend(node['children'])
    table(f'{name}_splits.tsv',features);table(f'{name}_direction_gradients.tsv',records)
    return model,leaves


def solve(name, leaves, d, ids, base, weight):
    tick=time.perf_counter();cpu=time.process_time()
    codes=[np.unique(leaves[:,j]) for j in range(leaves.shape[1])]
    leaf_phi=np.column_stack([(leaves[:,j]==k).astype(float) for j in range(leaves.shape[1]) for k in codes[j]])
    gram=leaf_phi.T@(weight[:,None]*leaf_phi)/weight.sum();eig,vec=np.linalg.eigh(gram)
    keep=eig>1e-10*eig.max();transform=vec[:,keep]/np.sqrt(eig[keep]);phi=leaf_phi@transform
    np.testing.assert_allclose(phi.T@(weight[:,None]*phi)/weight.sum(),np.eye(keep.sum()),atol=1e-9,rtol=0)
    truth=np.log(d['truth_E_GeV'][ids]);groups=masks({k:v[ids] for k,v in d.items()})
    head=RiskHead(phi,base-truth,np.log(d['pz'][ids]/.8)-truth,weight,groups)
    n=phi.shape[1];v=np.zeros(n+1);v[-1]=max(c for q,b,c in head.low)
    constraint=dict(type='ineq',fun=lambda z:-head.evaluate(z)[0],jac=lambda z:-head.evaluate(z)[1])
    objective=lambda z:float(z[-1]);derivative=lambda z:np.r_[np.zeros(n),1.]
    first=minimize(objective,v,jac=derivative,constraints=[constraint],method='SLSQP',
                   options=dict(maxiter=250,ftol=1e-10))
    fd=head.diagnostics(first.x,derivative(first.x));cap=float(first.x[-1]+1e-8)
    second=minimize(lambda z:float(z[:-1]@z[:-1]),first.x,jac=lambda z:np.r_[2*z[:-1],0.],
        constraints=[constraint,dict(type='ineq',fun=lambda z:cap-z[-1],jac=lambda z:np.r_[np.zeros(n),-1.])],
        method='SLSQP',options=dict(maxiter=250,ftol=1e-10))
    sd=head.diagnostics(second.x,np.r_[2*second.x[:-1],0.],extra=cap)
    valid=all(r['max_normalized_violation']<=1e-7 for r in [fd,sd]) and np.isfinite(second.x).all()
    diag=dict(name=name,feasible=bool(valid),rank=n,leaves=leaf_phi.shape[1],trees=leaves.shape[1],
        primary=dict(success=bool(first.success),iterations=first.nit,objective=first.fun,**fd),
        secondary=dict(success=bool(second.success),iterations=second.nit,objective=second.fun,**sd),
        CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick)
    save(f'{name}_solve.json',diag)
    if not valid:raise RuntimeError(name+': fixed head numerical feasibility failure; no retry')
    model=dict(codes=[c.tolist() for c in codes],theta=(transform@second.x[:-1]).tolist(),
               tau=float(first.fun),new_offset=False,baseline_deployment='frozen Stage87 direct_cal')
    (ART/f'{name}_head.json').write_text(json.dumps(model,indent=2)+'\n')
    pred=base+leaf_phi@np.array(model['theta'])
    # Independent prediction-space check of every training protection.
    error=pred-truth;original=base-truth
    for layer,m in groups.items():
        if layer not in LAYERS:continue
        avg=lambda z:float(np.average(z[m],weights=weight[m]))
        if layer in PROTECT:assert avg(error**2)<=avg(original**2)*PROTECT[layer]**2+1e-7*max(avg(original**2),1e-4)+1e-12
        for sign in [1,-1]:
            h=lambda e:np.maximum(e-np.log(1.5),0)**2 if sign==1 else np.maximum(np.log(.5)-e,0)**2
            old=avg(h(original));assert avg(h(error))-old<=1e-7*max(old,1e-4)+1e-12
    return model,diag


def predict(tree, head, x):
    import xgboost as xgb
    leaves=tree.predict(xgb.DMatrix(x,nthread=1),pred_leaf=True,
                         iteration_range=(0,len(head['codes']))).astype(int)
    offset=0;correction=np.zeros(len(x));theta=np.array(head['theta'])
    for j,codes in enumerate(head['codes']):
        codes=np.array(codes);ix=np.searchsorted(codes,leaves[:,j]);np.testing.assert_array_equal(codes[ix],leaves[:,j])
        correction+=theta[offset+ix];offset+=len(codes)
    return correction
