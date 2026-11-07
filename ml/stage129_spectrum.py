"""Selected-population spectrum closure and statistical precision, not full unfolding."""
import json
import time

import numpy as np
from scipy.optimize import minimize

from stage129_energy import ROOT, OUT, ART, load, table
from stage119_curve_common import weights

TRUTH=np.array([50,100,200,400,800,1600,3200,np.inf])
RECO=np.array([0,50,100,200,400,800,1600,3200,6400,np.inf])


def estimate(response, observed):
    start=np.full(response.shape[0],1/response.shape[0])
    def fun(f):
        p=f@response
        return -float(observed@np.log(np.maximum(p,1e-300)))
    def jac(f):return -response@(observed/np.maximum(f@response,1e-300))
    result=minimize(fun,start,jac=jac,bounds=[(0,1)]*len(start),constraints=[dict(type='eq',fun=lambda f:f.sum()-1,jac=lambda f:np.ones_like(f))],method='SLSQP',options=dict(ftol=1e-12,maxiter=1000))
    assert result.success, result.message
    return result.x


def main():
    tick=time.perf_counter();d=load(ROOT/'ntuples/energy_ml_stage119/old_input.npz');energy=d['truth_E_GeV'];rows=[];bins=[]
    policies={}
    for experiment,arm in [('saturation','Q'),('timing','T'),('trackmaterial','G'),('depth','Z')]:
        a=load(ART/f'{experiment}_predictions.npz');policies[experiment+'_'+arm]=a[arm]
    policies['direct62']=a['direct_cal'];policies['traditional']=a['traditional']
    cal=d['role']==2;test=d['role']==3
    truebin=np.searchsorted(TRUTH,energy,side='right')-1
    # Beyond the last finite edge is an explicit overflow truth bin.
    wcal=weights(d['incoming'][cal]);wtest=weights(d['incoming'][test]);truth=np.bincount(truebin[test],weights=wtest,minlength=7);truth/=truth.sum()
    for name,pred in policies.items():
        reco=np.searchsorted(RECO,np.exp(pred),side='right')-1
        matrix=np.zeros((7,9));np.add.at(matrix,(truebin[cal],reco[cal]),wcal)
        assert (matrix.sum(1)>0).all()
        response=matrix/matrix.sum(1)[:,None]
        empirical=np.bincount(reco[test],weights=wtest,minlength=9);empirical/=empirical.sum()
        fitted=estimate(response,empirical)
        q=truth@response;keep=q>0
        # Six free mixture coordinates on the exact unit simplex.
        deriv=(response[:6]-response[6]).T
        information=1000*(deriv[keep].T/q[keep])@deriv[keep]
        eigen=np.linalg.eigvalsh(information);rank=int((eigen>eigen.max()*1e-10).sum())
        regular=rank==6
        sig=None;siglow=None;condition=None
        if regular:
            cov7=np.linalg.inv(information);transform=np.vstack([np.eye(6),-np.ones(6)]);cov=transform@cov7@transform.T;sig=np.sqrt(np.diag(cov));contrast=np.r_[1.,1.,np.zeros(5)];siglow=float(np.sqrt(contrast@cov@contrast));condition=float(eigen[-1]/eigen[0])
        rows.append(dict(model=name,N_selected=1000,cal_N=int(cal.sum()),test_N=int(test.sum()),fisher_rank=rank,regular=regular,condition=condition,truth_low_fraction=float(truth[:2].sum()),fitted_low_fraction=float(fitted[:2].sum()),closure_low_fraction_shift_pp=float(100*(fitted[:2].sum()-truth[:2].sum())),knownresponse_sigma_low_fraction_pp=None if siglow is None else 100*siglow,scope='selected MC only, role2 response / exposed role3 closure; knownresponse conditional statistical precision, not actual data or full uncertainty'))
        for i in range(7):bins.append(dict(model=name,true_low_GeV=TRUTH[i],true_high_GeV=TRUTH[i+1],cal_effective_count=float(matrix[i].sum()),truth_fraction=truth[i],fitted_fraction=fitted[i],knownresponse_sigma_fraction=None if sig is None else sig[i]))
    table('spectrum_precision.tsv',rows);table('spectrum_bins.tsv',bins)
    (OUT/'spectrum_scope.json').write_text(json.dumps(dict(wall_s=time.perf_counter()-tick,actual_data_fit=False,selection='unchanged original selected MC; no parent efficiency inferred',N_selected=1000,missing_for_full_physics=['certified independent generator/response families','matched true-energy acceptance including rejected parents','real data exposure/GRL and background templates under identical selection','calibrated PMT/ADC response and gain/rail/timing nuisance constraints','GENIE interaction/FSI, flux and material uncertainties with correlations','finite response MC and refit/selection propagation'],repository_evidence='existing spectrum_hardness.py/local_information and joint_response.py conditional multinomial templates; this job does not assert those cover the missing detector/physics inputs',scope='quantifies feasible conditional spectrum information; original full physics precision target remains unmet'),indent=2)+'\n')


if __name__=='__main__':main()
