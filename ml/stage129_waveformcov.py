"""Feasible correlated GLS including measured residual template covariance.

Fixed three covariance updates per shift. Covariance is a plug-in measurement
approximation, not an exact amplitude-dependent likelihood. Source-held coverage
is mandatory. Original raw observations and strict timing statuses are untouched.
"""
import numpy as np
from scipy.linalg import solve_triangular
from scipy.optimize import LinearConstraint,minimize
from scipy.stats import norm
from stage129_waveform import MV_PER_ADC,PC,SHIFTS,DELTA95,whiten

def recover(adc, template, rail=0):
    adc=np.asarray(adc,float)
    low,high=template['window'];n=high-low
    baseline=float(adc[:template['baseline_samples']].mean())
    signal=baseline-adc[low:high]
    clipped=adc[low:high]<=rail
    scale=.04*MV_PER_ADC
    raw=float(signal.sum()*scale)
    result=dict(raw_W_pC=raw,Q_pC=np.nan,lower95_pC=np.nan,upper95_pC=np.nan,
                available=False,rail_samples=int(clipped.sum()),leading=False,trailing=False,
                chi2_ndof=np.nan,profile_bounded=False,profile_status='not_fitted')
    if clipped.any():
        first,last=np.flatnonzero(clipped)[[0,-1]]
        result['leading']=bool(((signal[:first]>5*template['sigma'])&~clipped[:first]).sum()>=2)
        result['trailing']=bool(((signal[last+1:]>5*template['sigma'])&~clipped[last+1:]).sum()>=2)
        if not (result['leading'] and result['trailing']):
            result['profile_status']='insufficient_two_edges'
            return result
    else:
        result.update(leading=True,trailing=True)
    observed=np.flatnonzero(~clipped)
    if len(observed)<8:
        return result
    # Simultaneous one-sided noise tube is valid without assuming independent
    # censored samples. AR(1) GLS models the observed-edge correlation exactly.
    k=float(norm.ppf(1-.025/max(1,int(clipped.sum()))))
    level=baseline-rail
    all_fits=[]
    for shift in SHIFTS:
        xx=np.arange(n)
        columns=[np.interp(xx-shift,xx,template['mean'],left=0,right=0)]
        columns.extend(np.interp(xx-shift,xx,template['pc'][:,i],left=0,right=0) for i in range(PC))
        matrix=np.column_stack(columns+[np.ones(n)])
        electronic_a,electronic_b=whiten(matrix[observed],signal[observed],observed,template['sigma'],template['rho'])
        start=np.linalg.lstsq(electronic_a,electronic_b,rcond=None)[0]
        start[0]=max(start[0],1.,float(signal.max()))
        shifted=np.arange(n)-shift;inside=(shifted>=0)&(shifted<n);take=np.clip(shifted,0,n-1)
        shape_cov=template['shape_cov'][np.ix_(take,take)]*inside[:,None]*inside[None,:]
        noise_cov=template['sigma']**2*template['rho']**np.abs(np.arange(n)[:,None]-np.arange(n))
        fitted=None
        for iteration in range(3):
            amplitude=max(start[0],1.)
            fullcov=noise_cov+amplitude**2*shape_cov
            factor=np.linalg.cholesky(fullcov[np.ix_(observed,observed)])
            a=solve_triangular(factor,matrix[observed],lower=True,check_finite=False)
            b=solve_triangular(factor,signal[observed],lower=True,check_finite=False)
            prior=np.zeros(PC+2);prior[-1]=1/template['baseline_sigma']
            a=np.vstack([a,prior]);b=np.r_[b,0]
            h=a.T@a;g=a.T@b;normalization=max(float(np.max(np.diag(h))),1.)
            constraints=[np.array([1.,0,0,0])];lower=[0.]
            for i in range(1,PC+1):
                v=np.zeros(PC+2);v[0]=3;v[i]=1;constraints.append(v);lower.append(0.)
                v=v.copy();v[i]=-1;constraints.append(v);lower.append(0.)
            if clipped.any():
                constraints.extend(matrix[clipped]);lower.extend(level-k*np.sqrt(np.diag(fullcov)[clipped]))
            cm=np.asarray(constraints);lb=np.asarray(lower);linear=LinearConstraint(cm,lb,np.inf)
            start[1:PC+1]=np.clip(start[1:PC+1],-3*start[0],3*start[0])
            objective=lambda beta:float((beta@h@beta-2*g@beta)/normalization)
            gradient=lambda beta:2*(h@beta-g)/normalization
            fitted=minimize(objective,start,jac=gradient,constraints=[linear],method='SLSQP',options={'maxiter':100,'ftol':1e-10})
            if not fitted.success or np.min(cm@fitted.x-lb)<-1e-3:break
            start=fitted.x.copy()
        if fitted is None or not fitted.success or np.min(cm@fitted.x-lb)<-1e-3:continue
        chi2=float(np.sum((a@fitted.x-b)**2))
        # Preserve every observed sample; fill only the hidden ADC top.
        charge=lambda beta,matrix=matrix: float(raw+scale*np.maximum(matrix[clipped]@beta-level,0).sum())
        all_fits.append(dict(chi2=chi2,beta=fitted.x,matrix=matrix,a=a,b=b,linear=linear,charge=charge,shape_sigma_pC=scale*amplitude*np.sqrt(max(0,shape_cov[np.ix_(clipped,clipped)].sum()))))
    if not all_fits:
        result['profile_status']='optimization_failed'
        return result
    best=min(all_fits,key=lambda x:x['chi2'])
    result['chi2_ndof']=best['chi2']/max(1,len(observed)-(PC+2))
    # Model mismatch is exposed even when the charge estimate is unavailable.
    if result['chi2_ndof']>10:
        result['profile_status']='template_mismatch'
        return result
    q=best['charge'](best['beta'])
    bounds=[];bounded=True
    for f in all_fits:
        if f['chi2']>best['chi2']+DELTA95:
            continue
        a,b=f['a'],f['b'];limit=best['chi2']+DELTA95
        region={'type':'ineq','fun':lambda beta,a=a,b=b,limit=limit: limit-float(np.sum((a@beta-b)**2)),
                'jac':lambda beta,a=a,b=b: -2*a.T@(a@beta-b)}
        interval=[]
        for sign in [1.,-1.]:
            solved=minimize(lambda beta,sign=sign,f=f:sign*f['charge'](beta),f['beta'],constraints=[f['linear'],region],
                            method='SLSQP',options={'maxiter':100,'ftol':1e-8})
            if not solved.success:
                bounded=False;break
            interval.append(f['charge'](solved.x))
        if not bounded:
            break
        bounds.append(interval)
    result['Q_pC']=q
    if bounded and bounds:
        # Add the measured raw integral/baseline noise uncertainty conservatively;
        # actual source-held coverage, not the profile convention, validates it.
        corr=template['rho']**np.abs(np.arange(n)[:,None]-np.arange(n))
        raw_sigma=scale*np.sqrt(template['sigma']**2*corr.sum()+n*n*template['baseline_sigma']**2)
        raw_sigma+=max(f['shape_sigma_pC'] for f in all_fits if f['chi2']<=best['chi2']+DELTA95)
        result.update(lower95_pC=min(v[0] for v in bounds)-1.96*raw_sigma,
                      upper95_pC=max(v[1] for v in bounds)+1.96*raw_sigma,
                      available=True,profile_bounded=True,profile_status='bounded_nominal_profile')
    else:
        result['Q_pC']=np.nan
        result['profile_status']='unbounded_or_profile_failed'
    return result
