"""Stage63 fixed binnings and conditional multinomial finite-template inference."""
import numpy as np
from scipy.optimize import minimize, minimize_scalar, brentq

from audited_features import REPO
from expert_combination import begin, resources, save

OUT = REPO/'workbook/stage63_energy_ml'
ART = REPO/'ml/artifacts/stage63'
REPRESENTATIONS = ['M_mu', 'S_scalar', 'J_joint']


def internal_quantiles(v, n):
    return np.unique(np.quantile(v[np.isfinite(v)], np.arange(1,n)/n)).tolist()


def binning(m, s):
    cut=internal_quantiles(m,4);layer=np.searchsorted(cut,m,side='right')
    return dict(M_edges=internal_quantiles(m,16),S_edges=internal_quantiles(s,16),
                J_M_edges=cut,J_delta_edges=[internal_quantiles((s-m)[layer==j],4) for j in range(len(cut)+1)])


def assign(m,s,p):
    """No truth/status/other features enter a statistic's categorical map."""
    b=p['binning'];out={}
    for name,v,edges in [('M_mu',m,b['M_edges']),('S_scalar',s,b['S_edges'])]:
        idx=np.searchsorted(edges,v,side='right');idx[~np.isfinite(v)]=len(edges)+1
        out[name]=idx
    layer=np.searchsorted(b['J_M_edges'],m,side='right');delta=s-m
    sizes=[len(e)+1 for e in b['J_delta_edges']];offset=np.r_[0,np.cumsum(sizes)]
    idx=np.full(len(m),int(offset[-1]),int)
    for j,edges in enumerate(b['J_delta_edges']):
        use=(layer==j)&np.isfinite(m)&np.isfinite(delta)
        idx[use]=offset[j]+np.searchsorted(edges,delta[use],side='right')
    out['J_joint']=idx
    return out


def category_counts(p):
    b=p['binning']
    return dict(M_mu=len(b['M_edges'])+2,S_scalar=len(b['S_edges'])+2,
                J_joint=1+sum(len(e)+1 for e in b['J_delta_edges']))


def histogram(index,low,weights,n):
    return np.array([np.bincount(index[low],weights=weights[low],minlength=n),
                     np.bincount(index[~low],weights=weights[~low],minlength=n)])


def fraction_to_r(f,f0):
    return float(f*(1-f0)/(f0*(1-f))) if f<1 else None


def multinomial_kl(counts,probability):
    use=counts>0
    if np.any(probability[use]<=0):return np.inf
    return float(counts[use]@np.log(counts[use]/counts.sum()/probability[use]))


class TemplateLikelihood:
    def __init__(self,mc,data,p,finite=True):
        mc=np.asarray(mc,float);data=np.asarray(data,float)
        assert mc.shape==(2,len(data)) and np.all(mc>=0) and np.all(data>=0)
        self.used=(mc.sum(axis=0)+data)>0
        self.mc=mc[:,self.used];self.data=data[self.used]
        self.totals=self.mc.sum(axis=1);assert np.all(self.totals>0)
        self.response=self.mc/self.totals[:,None];self.p=p;self.finite=finite
        self.calls=0;self.max_iterations=0;self.max_kkt=0.;self.cache={};self.fallbacks=0;self.max_dual_iterations=0

    def dual_allocation(self,f):
        """Exact convex profile via the total data allocation T, including zeros.

        KKT gives a_i=(mLi+t_i)/(ML+T), b_i=(mHi+d_i-t_i)/(MH+N-T).
        For fixed T each t_i is the physical quadratic root in [0,d_i].
        sum(t_i(T))-T is monotone. No probability floors or pseudocounts.
        """
        A,B=self.mc;D=self.data;N=D.sum();ML,MH=self.totals
        empty=(A+B)==0
        def allocation(T,empty_share=None):
            c=f/(ML+T);h=(1-f)/(MH+N-T);aa=c-h
            bb=c*A+h*B-aa*D;cc=c*A*D
            disc=np.sqrt(np.maximum(bb*bb+4*aa*cc,0))
            t=np.zeros_like(D);positive=bb>=0
            np.divide(2*cc,bb+disc,out=t,where=positive&((bb+disc)>0))
            if aa!=0:t[~positive]=(-bb[~positive]+disc[~positive])/(2*aa)
            t=np.clip(t,0,D)
            t[empty]=D[empty]*(1. if c>h else 0.)
            if empty_share is not None:t[empty]=D[empty]*empty_share
            return t
        # At c=h, a data-only category has a set-valued allocation; distribute
        # its mass to satisfy the simplex instead of crossing a discontinuity.
        knot=f*(MH+N)-(1-f)*ML
        special=False
        if empty.any() and 0<=knot<=N:
            t=allocation(knot,0.);required=knot-t.sum();available=D[empty].sum()
            if available>0 and 0<=required<=available:
                T=knot;t=allocation(T,required/available);special=True
        if not special:
            def root(T):return allocation(T).sum()-T
            if root(0)==0:T=0.;nit=0
            elif root(N)==0:T=N;nit=0
            else:
                T,result=brentq(root,0,N,xtol=self.p['dual_allocation_xtol'],full_output=True)
                assert result.converged;nit=result.iterations
            t=allocation(T);self.max_dual_iterations=max(self.max_dual_iterations,nit)
        a=(A+t)/(ML+T);b=(B+D-t)/(MH+N-T)
        np.testing.assert_allclose([a.sum(),b.sum()],1,rtol=0,atol=1e-10)
        return a,b

    def convex_polish(self,f,a,b):
        """Analytic-gradient SLSQP for slow EM boundary cells; same likelihood."""
        k=len(a);scale=self.totals.sum()+self.data.sum();d=self.data
        def objective(x):
            aa,bb=x[:k],x[k:];q=f*aa+(1-f)*bb
            value=multinomial_kl(d,q)+multinomial_kl(self.mc[0],aa)+multinomial_kl(self.mc[1],bb)
            gq=np.divide(d,q,out=np.zeros_like(q),where=q>0)
            ga=-np.divide(self.mc[0],aa,out=np.zeros_like(aa),where=aa>0)-f*gq
            gb=-np.divide(self.mc[1],bb,out=np.zeros_like(bb),where=bb>0)-(1-f)*gq
            return value/scale,np.r_[ga,gb]/scale
        jac=np.zeros((2,2*k));jac[0,:k]=1;jac[1,k:]=1
        # Positive-count cells alone have a numerical lower bound; zero-MC
        # cells can be exactly zero. This adds no events to the objective.
        lower=np.where(self.mc.ravel()>0,self.p['simplex_positive_floor'],0.)
        result=minimize(objective,np.maximum(np.r_[a,b],lower),jac=True,method='SLSQP',
            bounds=list(zip(lower,np.ones(2*k))),
            constraints=[dict(type='eq',fun=lambda x:jac@x-1,jac=lambda x:jac)],
            options={'ftol':self.p['simplex_ftol'],'maxiter':self.p['simplex_maxiter']})
        assert result.success,(f,result.message)
        self.fallbacks+=1
        return result.x[:k],result.x[k:]

    def evaluate(self,f):
        f=float(f)
        if f in self.cache:return self.cache[f]
        self.calls+=1
        a,b=self.response.copy();d=self.data
        if self.finite:
            if f==0:
                b=(self.mc[1]+d)/(self.totals[1]+d.sum());nit=1
            elif f==1:
                a=(self.mc[0]+d)/(self.totals[0]+d.sum());nit=1
            elif self.p.get('solver')=='dual_allocation_root':
                a,b=self.dual_allocation(f);nit=0
            else:
                # Strictly positive initialisation is not a pseudocount in the objective.
                a=np.maximum(a,self.p['EM_initial_probability']);a/=a.sum()
                b=np.maximum(b,self.p['EM_initial_probability']);b/=b.sum()
                for nit in range(1,self.p['EM_maxiter']+1):
                    q=f*a+(1-f)*b
                    z=np.divide(f*a,q,out=np.zeros_like(q),where=q>0)
                    assigned=d*z
                    na=(self.mc[0]+assigned)/(self.totals[0]+assigned.sum())
                    nb=(self.mc[1]+d-assigned)/(self.totals[1]+d.sum()-assigned.sum())
                    change=max(np.max(abs(na-a)),np.max(abs(nb-b)));a,b=na,nb
                    if change<self.p['EM_probability_tolerance']:break
                else:a,b=self.convex_polish(f,a,b)
            q=f*a+(1-f)*b
            # Convex fixed-f problem: simplex KKT, including zero-count boundaries.
            violations=[]
            for counts,prob,coefficient in [(self.mc[0],a,f),(self.mc[1],b,1-f)]:
                grad=-np.divide(counts,prob,out=np.zeros_like(prob),where=prob>0)
                grad-=coefficient*np.divide(d,q,out=np.zeros_like(q),where=q>0)
                lam=-grad@prob;active=prob>self.p['EM_active_probability']
                residual=grad+lam
                error=max(np.max(abs(residual[active]),initial=0),np.max(np.maximum(-residual[~active],0),initial=0))
                violations.append(error/(counts.sum()+d.sum()))
            kkt=max(violations)
            assert kkt<self.p['EM_KKT_tolerance'],(f,kkt,nit)
            value=multinomial_kl(d,q)+multinomial_kl(self.mc[0],a)+multinomial_kl(self.mc[1],b)
        else:
            nit=0;kkt=0.;q=f*a+(1-f)*b;value=multinomial_kl(d,q)
        self.max_iterations=max(self.max_iterations,nit);self.max_kkt=max(self.max_kkt,kkt)
        self.cache[f]=(value,a,b)
        return self.cache[f]

    def fit(self,f0):
        grid=np.linspace(0,1,self.p['fraction_bracket_points'])
        values=np.array([self.evaluate(f)[0] for f in grid])
        candidates=[(values[0],0.),(values[-1],1.)];terminations=[]
        brackets=[]
        if values[0]<=values[1]:brackets.append((grid[0],grid[1]))
        if values[-1]<=values[-2]:brackets.append((grid[-2],grid[-1]))
        # Refine every interior grid minimum; this is a fixed parameter profile,
        # never a search over binnings/models or physical uncertainty scenarios.
        for j in range(1,len(grid)-1):
            if values[j]<=values[j-1] and values[j]<=values[j+1]:
                brackets.append((grid[j-1],grid[j+1]))
        for bracket in brackets:
            result=minimize_scalar(lambda f:self.evaluate(f)[0],bounds=bracket,
                method='bounded',options={'xatol':self.p['fraction_xtol'],'maxiter':self.p['fraction_maxiter']})
            assert result.success,result.message
            candidates.append((float(result.fun),float(result.x)));terminations.append(dict(success=True,nfev=int(result.nfev)))
        value,fhat=min(candidates);a,b=self.evaluate(fhat)[1:]
        target=value+.5
        low=0. if self.evaluate(0)[0]<=target else float(brentq(lambda f:self.evaluate(f)[0]-target,0,fhat,xtol=self.p['fraction_xtol']))
        high=1. if self.evaluate(1)[0]<=target else float(brentq(lambda f:self.evaluate(f)[0]-target,fhat,1,xtol=self.p['fraction_xtol']))
        sig=information(np.array([a,b])*self.totals[:,None],fhat,self.data.sum(),self.finite)
        return dict(f_hat=fhat,r_hat=fraction_to_r(fhat,f0),f_low68=low,f_high68=high,
            r_low68=fraction_to_r(low,f0),r_high68=fraction_to_r(high,f0),
            boundary=bool(fhat<1e-8 or fhat>1-1e-8),interval_hits_boundary=bool(low==0 or high==1),
            twice_NLL_min=2*value,sigma_f=sig,relative_sigma_r=(sig/(fhat*(1-fhat))) if sig is not None and 0<fhat<1 else None,
            fraction_profile_calls=self.calls,max_EM_iterations=self.max_iterations,max_simplex_KKT=self.max_kkt,
            convex_polish_calls=self.fallbacks,
            max_dual_root_iterations=self.max_dual_iterations,
            scalar_terminations=terminations,
            grid_profile=[dict(f=float(f),twice_delta_NLL=float(2*(v-value)) if np.isfinite(v) else None) for f,v in zip(grid,values)],
            grid_global_check_pass=bool(value<=np.min(values)+1e-8))


def information(mc,f,n,finite=True):
    """Efficient joint multinomial Fisher via covariance of data minus templates.

    Equivalent to a simplex-nuisance Schur complement in the interior. At zero
    template cells it is a tangent Gaussian approximation, not boundary coverage.
    """
    if not 0<f<1:return None
    totals=mc.sum(axis=1)
    if np.any(totals<=0):return None
    a,b=mc/totals[:,None];q=f*a+(1-f)*b;use=q>0;a,b,q=a[use],b[use],q[use]
    v=(np.diag(q)-np.outer(q,q))/n
    if finite:v+=f*f*(np.diag(a)-np.outer(a,a))/totals[0]+(1-f)**2*(np.diag(b)-np.outer(b,b))/totals[1]
    contrast=a-b
    eigen,vec=np.linalg.eigh(v);positive=eigen>max(eigen.max()*1e-12,1e-18)
    info=float(np.sum((vec[:,positive].T@contrast)**2/eigen[positive]))
    return float(1/np.sqrt(info)) if info>1e-12 else None
