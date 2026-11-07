"""Measured lineage/flow diagnostics at matched low-muon momentum, after fixed risks."""
import numpy as np
from stage131_common import OUT,CACHE,ART,load,table,protocol

def main():
    d=load(CACHE/'matched_input.npz');p=protocol();pred=load(ART/'energy_predictions.npz');rows=[]
    for role in [1,2,3]:
        base=d['role']==role;E=d['truth_E_GeV'];pz=d['pz'];err=pred['direct_cal']-np.log(E)
        groups=dict(lowE_lowpz=(E>=50)&(E<100)&(pz<100),highE_lowpz=(E>=200)&(pz<100),
            transitionE=(E>=100)&(E<200),highE=E>=1000,
            lowE_f0_positive_tail=(E>=50)&(E<100)&(np.expm1(err)>.5),lowE_f0_not_positive_tail=(E>=50)&(E<100)&(np.expm1(err)<=.5))
        for name,group in groups.items():
            use=base&group;w=d['weight'][use]
            if not use.any():continue
            for j in range(10):
                f=d['lineage'][use,j];finite=np.isfinite(f);total=np.expm1(d['total'][use,j]);nonmu=total*(1-f)
                rows.append(dict(role=role,group=name,window='all' if j<5 else 'prompt0_1000ns',detector=p['detectors'][j%5],N=int(use.sum()),ESS=float(w.sum()**2/(w@w)),available_N=int(finite.sum()),weighted_mu_fraction=float(np.average(f[finite],weights=w[finite])) if finite.any() else None,all_mu_N=int((f==1).sum()),nonmu_activity_N=int((f<1).sum()),weighted_nonmu_deposit_GeV=float(np.average(nonmu[finite],weights=w[finite])) if finite.any() else None,scope='descriptive conditional association,not causal energy-error explanation'))
            flow=np.expm1(d['flow'][use,0]);finite=np.isfinite(flow)
            rows.append(dict(role=role,group=name,window='first_exit',detector='target_envelope',N=int(use.sum()),ESS=float(w.sum()**2/(w@w)),available_N=int(finite.sum()),nonmu_activity_N=int((flow>0).sum()),weighted_nonmu_exit_KE_GeV=float(np.average(flow[finite],weights=w[finite])) if finite.any() else None,scope='non-neutrino nonmu transportKE,including neutralhadrons; not detector-visible energy or H; stackkilled neutrino flow unmeasured'))
    table('mechanism_diagnostics.tsv',rows)

if __name__=='__main__':main()
