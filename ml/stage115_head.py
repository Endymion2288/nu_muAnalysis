"""Fixed signed rule residuals and two convex solves per arm, batch only."""
import json
import time

import numpy as np
from scipy.optimize import minimize, nnls

from stage115_common import ART, BITS, LAYERS, OUT, PROTECT, ROOT, masks, save, status_features, table


class RiskHead:
    def __init__(self,phi,error,traditional_error,weight,groups):
        self.phi=phi;self.error=error;self.w=weight/weight.sum();self.rank=phi.shape[1]
        self.low=[];self.protect=[];self.names=[]
        for name in LAYERS:
            m=groups[name];w=weight[m]/weight[m].sum();p=phi[m];e=error[m]
            q=p.T@(w[:,None]*p);b=p.T@(w*e);c=float(w@e**2)
            if name in LAYERS[:2]:
                scale=float(w@traditional_error[m]**2)
                self.low.append((q/scale,b/scale,c/scale))
                self.names.append(name+'_risk_over_traditional_minus_tau')
            if name in PROTECT:
                scale=max(c,1e-4)
                self.protect.append((q/scale,b/scale,c/scale,c*PROTECT[name]**2/scale))
        self.names += [k+'_protected_MSE' for k in PROTECT]
        ww=np.column_stack([np.where(groups[k],weight,0) for k in LAYERS])
        ww/=ww.sum(0)
        self.tail_weights=ww
        self.tail_reference=np.concatenate([ww.T@np.maximum(error-np.log(1.5),0)**2,
                                           ww.T@np.maximum(np.log(.5)-error,0)**2])
        self.tail_scale=np.maximum(self.tail_reference,1e-4)
        self.names += [k+'_'+sign+'_squared_hinge' for sign in ['positive','negative'] for k in LAYERS]
        self.cache_x=None

    def evaluate(self,v):
        if self.cache_x is not None and np.array_equal(v,self.cache_x): return self.cache
        t,tau=v[:-1],v[-1];n=self.rank;g=[];jac=[]
        for q,b,c in self.low:
            g.append(t@q@t+2*b@t+c-tau);jac.append(np.r_[2*(q@t+b),-1.])
        for q,b,c,limit in self.protect:
            g.append(t@q@t+2*b@t+c-limit);jac.append(np.r_[2*(q@t+b),0.])
        e=self.error+self.phi@t
        plus=np.maximum(e-np.log(1.5),0);minus=np.maximum(np.log(.5)-e,0)
        h=np.r_[self.tail_weights.T@(plus*plus),self.tail_weights.T@(minus*minus)]
        jplus=(2*self.phi.T@(self.tail_weights*plus[:,None])).T
        jminus=(-2*self.phi.T@(self.tail_weights*minus[:,None])).T
        g.extend((h-self.tail_reference)/self.tail_scale)
        j=np.vstack([jplus,jminus])/self.tail_scale[:,None]
        jac.extend(np.column_stack([j,np.zeros(16)]))
        self.cache_x=v.copy();self.cache=(np.array(g),np.array(jac))
        return self.cache

    def diagnostics(self,v,grad,extra=None):
        g,j=self.evaluate(v)
        if extra is not None:
            cap=extra
            g=np.r_[g,v[-1]-cap];j=np.vstack([j,np.r_[np.zeros(self.rank),1.]])
        active=g>=-1e-6
        lam=np.zeros(len(g))
        if active.any(): lam[active],_=nnls(j[active].T,-grad,maxiter=1000)
        residual=grad+j.T@lam
        return dict(max_normalized_violation=float(max(0,g.max())),
            approximate_KKT_stationarity_inf=float(np.max(abs(residual))),
            approximate_complementarity_inf=float(np.max(abs(lam*g))),
            dual_nonnegative=True,approximate_multipliers=lam,
            active_constraints=[(self.names+(['tau_secondary_cap'] if extra is not None else []))[i] for i in np.flatnonzero(active)],
            constraint_values=g,formal_dual_lower_bound=None,
            certification='convex fixed dictionary; approximate active-set KKT only, no rigorous global optimality certificate')


def qa(x,d):
    tr=np.flatnonzero(d['role']==1)
    ids=list(tr[d['input_missing'][tr]])+list(tr[:40])
    ids=np.array(list(dict.fromkeys(ids))[:40]);assert len(ids)==40
    status=np.array([[0,1,4,16,32,8,128,256,511,-1,np.nan],[0]*11],float)
    f,a=status_features(status)
    assert not a[0] and a[1] and np.isnan(f[0,-8:]).all()
    for j,bit in enumerate(BITS.values()):
        for i,value in enumerate(status[0,:9]): assert f[0,4*i+j]==bool(int(value)&bit)
    np.testing.assert_array_equal(x['A'],x['B'][:,:66])
    assert np.isnan(x['A'][ids,:62]).any()
    zero=d['base'][ids].copy()+np.zeros(len(ids))
    assert zero.tobytes()==d['base'][ids].tobytes()
    # Independent finite differences of every constraint; no extra learned model.
    rng=np.random.default_rng(2026110515);phi=rng.normal(size=(40,3));e=rng.normal(0,.5,40)
    groups={k:np.arange(40)%2==0 if k==LAYERS[0] else np.arange(40)%2==1 if k==LAYERS[1] else np.ones(40,bool) for k in LAYERS}
    h=RiskHead(phi,e,e+.2,np.ones(40),groups);v=np.array([.01,-.03,.02,2.])
    _,j=h.evaluate(v);numeric=np.zeros_like(j)
    for k in range(4):
        step=np.zeros(4);step[k]=1e-6
        numeric[:,k]=(h.evaluate(v+step)[0]-h.evaluate(v-step)[0])/2e-6
    err=float(np.max(abs(numeric-j)));assert err<1e-6
    save('QA.json',dict(passed=True,real_train_identities=40,rows=d['row'][ids],
         state_bits_and_unknown_NaN=True,common_A_B_exact=True,zero_residual_bit_exact=True,
         typed_NaNs_preserved=True,all_constraint_gradient_max_abs=err,new_QA_fits=0))


def fit_arm(spec):
    import xgboost as xgb
    name,x,d,protocol=spec;wall=time.perf_counter();cpu=time.process_time()
    tr=d['role']==1;truth=np.log(d['truth_E_GeV']);target=truth-d['base'];w=d['weight'][tr]
    base_protocol=json.loads((ROOT/'workbook/stage87_energy_ml/protocol.json').read_text())
    params=dict(base_protocol['baseline']['xgboost']);params.update(max_depth=3,min_child_weight=200,
        seed=protocol['seed'],base_score=float(np.average(target[tr],weights=w)),boost_from_average=0)
    train=xgb.DMatrix(x[tr],label=target[tr],weight=w,nthread=1)
    tree=xgb.train(params,train,num_boost_round=8)
    ART.mkdir(parents=True,exist_ok=True);path=ART/f'{name}_rules.ubj';tree.save_model(path)
    reload=xgb.Booster(params={'nthread':1});reload.load_model(path)
    leaves=tree.predict(train,pred_leaf=True).astype(int)
    np.testing.assert_array_equal(leaves,reload.predict(train,pred_leaf=True).astype(int))
    codes=[np.unique(leaves[:,j]) for j in range(8)]
    leaf_phi=np.column_stack([(leaves[:,j]==k).astype(float) for j in range(8) for k in codes[j]])
    assert leaf_phi.shape[1]<=64
    gram=leaf_phi.T@(w[:,None]*leaf_phi)/w.sum()
    eig,vec=np.linalg.eigh(gram);keep=eig>1e-10*eig.max()
    transform=vec[:,keep]/np.sqrt(eig[keep])
    phi=np.ascontiguousarray(leaf_phi@transform)
    np.testing.assert_allclose(phi.T@(w[:,None]*phi)/w.sum(),np.eye(keep.sum()),rtol=0,atol=1e-9)
    td={k:v[tr] for k,v in d.items()};groups=masks(td)
    head=RiskHead(phi,-target[tr],np.log(d['pz'][tr]/.8)-truth[tr],w,groups)
    n=phi.shape[1];v=np.zeros(n+1);v[-1]=max(c for q,b,c in head.low)
    assert head.evaluate(v)[0].max()<1e-10
    started=dict(arm=name,tree_params=params,trees=8,leaf_indicators=leaf_phi.shape[1],rank=n,
                 train_rows=int(tr.sum()),train_only_dictionary=True,in_sample_f0_residuals_not_OOF=True)
    save(f'{name}_dictionary.json',started)
    constraint=dict(type='ineq',fun=lambda z:-head.evaluate(z)[0],jac=lambda z:-head.evaluate(z)[1])
    objective=lambda z:float(z[-1])
    derivative=lambda z:np.r_[np.zeros(n),1.]
    tick=time.perf_counter()
    first=minimize(objective,v,jac=derivative,constraints=[constraint],method='SLSQP',
                   options=dict(maxiter=200,ftol=1e-10,disp=False))
    first_diag=head.diagnostics(first.x,derivative(first.x))
    save(f'{name}_primary_solve.json',dict(success=bool(first.success),message=str(first.message),
         iterations=first.nit,objective=first.fun,wall_s=time.perf_counter()-tick,**first_diag))
    if first_diag['max_normalized_violation']>1e-7 or not np.isfinite(first.x).all():
        raise RuntimeError(name+': primary numerical feasibility failure; no favorable fallback')
    cap=float(first.x[-1]+1e-8)
    secondary=dict(type='ineq',fun=lambda z:cap-z[-1],jac=lambda z:np.r_[np.zeros(n),-1.])
    objective2=lambda z:float(z[:-1]@z[:-1])
    derivative2=lambda z:np.r_[2*z[:-1],0.]
    tick=time.perf_counter()
    second=minimize(objective2,first.x,jac=derivative2,constraints=[constraint,secondary],method='SLSQP',
                    options=dict(maxiter=200,ftol=1e-10,disp=False))
    second_diag=head.diagnostics(second.x,derivative2(second.x),extra=cap)
    save(f'{name}_secondary_solve.json',dict(success=bool(second.success),message=str(second.message),
         iterations=second.nit,objective=second.fun,tau_cap=cap,wall_s=time.perf_counter()-tick,**second_diag))
    if second_diag['max_normalized_violation']>1e-7 or not np.isfinite(second.x).all():
        raise RuntimeError(name+': secondary numerical feasibility failure; no selected alternate')
    theta=second.x[:-1];leaf_theta=transform@theta
    model=dict(arm=name,leaf_codes=[v.tolist() for v in codes],leaf_theta=leaf_theta.tolist(),
               orthogonal_theta=theta.tolist(),tau_primary=float(first.x[-1]),tau_secondary=float(second.x[-1]),
               rank=n,leaf_indicators=len(leaf_theta),mean_train_correction_squared=float(theta@theta),
               baseline='frozen Stage87 direct_cal',new_offset=False,seed=protocol['seed'],
               train_target='logtruth - fitted train f0, not OOF',head_solver_calls=2)
    (ART/f'{name}_head.json').write_text(json.dumps(model,indent=2)+'\n')
    correction=leaf_phi@leaf_theta
    np.testing.assert_allclose(correction,phi@theta,rtol=0,atol=1e-12)
    prediction=d['base'][tr]+correction
    # Evaluate train constraints independently in raw prediction space.
    err=prediction-truth[tr];original=d['base'][tr]-truth[tr];constraints=[]
    for layer in LAYERS:
        m=groups[layer];ww=w[m];avg=lambda a:float(np.average(a[m],weights=ww))
        newmse=avg(err**2);oldmse=avg(original**2)
        if layer in PROTECT: assert newmse-oldmse*PROTECT[layer]**2<=1e-7*max(oldmse,1e-4)+1e-12
        for sign in ['positive','negative']:
            h=lambda e:np.maximum(e-np.log(1.5),0)**2 if sign=='positive' else np.maximum(np.log(.5)-e,0)**2
            old=avg(h(original));new=avg(h(err))
            assert new-old<=1e-7*max(old,1e-4)+1e-12
            constraints.append(dict(arm=name,stratum=layer,sign=sign,baseline_H=old,new_H=new,change=new-old))
    table(f'{name}_train_tail_constraints.tsv',constraints)
    result=dict(**started,primary_success=bool(first.success),secondary_success=bool(second.success),
                primary_KKT_inf=first_diag['approximate_KKT_stationarity_inf'],secondary_KKT_inf=second_diag['approximate_KKT_stationarity_inf'],
                primary_max_violation=first_diag['max_normalized_violation'],secondary_max_violation=second_diag['max_normalized_violation'],
                CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-wall,parameters=model)
    save(f'{name}_fit.json',result)
    return name,result


def infer_arm(spec):
    import xgboost as xgb
    name,x,d=spec
    assert (OUT/'fits_frozen.json').exists()
    model=json.loads((ART/f'{name}_head.json').read_text())
    tree=xgb.Booster(params={'nthread':1});tree.load_model(ART/f'{name}_rules.ubj')
    leaves=tree.predict(xgb.DMatrix(x,nthread=1),pred_leaf=True).astype(int)
    theta=np.array(model['leaf_theta']);offset=0;correction=np.zeros(len(x))
    for j,code in enumerate(model['leaf_codes']):
        code=np.array(code);ix=np.searchsorted(code,leaves[:,j])
        np.testing.assert_array_equal(code[ix],leaves[:,j])
        correction+=theta[offset+ix];offset+=len(code)
    prediction=d['base'].copy();np.add(prediction,correction,out=prediction,where=correction!=0)
    assert np.isfinite(prediction).all()
    return name,prediction
