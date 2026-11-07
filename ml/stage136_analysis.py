"""Selected-spectrum precision with measured clustered response-MC covariance.

Physical nuisance constraints, acceptance and backgrounds are not fabricated.
The linear Gaussian auxiliary calculation is not a coverage certification.
"""
import json
import resource
import time
import numpy as np
from stage119_curve_common import weights
from stage133_common import load
from stage136_common import OUT, CACHE, table

TRUTH=np.array([50,100,200,400,800,1600,3200,np.inf])
RECO=np.array([0,50,100,200,400,800,1600,3200,6400,np.inf])
PZ=np.array([50,100,200,400,np.inf])

def precision(response, fraction, mc_cov):
    q=fraction@response
    keep=q>0
    r=response[:,keep]
    q=q[keep]
    # One omitted observable probability coordinate removes the simplex zero mode.
    derivative=(r[:6]-r[6]).T[:-1]
    vdata=(np.diag(q)-np.outer(q,q))[:-1,:-1]/1000
    vtemplate=sum(fraction[j]**2*mc_cov[j][np.ix_(keep,keep)]
                  for j in range(7))[:-1,:-1]
    iknown=derivative.T@np.linalg.solve(vdata,derivative)
    ieff=derivative.T@np.linalg.solve(vdata+vtemplate,derivative)
    # Independent explicit auxiliary-template Schur complement (Woodbury).
    eig,vec=np.linalg.eigh(vtemplate)
    use=eig>max(float(eig.max())*1e-12,1e-20)
    loading=vec[:,use]*np.sqrt(eig[use])
    cross=derivative.T@np.linalg.solve(vdata,loading)
    aux=np.eye(use.sum())+loading.T@np.linalg.solve(vdata,loading)
    schur=iknown-cross@np.linalg.solve(aux,cross.T)
    discrepancy=float(np.max(abs(schur-ieff)))
    assert discrepancy<max(1e-9,float(abs(ieff).max())*1e-10)
    result=dict(observed_categories=int(keep.sum()),
                schur_max_abs_difference=discrepancy)
    contrast=np.r_[1.,1.,np.zeros(4)]
    for name,info in [('known',iknown),('finiteMC',ieff)]:
        values=np.linalg.eigvalsh(info)
        rank=int((values>values.max()*1e-10).sum())
        result[name+'_rank']=rank
        result[name+'_condition']=float(values[-1]/values[0]) if rank==6 else None
        result[name+'_sigma_low_fraction_pp']=float(100*np.sqrt(
            contrast@np.linalg.solve(info,contrast))) if rank==6 else None
    return result,q,vtemplate

def main():
    tick=time.perf_counter();cpu=time.process_time()
    d=load('ntuples/energy_ml_stage119/old_input.npz')
    pred=load('ml/artifacts/stage129/depth_predictions.npz')
    cal=d['role']==2;test=d['role']==3
    truebin=np.searchsorted(TRUTH,d['truth_E_GeV'],side='right')-1
    assert np.all((truebin[cal|test]>=0)&(truebin[cal|test]<7))
    wtest=weights(d['incoming'][test])
    fraction=np.bincount(truebin[test],weights=wtest,minlength=7)
    fraction/=fraction.sum()
    _,gid=np.unique(d['incoming'][cal],axis=0,return_inverse=True)
    count=np.bincount(gid);wcal=1/count[gid]
    family_truth=np.full(len(count),-1,int)
    for j in range(7):
        groups=np.unique(gid[truebin[cal]==j])
        assert np.all(family_truth[groups]==-1), 'One incoming proxy crosses truth bins'
        family_truth[groups]=j
    assert (family_truth>=0).all()
    traditional=np.searchsorted(RECO,np.exp(pred['traditional'][cal]),side='right')-1
    direct=np.searchsorted(RECO,np.exp(pred['direct_cal'][cal]),side='right')-1
    pz=np.searchsorted(PZ,d['pz'][cal],side='right')-1
    assert np.all((pz>=0)&(pz<4))
    maps={'traditional':(traditional,9),'direct62':(direct,9),
          'joint_direct62_pz0':(direct*4+pz,36)}
    rows=[];support=[];saved={};errors=[]
    for name,(category,size) in maps.items():
        assert np.all((category>=0)&(category<size))
        families=np.zeros((len(count),size))
        np.add.at(families,(gid,category),wcal)
        np.testing.assert_allclose(families.sum(1),1,atol=1e-12)
        response=[];cov=[];draws=[]
        for j in range(7):
            c=families[family_truth==j];n=len(c);assert n>1
            r=c.mean(0);center=c-r
            v=center.T@center/(n*(n-1))
            response.append(r);cov.append(v)
            # Same family order and random counts in all three representations.
            rng=np.random.default_rng(20261107136+j)
            multiplicity=rng.multinomial(n,np.full(n,1/n),size=500)
            draws.append(multiplicity@c/n)
            support.append(dict(model=name,true_bin=j,cal_rows=int((truebin[cal]==j).sum()),
                cal_incoming_proxies=n,empty_response_cells=int((r==0).sum()),
                response_cells=size,minimum_positive_probability=float(r[r>0].min()),
                clustered_covariance_trace=float(np.trace(v))))
        response=np.array(response);cov=np.array(cov)
        result,q,vtemplate=precision(response,fraction,cov)
        bootstrap_q=np.einsum('j,jbm->bm',fraction,np.array(draws))
        analytic=sum(fraction[j]**2*cov[j] for j in range(7))
        empirical=np.cov(bootstrap_q,rowvar=False,ddof=1)
        trace_ratio=float(np.trace(empirical)/np.trace(analytic))
        saved[name+'_response']=response;saved[name+'_mc_cov']=cov
        saved[name+'_bootstrap_q']=bootstrap_q
        rows.append(dict(model=name,N_selected=1000,cal_rows=int(cal.sum()),
            test_rows=int(test.sum()),cal_incoming_proxies=len(count),
            truth_low_fraction=float(fraction[:2].sum()),**result,
            bootstrap_to_analytic_MC_trace_ratio=trace_ratio,
            coverage_certified=False,actual_data=False))
        errors.append(result['schur_max_abs_difference'])
    CACHE.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(CACHE/'response_evidence.npz',truth_fraction=fraction,**saved)
    table('precision.tsv',rows);table('response_support.tsv',support)
    scope=dict(measured_finite_response_MC=True,physical_nuisance_constraints=False,
        actual_data_fit=False,acceptance_or_background_included=False,
        no_model_training_or_forward=True,reserved_forward=0,
        incoming_dtype=str(d['incoming'].dtype),
        validation='independent explicit auxiliary Schur complement vs covariance sum',
        max_schur_abs_difference=max(errors),coverage='unmeasured; local asymptotic,empty cells may be nonregular',
        missing=['matched data exposure/GRL/background/acceptance',
                 'calibrated correlated detector/material/GENIE/FSI/flux nuisance constraints',
                 'certified independent generator families and refit/selection propagation'],
        CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,
        RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,GPU=0)
    (OUT/'scope.json').write_text(json.dumps(scope,indent=2)+'\n')
    print(rows,flush=True)

if __name__=='__main__':
    main()
