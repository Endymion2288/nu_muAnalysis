"""Stage65 local low-fraction / high-component hardness information."""
import numpy as np

from response_migration import (REPO,REPRESENTATIONS,TERMS,COMPONENTS,group_counts,
    source_draws,decompose,begin,resources,save)

OUT = REPO/'workbook/stage65_energy_ml'


def directions(mc,high_log_sum,f):
    totals=mc.sum(axis=1);a,b=mc/totals[:,None]
    mean=float(high_log_sum.sum()/totals[1])
    C=(high_log_sum-mean*mc[1])/totals[1]
    return np.column_stack([a-b,(1-f)*C]),C,mean


def covariance(mc,f,n,finite):
    totals=mc.sum(axis=1);a,b=mc/totals[:,None];q=f*a+(1-f)*b
    V=(np.diag(q)-np.outer(q,q))/n
    if finite:
        V+=f*f*(np.diag(a)-np.outer(a,a))/totals[0]
        V+=(1-f)**2*(np.diag(b)-np.outer(b,b))/totals[1]
    return V


def local_information(mc,high_log_sum,f,p,finite=True):
    D,C,mean=directions(mc,high_log_sum,f);V=covariance(mc,f,p['N_selected'],finite)
    eigen,vec=np.linalg.eigh(V)
    positive=eigen>max(eigen.max()*p['covariance_relative_cut'],p['covariance_absolute_cut'])
    W=(vec[:,positive]/eigen[positive])@vec[:,positive].T
    I=D.T@W@D;diag=I.diagonal();present=diag>p['direction_information_min']
    normal=np.zeros((2,2));normal[np.diag_indices(2)]=present.astype(float)
    rho=None
    if present.all():
        rho=float(I[0,1]/np.sqrt(diag[0]*diag[1]));normal[0,1]=normal[1,0]=rho
    ne=np.linalg.eigvalsh(normal);rank=int((ne>p['normalized_rank_cut']).sum())
    interior=p['fraction_boundary_tolerance']<f<1-p['fraction_boundary_tolerance']
    regular=bool(rank==2 and interior)
    fixed_sigma=float(1/np.sqrt(I[0,0])) if present[0] and interior else None
    fixed_op=(D[:,0]@W/I[0,0]) if fixed_sigma is not None else None
    free_op=None;free_sigma=None;sigma_alpha=None;unit_error=None;schur_sigma=None
    if regular:
        inverse=np.linalg.inv(I);free_sigma=float(np.sqrt(inverse[0,0]));sigma_alpha=float(np.sqrt(inverse[1,1]))
        free_op=np.linalg.solve(I,D.T@W);unit_error=float(np.max(abs(free_op@D-np.eye(2))))
        schur_sigma=float(1/np.sqrt(I[0,0]-I[0,1]**2/I[1,1]))
        assert free_sigma>=fixed_sigma*(1-1e-10)
    result=dict(f=f,finite_MC=finite,regular=regular,normalized_rank=rank,
        normalized_condition=float(ne[-1]/ne[0]) if rank==2 else None,
        information_correlation=rho,parameter_correlation=(-rho) if regular else None,
        sigma_f_fixed=fixed_sigma,sigma_f_free=free_sigma,sigma_alpha=sigma_alpha,
        sigma_r_over_r_fixed=(fixed_sigma/(f*(1-f))) if fixed_sigma is not None else None,
        sigma_r_over_r_free=(free_sigma/(f*(1-f))) if free_sigma is not None else None,
        sigma_f_cost_ratio=free_sigma/fixed_sigma if regular else None,
        Schur_sigma_f=schur_sigma,unit_operator_error=unit_error,
        C_sum=float(C.sum()),high_mean_log_E_over400=mean,
        covariance_rank=int(positive.sum()),fisher=I.tolist(),normalized_fisher=normal.tolist())
    return result,D,W,fixed_op,free_op


def response_vectors(dec,f):
    weighted=dec['vectors']*np.array([f,1-f])[:,None,None]
    return np.concatenate([weighted,weighted.sum(axis=0,keepdims=True)],axis=0)


def project_response(vectors,D,W,fixed_op,free_op):
    """Returns absolute f/alpha shifts and full signed residuals, no clipping."""
    fixed=vectors@fixed_op if fixed_op is not None else np.full(vectors.shape[:-1],np.nan)
    rf=vectors-fixed[...,None]*D[:,0]
    free=vectors@free_op.T if free_op is not None else np.full(vectors.shape[:-1]+(2,),np.nan)
    ru=vectors-np.einsum('...j,zj->...z',free,D)
    def norm(residual):
        square=np.einsum('...z,zy,...y->...',residual,W,residual)
        return .5*abs(residual).sum(axis=-1),np.sqrt(np.maximum(square,0))
    ff,fw=norm(rf);uf,uw=norm(ru)
    return dict(fixed_delta_f=fixed,free_delta_f=free[...,0],free_delta_alpha=free[...,1],
        fixed_half_L1=ff,free_half_L1=uf,fixed_weighted_norm=fw,free_weighted_norm=uw,
        fixed_residual=rf,free_residual=ru)


def grouped_moments(d,p,role):
    groups,gid,layer,counts=group_counts(d,p,role);take=d['role']==role;high=~d['low'][take]
    u=np.log(d['truth_E_GeV'][take]/p['energy_scale_GeV']);K=counts['M_mu'].shape[2]
    first={}
    for name in REPRESENTATIONS:
        B=p['category_counts'][name];flat=(gid[high]*K+layer[high])*B+d[name][take][high]
        first[name]=np.bincount(flat,weights=u[high],minlength=len(groups)*K*B).reshape(len(groups),K,B)
    return groups,counts,first
