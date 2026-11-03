#!/usr/bin/env python3
"""Small arithmetic/gradient/NaN and resource pilot, never a scientific candidate."""
import json
import numpy as np
import xgboost as xgb
from audited_features import clean
from energy_reweight import *


def main():
    start=begin();p=json.loads((OUT/'protocol.json').read_text());d=arrays(CACHE/'input.npz');tr=d['role']=='train'
    qa=[]
    for name,alpha in ARMS.items():
        w,b,c=weights(d['truth_E_GeV'][tr],alpha);s=np.bincount(b,weights=w,minlength=9)
        assert abs(w.mean()-1)<1e-12
        if name=='U':np.testing.assert_array_equal(w,np.ones(len(w)))
        if name=='F':np.testing.assert_allclose(s[1:8],np.full(7,len(w)/7),rtol=1e-12)
        if name=='S':np.testing.assert_allclose(s[1:8]/np.sqrt(c[1:8]),np.full(7,s[1]/np.sqrt(c[1])),rtol=1e-12)
        qa.append(dict(arm=name,ESS=float(w.sum()**2/(w@w)),weight_min=float(w.min()),weight_max=float(w.max())))
    np.testing.assert_allclose(qa[2]['ESS'],8621.671252,rtol=1e-9)
    w=np.array([.5,1.,1.5]);y=np.array([4.,5.,6.]);z=np.array([4.5,4.9,5.8]);eps=1e-5
    def loss(v):return .5*np.sum(w*(v-y)**2)
    numerical=np.array([(loss(z+np.eye(3)[i]*eps)-loss(z-np.eye(3)[i]*eps))/(2*eps) for i in range(3)])
    gradient_diff=float(np.max(abs(numerical-w*(z-y))));assert gradient_diff<1e-9
    np.testing.assert_array_equal(clean([-999,-1,0],dict(domain='signed')),[-999,-1,0])
    # Tiny 512-row / two-tree resource and deployment pilot, deleted immediately.
    idx=np.r_[np.flatnonzero(tr)[:500],np.flatnonzero(tr&d['missing'])[:12]]
    xx=d['x'][idx];yy=np.log(d['truth_E_GeV'][idx]);ww=weights(d['truth_E_GeV'][idx],.5)[0]
    dm=xgb.DMatrix(xx,label=yy,weight=ww,feature_names=p['features'],nthread=1)
    fitstart=begin();params=dict(p['xgboost'],seed=p['seed'],base_score=float(yy.mean()),boost_from_average=0)
    model=xgb.train(params,dm,num_boost_round=2)
    dd=xgb.DMatrix(xx,feature_names=p['features'],nthread=1)
    np.testing.assert_array_equal(model.predict(dm),model.predict(dd));assert np.isfinite(model.predict(dd)).all()
    # Native square-error DMatrix weights match analytic gradients for one step.
    custom=xgb.Booster(params=params,cache=[dm]);pred=custom.predict(dm,output_margin=True)
    custom.boost(dm,0,(dm.get_weight()*(pred-dm.get_label())).astype('float32'),dm.get_weight())
    builtin=xgb.train(params,dm,num_boost_round=1)
    np.testing.assert_array_equal(custom.predict(dd),builtin.predict(dd))
    pilot_resources=resources(fitstart)
    save(OUT/'pilot.json',dict(passed=True,policies=qa,gradient_max_abs_diff=gradient_diff,
        weight_mean_one=True,F_bin_mass_equal=True,S_bin_mass_sqrtN=True,analytic_one_step_exact=True,
        NaN_present=int(np.isnan(xx).sum()),deployment_only_X=True,tiny_resource_N=len(idx),pilot_trees=2,
        pilot_is_candidate=False,retained_pilot_models=0,pilot_resources=pilot_resources,
        xgboost_version=xgb.__version__,budget_confirmed='4 jobs x 1CPU/3000MB; CPU total3600s; wall/job1800s; worker1750s/callbackCPU850s',**resources(start)))
    print((OUT/'pilot.json').read_text())


if __name__=='__main__':main()
