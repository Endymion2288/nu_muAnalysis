"""Stage78 nested source-safe conditional combinations of fixed log experts."""
import json
import numpy as np
from scipy.optimize import minimize
from sklearn.tree import DecisionTreeRegressor
from support_augmentation import (REPO, arrays, begin, resources, save, table,
    masks, metrics, indicator, boot_weights, LOW, COST, TAILS)
from energy_reweight import ENERGY, support, finite, weights
from group_risk import training_split

OUT=REPO/'workbook/stage78_energy_ml'
ART=REPO/'ml/artifacts/stage78'
CACHE=REPO/'ntuples/energy_ml_stage78'
JOBS=['fold0','fold1','fold2','final']
ARMS=['Q0','Q_local']


def subset(d, m):return {k:v[m] for k,v in d.items()}


def diagnostic_masks(d):
    out=masks(d)
    for k in LOW+['E200_inf']:
        out['pz50_100_'+k]=out['pz50_100']&out[k]
    return out


def inner_splits(d,p,job):
    outer,held,_=training_split(d,p,job)
    assert held is not None
    fold=np.full(len(outer),-1)
    fold[d['role']=='train']=[p['fold_by_group'][str(g)] for g in d['group'][d['role']=='train']]
    for k in sorted(set(fold[outer])):
        ih=outer&(fold==k);candidate=outer&~ih
        keys=set(map(tuple,d['incoming'][ih]))
        purge=np.array([bool(candidate[i]) and tuple(v) in keys for i,v in enumerate(d['incoming'])])
        it=candidate&~purge
        assert not set(d['group'][it])&set(d['group'][ih])
        assert not set(map(tuple,d['incoming'][it]))&keys
        assert not np.any(it&~outer) and not np.any(ih&~outer)
        yield int(k),it,ih,purge


def preprocessing(x):
    med=[]
    for col in x.T:
        good=col[np.isfinite(col)]
        med.append(float(np.median(good)) if len(good) else 0.)
    return np.array(med)


def transformed(x, median):
    missing=~np.isfinite(x)
    return np.c_[np.where(missing,median,x),missing].astype('float32')


def fit_partition(x,h,y,p):
    delta=np.c_[(h[:,0]-y)**2-(h[:,1]-y)**2,(h[:,0]-y)**2-(h[:,2]-y)**2]
    rms=np.sqrt(np.mean(delta**2,axis=0))
    target=np.divide(delta,rms,out=np.zeros_like(delta),where=rms>0)
    median=preprocessing(x);xx=transformed(x,median)
    tree=DecisionTreeRegressor(max_depth=3,min_samples_leaf=200,criterion='squared_error',random_state=p['partition_seed'])
    tree.fit(xx,target);t=tree.tree_;leaf=tree.apply(xx)
    obj=dict(median=median.tolist(),target_RMS=rms.tolist(),target_zero_RMS=(rms==0).tolist(),
        children_left=t.children_left.tolist(),children_right=t.children_right.tolist(),
        feature=t.feature.tolist(),threshold=t.threshold.tolist(),leaf_ids=np.unique(leaf).tolist(),
        feature_importances=tree.feature_importances_.tolist(),training_N=len(x),max_depth=3,min_samples_leaf=200,
        seed=p['partition_seed'],inputs='62 reco finite medians +62 missing masks; no labels in deployment')
    np.testing.assert_array_equal(route(x,obj),np.searchsorted(obj['leaf_ids'],leaf))
    assert len(obj['leaf_ids'])<=8
    return obj


def route(x,obj):
    """Deployment depends only on reco; thresholds match sklearn float32 inputs."""
    xx=transformed(x,np.array(obj['median']));node=np.zeros(len(x),int)
    left=np.array(obj['children_left']);right=np.array(obj['children_right'])
    feature=np.array(obj['feature']);threshold=np.array(obj['threshold'])
    for _ in range(4):
        use=left[node]>=0
        if not use.any():break
        ii=np.flatnonzero(use);nn=node[use]
        node[ii]=np.where(xx[ii,feature[nn]]<=threshold[nn],left[nn],right[nn])
    assert np.all(left[node]<0)
    out=np.searchsorted(obj['leaf_ids'],node)
    np.testing.assert_array_equal(np.array(obj['leaf_ids'])[out],node)
    return out


def predict_head(x,h,obj,arm):
    leaf=np.zeros(len(x),int) if arm=='Q0' else route(x,obj['partition'])
    w=np.array(obj['solutions'][arm]['weights'])
    return np.einsum('ij,ij->i',w[leaf],h)


def moment_matrices(h,y,leaf,mm,L):
    e=h-y[:,None]
    return {k:np.array([e[m&(leaf==l)].T@e[m&(leaf==l)]/m.sum() for l in range(L)]) for k,m in mm.items()}


def risk(C,w):return float(np.einsum('li,lij,lj->',w,C,w))


def gradient(C,w):return (2*np.einsum('lij,lj->li',C,w)).ravel()


def solve_combination(h,y,leaf,dd,p):
    """Two deterministic analytic-gradient SLSQP calls for one convex QC problem."""
    start=begin();L=int(leaf.max())+1;mm=diagnostic_masks(dd)
    keys=LOW+list(COST);mm={k:mm[k] for k in keys}
    assert all(m.any() for m in mm.values())
    raw=moment_matrices(h,y,leaf,mm,L)
    denom={k:float(np.mean((h[mm[k],2 if k in LOW else 0]-y[mm[k]])**2)) for k in keys}
    C={k:raw[k]/denom[k] for k in keys}
    cap={k:v*v for k,v in COST.items()}
    initial=np.zeros((L,3));initial[:,0]=1
    tau0=max(risk(C[k],initial) for k in LOW)
    eq=np.zeros((L,L*3+1))
    for l in range(L):eq[l,l*3:l*3+3]=1
    def ineq(z):
        w=z[:-1].reshape(L,3)
        return np.array([z[-1]-risk(C[k],w) for k in LOW]+[cap[k]-risk(C[k],w) for k in COST])
    def ijac(z):
        w=z[:-1].reshape(L,3)
        return np.array([np.r_[-gradient(C[k],w),1.] for k in LOW]+[np.r_[-gradient(C[k],w),0.] for k in COST])
    def check(w,tau):
        vals={k:risk(C[k],w) for k in keys}
        direct={k:float(np.mean((np.einsum('ij,ij->i',w[leaf[mm[k]]],h[mm[k]])-y[mm[k]])**2)/denom[k]) for k in keys}
        identity=max(abs(vals[k]-direct[k]) for k in keys)
        return dict(normalized_MSE=direct,slack={k:cap[k]-direct[k] for k in COST},
            low_tau_slack={k:tau-direct[k] for k in LOW},risk_matrix_direct_max_abs_diff=identity,
            simplex_max_abs_diff=float(abs(w.sum(1)-1).max()),minimum_weight=float(w.min()))
    opt=dict(ftol=p['solver_ftol'],maxiter=p['solver_maxiter'],disp=False)
    res=minimize(lambda z:z[-1],np.r_[initial.ravel(),tau0],jac=lambda z:np.r_[np.zeros(L*3),1.],
        method='SLSQP',bounds=[(0.,1.)]*(L*3)+[(0.,None)],
        constraints=[dict(type='eq',fun=lambda z:eq@z-1,jac=lambda z:eq),dict(type='ineq',fun=ineq,jac=ijac)],options=opt)
    primary=res.x.copy();w=primary[:-1].reshape(L,3);tau=float(primary[-1]);qa=check(w,tau)
    def qualified(r,q):
        return bool(r.success and np.isfinite(r.x).all() and q['minimum_weight']>=-1e-8 and q['simplex_max_abs_diff']<1e-8
            and min(list(q['slack'].values())+list(q['low_tau_slack'].values()))>=-p['solver_feasibility_tolerance'] and q['risk_matrix_direct_max_abs_diff']<1e-10)
    primary_ok=qualified(res,qa)
    log=[dict(phase='primary',success=bool(res.success),status=int(res.status),message=str(res.message),iterations=int(res.nit),
        qualified=primary_ok,tau=tau,objective=float(res.fun),**qa)]
    if not primary_ok:
        return dict(solved=False,weights=None,solver_calls=1,records=log,**resources(start))
    # Same predeclared secondary criterion for every split. No solver/parameter retry.
    freq=np.bincount(leaf,minlength=L)/len(leaf)
    limit=tau+p['secondary_tau_tolerance']
    def sin(z):
        ww=z.reshape(L,3)
        return np.array([limit-risk(C[k],ww) for k in LOW]+[cap[k]-risk(C[k],ww) for k in COST])
    def sj(z):
        ww=z.reshape(L,3);return np.array([-gradient(C[k],ww) for k in keys])
    secondary=minimize(lambda z:float(np.sum(freq[:,None]*(z.reshape(L,3)-initial)**2)),w.ravel(),
        jac=lambda z:(2*freq[:,None]*(z.reshape(L,3)-initial)).ravel(),method='SLSQP',bounds=[(0.,1.)]*(L*3),
        constraints=[dict(type='eq',fun=lambda z:eq[:,:-1]@z-1,jac=lambda z:eq[:,:-1]),dict(type='ineq',fun=sin,jac=sj)],options=opt)
    ww=secondary.x.reshape(L,3);q2=check(ww,limit);secondary_ok=qualified(secondary,q2)
    log.append(dict(phase='secondary',success=bool(secondary.success),status=int(secondary.status),message=str(secondary.message),
        iterations=int(secondary.nit),qualified=secondary_ok,tau_cap=limit,objective=float(secondary.fun),**q2))
    # An unresolved prescribed tie-break is a numerical failure, never a new policy.
    return dict(solved=secondary_ok,weights=ww.tolist() if secondary_ok else None,selected_phase='secondary',
        secondary_solved=secondary_ok,primary_tau=tau,solver_calls=2,records=log,
        training_leaf_counts=np.bincount(leaf,minlength=L).tolist(),denominators=denom,**resources(start))
