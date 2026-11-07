"""Constrained edge GLS with correlated noise and simultaneous censoring bounds.

This is a constrained measurement model, not an exact multivariate truncated
Gaussian likelihood. Profile intervals require the held-source coverage check.
No arrival time is exposed; the discrete translation is an internal nuisance.
"""
import numpy as np
from scipy.optimize import LinearConstraint, minimize
from scipy.stats import norm

MV_PER_ADC=2/16.384
PC=2
SHIFTS=(-2,-1,0,1,2)
DELTA95=3.841458820694124


def templates(waves, window, baseline_samples=75):
    """Train-only, real unsaturated controls. Input is already source/role held."""
    waves=np.asarray(waves,float)
    assert waves.ndim==2 and waves.shape[1]==600 and len(waves)>=8
    low,high=window
    noise=waves[:,:baseline_samples]-waves[:,:baseline_samples].mean(1)[:,None]
    sigma=float(np.sqrt(np.mean(noise**2)))
    rho=float(np.sum(noise[:,1:]*noise[:,:-1])/np.sum(noise[:,:-1]**2))
    assert sigma>0 and abs(rho)<.99, (sigma,rho)
    signal=waves[:,:baseline_samples].mean(1)[:,None]-waves
    peaks=np.argmax(signal[:,low:high],axis=1)+low
    centre=int(np.rint(np.median(peaks)))
    aligned=[]
    grid=np.arange(low,high)
    for wave,peak in zip(signal,peaks):
        value=np.interp(grid+(peak-centre),np.arange(600),wave)
        amplitude=wave[peak]
        if amplitude>10*sigma:
            aligned.append(value/amplitude)
    assert len(aligned)>=8
    aligned=np.asarray(aligned)
    mean=np.mean(aligned,axis=0)
    _,singular,components=np.linalg.svd(aligned-mean,full_matrices=False)
    shape=(components[:PC].T*singular[:PC]/np.sqrt(len(aligned)-1))
    rho_power=rho**np.abs(np.arange(baseline_samples)[:,None]-np.arange(baseline_samples))
    baseline_sigma=sigma*np.sqrt(rho_power.sum())/baseline_samples
    return dict(mean=mean,pc=shape,sigma=sigma,rho=rho,baseline_sigma=baseline_sigma,
                baseline_samples=baseline_samples,window=[low,high],centre=centre,controls=len(aligned))


def whiten(matrix, value, indices, sigma, rho):
    """Exact stationary AR(1) marginal precision for irregular observed samples."""
    a=matrix.copy();b=value.copy()
    if len(indices)>1:
        correlation=rho**np.diff(indices)
        scale=sigma*np.sqrt(1-correlation**2)
        a[1:]=(matrix[1:]-correlation[:,None]*matrix[:-1])/scale[:,None]
        b[1:]=(value[1:]-correlation*value[:-1])/scale
    a[0]/=sigma;b[0]/=sigma
    return a,b


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
        a,b=whiten(matrix[observed],signal[observed],observed,template['sigma'],template['rho'])
        prior=np.zeros(PC+2);prior[-1]=1/template['baseline_sigma']
        a=np.vstack([a,prior]);b=np.r_[b,0]
        h=a.T@a;g=a.T@b
        normalization=max(float(np.max(np.diag(h))),1.)
        # Parameters remain in ADC units, with data-derived shape fluctuations
        # bounded to three training SD relative to the fitted amplitude.
        constraints=[np.array([1.,0,0,0])];lower=[0.]
        for i in range(1,PC+1):
            v=np.zeros(PC+2);v[0]=3;v[i]=1;constraints.append(v);lower.append(0.)
            v=v.copy();v[i]=-1;constraints.append(v);lower.append(0.)
        if clipped.any():
            constraints.extend(matrix[clipped]);lower.extend(np.full(clipped.sum(),level-k*template['sigma']))
        cm=np.asarray(constraints);lb=np.asarray(lower)
        linear=LinearConstraint(cm,lb,np.inf)
        try:
            start=np.linalg.solve(h,g)
        except np.linalg.LinAlgError:
            continue
        start[0]=max(start[0],1.,float(signal.max()))
        start[1:PC+1]=np.clip(start[1:PC+1],-3*start[0],3*start[0])
        objective=lambda beta: float((beta@h@beta-2*g@beta)/normalization)
        gradient=lambda beta: 2*(h@beta-g)/normalization
        fitted=minimize(objective,start,jac=gradient,constraints=[linear],method='SLSQP',options={'maxiter':100,'ftol':1e-10})
        if not fitted.success or np.min(cm@fitted.x-lb)<-1e-3:
            continue
        chi2=float(np.sum((a@fitted.x-b)**2))
        # Preserve every observed sample; fill only the hidden ADC top.
        charge=lambda beta,matrix=matrix: float(raw+scale*np.maximum(matrix[clipped]@beta-level,0).sum())
        all_fits.append(dict(chi2=chi2,beta=fitted.x,matrix=matrix,a=a,b=b,linear=linear,charge=charge))
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
        result.update(lower95_pC=min(v[0] for v in bounds)-1.96*raw_sigma,
                      upper95_pC=max(v[1] for v in bounds)+1.96*raw_sigma,
                      available=True,profile_bounded=True,profile_status='bounded_nominal_profile')
    else:
        result['Q_pC']=np.nan
        result['profile_status']='unbounded_or_profile_failed'
    return result
