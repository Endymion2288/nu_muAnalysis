"""Confirmation planning with explicit sparse and zero-discordance limitations."""
import json

import numpy as np
from scipy.stats import beta

from stage119_curve_common import OUT,load,masks,table


def main():
    d=load('ntuples/energy_ml_stage119/curve_input.npz');pred=load('ml/artifacts/stage119/augmented_predictions.npz');ref=load('ml/artifacts/stage119/reference_predictions.npz')
    ix=np.flatnonzero((d['role']==2)&(d['kind']=='expansion'));sd={k:v[ix] for k,v in d.items()};rows=[]
    for layer,z in masks(sd).items():
        use=ix[z]
        if not len(use):continue
        _,gid,count=np.unique(d['incoming'][use],axis=0,return_inverse=True,return_counts=True);n=len(count);w=1/count[gid]
        y=np.log(d['truth_E_GeV'][use]);a=pred['new_cal'][use]-y
        for reference in ['direct_cal','traditional']:
            b=(ref['new'][use] if reference=='direct_cal' else np.log(d['pz'][use]/.8))-y
            family=np.bincount(gid,weights=w*(a*a-b*b));variance=float(np.var(family,ddof=1)) if n>1 else None
            meanref=float(np.average(b*b,weights=w));delta=.0975*meanref
            needed=int(np.ceil((1.959963984540054+.8416212335729143)**2*variance/delta**2)) if variance is not None and delta>0 and variance>0 else None
            row=dict(stratum=layer,reference=reference,development_rows=len(use),development_incoming=n,
                paired_lossdiff_variance=variance,reference_MSE=meanref,target_RMSE_ratio=.95,
                normal_80pct_power_incoming=needed,
                planning_scope='5% improvement vs chosen reference, two-sided95% normal approximation at zero mean loss difference; not original joint-gate power or certified new-blind size',
                sparse_warning='pilot <30 incoming; variance unstable' if n<30 else 'conditional source/proxy variance, no refit/system/research selection coverage')
            for sign,fa,fb in [('total',abs(np.expm1(a))>.5,abs(np.expm1(b))>.5),('positive',np.expm1(a)>.5,np.expm1(b)>.5),('negative',np.expm1(a)<-.5,np.expm1(b)<-.5)]:
                diff=fa.astype(float)-fb.astype(float);family=np.bincount(gid,weights=w*diff)
                v=float(np.var(family,ddof=1)) if n>1 else None
                discordant=np.bincount(gid,weights=(fa!=fb).astype(float))>0;k=int(discordant.sum())
                upper=float(beta.ppf(.95,k+1,n-k)) if k<n else 1.
                row.update({sign+'_discordant_families':k,sign+'_discordance_upper95':upper,
                    sign+'_empirical_1pp_halfwidth_incoming':int(np.ceil(1.959963984540054**2*v/.01**2)) if v is not None and v>0 else None,
                    sign+'_upper_variance_1pp_planning_incoming':int(np.ceil(1.959963984540054**2*upper/.01**2))})
            rows.append(row)
    table('confirmation_plan.tsv',rows)
    (OUT/'confirmation_decision.json').write_text(json.dumps(dict(open_reserved=False,
        reasons=['augmented candidate fails original gates on developed target','lowest new development only14 incoming, reserve6','complete GENIE-family and historical parent exposure certification absent'],
        correction='confirmation_power.tsv is an initial empirical variance diagnostic; zero-variance tail N=0 is not a valid sample-size claim. confirmation_plan.tsv replaces it with unavailable empirical precision and a discordance-upper-bound planning scale.',
        conservative_precision='paired-family tail difference variance <= probability(any discordant response view); exact binomial95% upper on sampled family disagreement, then normal halfwidth1pp planning; conditional proxies, not a simultaneous guarantee',
        no_new_independent_confirmation_claim=True),indent=2)+'\n')


if __name__=='__main__':main()
