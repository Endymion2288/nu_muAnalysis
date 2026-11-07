"""Frozen pointwise coverage experiments, not physical-systematic calibration."""
import concurrent.futures
import csv
import json
import resource
import time
from pathlib import Path
import numpy as np
from scipy.optimize import brentq,minimize,LinearConstraint,Bounds
from stage139_likelihood import fit,loglike

OUT=Path('workbook/stage139_energy_ml');CACHE=Path('ntuples/energy_ml_stage139')
CRITICAL=3.841458820694124

def solve(data,mc,fraction,psi=None):
    # Numerical starts solve the same frozen likelihood; no statistical prior,
    # model variant, or feature selection is introduced by this check.
    fits=[fit(data,mc,f,psi=psi,max_iterations=100000)
          for f in [fraction,np.full(7,1/7)]]
    assert all(r['converged'] for r in fits),[r['iterations'] for r in fits]
    best=max(fits,key=lambda r:r['loglike'])
    best['start_LL_difference']=abs(fits[0]['loglike']-fits[1]['loglike'])
    best['max_iterations']=max(r['iterations'] for r in fits)
    return best

def independent(data,mc,fraction,psi,em):
    k=mc.shape[1];n=7+7*k;scale=float(data.sum()+mc.sum())
    a=np.zeros((9,n));a[0,:7]=1
    for j in range(7):a[j+1,7+j*k:7+(j+1)*k]=1
    a[-1,:2]=1;rhs=np.r_[np.ones(8),psi]
    lower=np.zeros(n);lower[7:][mc.ravel()>0]=1e-14
    def fun(x):return -loglike(data,mc,x[:7],x[7:].reshape(7,k))/scale
    def jac(x):
        f=x[:7];q=x[7:].reshape(7,k);mix=f@q
        rat=np.divide(data,mix,out=np.zeros_like(data),where=mix>0)
        aux=np.divide(mc,q,out=np.zeros_like(q),where=q>0)
        return -np.r_[q@rat,(aux+f[:,None]*rat).ravel()]/scale
    start=np.r_[em['fraction'],em['response'].ravel()]
    result=minimize(fun,start,jac=jac,method='SLSQP',bounds=Bounds(lower,np.ones(n)),
        constraints=[LinearConstraint(a,rhs,rhs)],options=dict(ftol=1e-12,maxiter=2000))
    delta=float(-result.fun*scale-em['loglike'])
    assert result.success and abs(delta)<1e-3,(result.message,delta)
    return dict(success=True,loglike_delta_SLSQP_minus_EM=delta,iterations=int(result.nit))

def wilson(covered,n):
    z=1.959963984540054;p=covered/n;den=1+z*z/n
    half=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    center=(p+z*z/(2*n))/den
    return float(center-half),float(center+half)

def worker(spec):
    name,scenario=spec;tick=time.perf_counter();cpu=time.process_time()
    with np.load(CACHE/'template_counts.npz') as source:
        fraction=source['fraction'];mc=source[name+'_MC_counts']
    n=mc.sum(1);q=mc/n[:,None];psi=float(fraction[:2].sum())
    if scenario=='unseen_cell_stress':
        # This artificial categorical sensitivity scenario has no claim to be
        # a measured detector/physics variation or a calibrated MC confidence set.
        for j in range(7):
            zero=q[j]==0
            if zero.any():
                mass=min(.05,3./n[j]);q[j]*=1-mass;q[j,zero]=mass/zero.sum()
    asimov_mc=n[:,None]*q;asimov_data=1000*(fraction@q)
    free=solve(asimov_data,asimov_mc,fraction)
    exact=loglike(asimov_data,asimov_mc,fraction,q)
    assert abs(free['loglike']-exact)<1e-3,(name,scenario,'Asimov',free['loglike']-exact)
    curves=[];validation=[]
    def profile(value):
        result=solve(asimov_data,asimov_mc,fraction,psi=value)
        stat=max(0.,2*(free['loglike']-result['loglike']))
        return stat,result
    for value in np.linspace(max(0.,psi-.06),min(1.,psi+.06),21):
        stat,result=profile(float(value));curves.append(dict(psi=float(value),LR=stat))
    for value in [max(.001,psi-.02),psi,min(.999,psi+.02)]:
        stat,result=profile(value)
        validation.append(dict(psi=value,LR=stat,**independent(asimov_data,asimov_mc,fraction,value,result)))
    low=brentq(lambda v:profile(v)[0]-CRITICAL,0,psi,xtol=1e-7) if profile(0)[0]>CRITICAL else 0.
    high=brentq(lambda v:profile(v)[0]-CRITICAL,psi,1,xtol=1e-7) if profile(1)[0]>CRITICAL else 1.
    rng=np.random.default_rng(202611071390+(0 if scenario=='nominal_empirical' else 100))
    toys=[]
    for toy in range(500):
        aux=np.array([rng.multinomial(int(count),r) for count,r in zip(n,q)])
        observed=rng.multinomial(1000,fraction@q)
        a=solve(observed,aux,fraction)
        b=solve(observed,aux,fraction,psi=psi)
        assert a['loglike']>=b['loglike']-1e-4,(name,scenario,toy,a['loglike'],b['loglike'])
        stat=max(0.,2*(a['loglike']-b['loglike']))
        toys.append(dict(toy=toy,LR=stat,covered=stat<=CRITICAL,
            psi_hat=float(a['fraction'][:2].sum()),
            free_iterations=a['max_iterations'],fixed_iterations=b['max_iterations'],
            max_start_LL_difference=max(a['start_LL_difference'],b['start_LL_difference'])))
    covered=sum(r['covered'] for r in toys);lo,hi=wilson(covered,len(toys))
    result=dict(model=name,scenario=scenario,true_psi=psi,toys=len(toys),covered=covered,
        pointwise_coverage=covered/len(toys),coverage_Wilson_low95=lo,coverage_Wilson_high95=hi,
        Asimov_low95_pp=100*low,Asimov_high95_pp=100*high,Asimov_width95_pp=100*(high-low),
        fitted_psi_bias_pp=100*(np.mean([r['psi_hat'] for r in toys])-psi),
        fitted_psi_RMS_pp=100*np.sqrt(np.mean([(r['psi_hat']-psi)**2 for r in toys])),
        max_start_LL_difference=max(r['max_start_LL_difference'] for r in toys),
        max_EM_iterations=max(max(r['free_iterations'],r['fixed_iterations']) for r in toys),
        CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,
        numerical_validation=validation,profile=curves)
    with (OUT/f'{name}_{scenario}_toys.tsv').open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(toys[0]),delimiter='\t',lineterminator='\n');writer.writeheader();writer.writerows(toys)
    (OUT/f'{name}_{scenario}.json').write_text(json.dumps(result,indent=2)+'\n')
    print('COVERAGE',name,scenario,covered,'/500',flush=True)
    return result

def main():
    tick=time.perf_counter()
    specs=[(name,scenario) for name in ['traditional','direct62','joint_direct62_pz0']
           for scenario in ['nominal_empirical','unseen_cell_stress']]
    with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:results=list(pool.map(worker,specs))
    rows=[{k:v for k,v in r.items() if k not in ['numerical_validation','profile']} for r in results]
    with (OUT/'coverage_summary.tsv').open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n');writer.writeheader();writer.writerows(rows)
    summary=dict(passed_numerical_checks=True,experiments=6,toys=3000,
        independent_SLSQP_checks=sum(len(r['numerical_validation']) for r in results),
        CPU_s=sum(r['CPU_s'] for r in results),wall_s=time.perf_counter()-tick,
        scope='pointwise parametric working-model LR coverage only; no actualdata/systematic/full-family/selection certification; stress scenarios differ by representation and cannot be interpreted as common physical shifts',
        no_model_training_or_forward=True,reserved_forward=0,GPU=0)
    (OUT/'coverage_scope.json').write_text(json.dumps(summary,indent=2)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(7,4.5),layout='constrained')
    for r in results:
        if r['scenario']=='nominal_empirical':ax.plot([100*x['psi'] for x in r['profile']],[x['LR'] for x in r['profile']],label=r['model'])
    ax.axhline(CRITICAL,color='gray',ls='--');ax.set(xlabel='Selected E<200 GeV fraction (%)',ylabel='Profile likelihood ratio',ylim=(0,12),title='Finite MC auxiliary likelihood; empirical working model')
    ax.legend();ax.grid(alpha=.2);fig.savefig(OUT/'profile_likelihood.png',dpi=160);plt.close(fig)

if __name__=='__main__':main()
