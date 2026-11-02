"""Stage64 fixed-stratum response decomposition and linear sensitivity."""
import numpy as np

from audited_features import REPO
from expert_combination import begin, resources, save

OUT = REPO/'workbook/stage64_energy_ml'
REPRESENTATIONS = ['M_mu', 'S_scalar']
TERMS = ['mixture', 'conditional', 'unmatched', 'total']
COMPONENTS = ['low', 'high', 'combined']


def decompose(train, role):
    """Counts [truth component, stratum k, statistic bin]; no support pruning."""
    totals_t=train.sum(axis=(1,2));totals_r=role.sum(axis=(1,2))
    assert np.all(totals_t>0) and np.all(totals_r>0)
    nt=train.sum(axis=2);nr=role.sum(axis=2);shared=(nt>0)&(nr>0)
    wt=nt/totals_t[:,None];wr=nr/totals_r[:,None]
    rt=np.divide(train,nt[:,:,None],out=np.zeros_like(train,dtype=float),where=nt[:,:,None]>0)
    rr=np.divide(role,nr[:,:,None],out=np.zeros_like(role,dtype=float),where=nr[:,:,None]>0)
    jt=train/totals_t[:,None,None];jr=role/totals_r[:,None,None]
    by_k=np.stack([(wr-wt)[:,:,None]*rt*shared[:,:,None],
                   wr[:,:,None]*(rr-rt)*shared[:,:,None],
                   (jr-jt)*(~shared)[:,:,None]],axis=1)
    raw=(jr-jt).sum(axis=1);parts=by_k.sum(axis=2)
    vectors=np.concatenate([parts,raw[:,None,:]],axis=1)
    error=float(np.max(abs(parts.sum(axis=1)-raw)))
    unmatched=np.stack([(wt*(~shared)).sum(axis=1),(wr*(~shared)).sum(axis=1)],axis=1)
    return dict(vectors=vectors,by_k=by_k,shared=shared,
        unmatched_mass=unmatched,half_L1=.5*abs(vectors).sum(axis=2),conservation_error=error)


def linear_operator(mc, f, n=1000):
    totals=mc.sum(axis=1);a,b=mc/totals[:,None];q=f*a+(1-f)*b;use=q>0
    aa,bb,qq=a[use],b[use],q[use];contrast=aa-bb
    cov=(np.diag(qq)-np.outer(qq,qq))/n
    cov+=f*f*(np.diag(aa)-np.outer(aa,aa))/totals[0]
    cov+=(1-f)**2*(np.diag(bb)-np.outer(bb,bb))/totals[1]
    eigen,vec=np.linalg.eigh(cov);positive=eigen>max(eigen.max()*1e-12,1e-18)
    inverse_v=vec[:,positive]@((vec[:,positive].T@contrast)/eigen[positive])
    info=float(contrast@inverse_v);assert info>0
    operator=np.zeros(len(a));operator[use]=inverse_v/info
    return operator,dict(sigma_f=float(1/np.sqrt(info)),rank=int(positive.sum()),
                         unit_contrast_error=float(abs(operator@(a-b)-1)))


def project(vectors, operator, f):
    """Component contributions include their fixed nominal mixing fractions."""
    weighted=np.einsum('ctz,z->ct',vectors,operator)*np.array([f,1-f])[:,None]
    return np.vstack([weighted,weighted.sum(axis=0)])


def group_counts(d, p, role):
    take=d['role']==role;groups,gid=np.unique(d['group'][take],return_inverse=True)
    energy=np.searchsorted(p['truth_E_edges_GeV'],d['truth_E_GeV'][take],side='right')
    production=np.array([p['production_components'].index(str(v)) for v in d['component'][take]])
    layer=energy*len(p['production_components'])+production
    truth=(~d['low'][take]).astype(int);K=(len(p['truth_E_edges_GeV'])+1)*len(p['production_components'])
    out={}
    for name in REPRESENTATIONS:
        B=p['category_counts'][name];flat=((gid*2+truth)*K+layer)*B+d[name][take]
        out[name]=np.bincount(flat,minlength=len(groups)*2*K*B).reshape(len(groups),2,K,B)
        assert out[name].sum()==take.sum()
    return groups,gid,layer,out


def source_draws(groups, seed, repeats):
    rng=np.random.default_rng(seed);draw=np.zeros((repeats,len(groups)),int)
    for component in ['pi','k','charm']:
        idx=np.flatnonzero(np.char.startswith(groups,component+':'))
        if len(idx):draw[:,idx]=rng.multinomial(len(idx),np.full(len(idx),1/len(idx)),size=repeats)
    assert np.all(draw.sum(axis=1)==len(groups))
    return draw


def source_ess(draw, counts):
    number=counts.sum(axis=(2,3))
    sizes=np.column_stack([number.sum(axis=1),number])
    numerator=draw@sizes;denominator=(draw*draw)@sizes
    return numerator*numerator/denominator
