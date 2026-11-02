#!/usr/bin/env python3
"""Freeze a transparent numerical amendment after the first KKT failure."""
from datetime import datetime,timezone
import json
import numpy as np

from joint_response import OUT,ART,TemplateLikelihood,histogram,begin,resources,save
from report_joint_response import independent_profile


def main():
    start=begin();p=json.loads((OUT/'protocol.json').read_text())
    assert not (OUT/'protocol_v2.json').exists()
    p.update(solver='dual_allocation_root',dual_allocation_xtol=1e-10,formal_job_limit=2,
        numerical_amendment_utc=datetime.now(timezone.utc).isoformat(),
        amendment_reason='job9661816 stopped at fixed f=.8125 KKT3.1284307e-6>1e-6; no complete physics outputs; replace nuisance solver only',
        solver_v2='Exact KKT allocation quadratic per category, monotone scalar root of total assigned data; no floors/pseudocounts; unchanged objective, outer grid, intervals, bins, pressures, acceptance and total CPU budget',
        superseded_numerics='EM/SLSQP options retained only as historical metadata; not used by the v2 finite-MC interior solver',
        job_budget_note='second and last job, within roadmap <=2 tasks; combined RemoteCPU<=3600s; no automated retry')
    rng=np.random.default_rng(63);tests=[]
    cases=[]
    for j in range(6):
        mc=rng.poisson(np.tile(np.r_[np.arange(1,9),np.arange(8,0,-1)],(2,1))).astype(float);mc[j%2,j]=0
        data=rng.multinomial(1000,rng.dirichlet(np.ones(16))).astype(float);cases.append((f'random{j}',mc,data))
    mc=np.array([[0.,30.,70.],[80.,20.,0.]])
    cases.append(('zero_component_cells',mc,1000*(.1*mc[0]/100+.9*mc[1]/100)))
    cases.append(('data_only_cell',np.array([[0.,30.,70.],[0.,80.,20.]]),np.array([200.,400.,400.])))
    mc=np.array([[320.,160.,80.,40.],[30.,100.,250.,820.]])
    cases.append(('interior',mc,1000*(.12*mc[0]/600+.88*mc[1]/1200)))
    for label,mc,data in cases:
        like=TemplateLikelihood(mc,data,p,True)
        for f in [1e-5,.1,.8125,.99999]:
            value=like.evaluate(f)[0];independent=independent_profile(mc,data,f);error=abs(value-independent)
            assert error<2e-6,(label,f,error)
            tests.append(dict(case=label,f=f,independent_NLL_error=error,KKT_max=like.max_kkt))
        fit=like.fit(.1)
        if label=='zero_component_cells':assert abs(fit['f_hat']-.1)<1e-6
        if label=='interior':assert abs(fit['f_hat']-.12)<1e-6
    # Reproduce only the failed fixed-f arithmetic, not a new method/pressure.
    with np.load(ART/'observables.npz') as z:d={k:z[k] for k in z.files}
    tr=d['role']=='train';take=d['role']=='cal';low=d['low'][take];w=np.ones(take.sum())
    w[(~low)&(d['pz'][take]<100)&(d['y_lepton'][take]>=.8)]*=.75
    for c in [low,~low]:w[c]*=c.sum()/w[c].sum()
    reproduced=[]
    for name in p['selected_models']:
        mc=histogram(d[name][tr],d['low'][tr],np.ones(tr.sum()),p['category_counts'][name])
        data=histogram(d[name][take],low,w,p['category_counts'][name]).sum(axis=0)/w.sum()*1000
        like=TemplateLikelihood(mc,data,p,True);value=like.evaluate(.8125)[0]
        error=abs(value-independent_profile(mc,data,.8125));assert error<2e-6
        reproduced.append(dict(representation=name,f=.8125,KKT=like.max_kkt,independent_NLL_error=error))
    save(OUT/'numerical_amendment_QA.json',dict(synthetic_fixed_f_checks=tests,reproduced_fixed_f=reproduced,
        successful_synthetic_profiles=len(cases),first_failed_job='9661816',first_failed_remote_CPU_s=3,
        prior_failed_synthetic_prepare_resources='not measured',**resources(start)))
    save(OUT/'protocol_v2.json',p)
    print(json.dumps(dict(max_NLL_error=max(t['independent_NLL_error'] for t in tests),reproduced=reproduced,resources=resources(start)),indent=2))


if __name__=='__main__':main()
