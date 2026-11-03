#!/usr/bin/env python3
"""Small stage74 ratio, BCE, proposal and deployment QA; no scientific candidate."""
import json
import numpy as np
import xgboost as xgb
from audited_features import clean
from group_risk import training_split
from conditional_hypotheses import *


def main():
    start=begin();p=json.loads((OUT/'protocol.json').read_text());d=arrays(CACHE/'input.npz')
    # Piecewise-constant toy densities with known conditional ratios.
    q=np.array([[.8,.2],[.3,.7]]);posterior=np.array([[.9,.1],[.2,.8]])
    logratio=np.log(posterior/q)
    recovered=q*np.exp(logratio)
    np.testing.assert_allclose(recovered,posterior,rtol=1e-14)
    np.testing.assert_allclose(recovered.sum(1),1,rtol=1e-14)
    np.testing.assert_array_equal(np.log(q/q),np.zeros_like(q))
    wrong=q.mean(0)[None,:]*np.exp(logratio)
    assert np.max(abs(wrong-posterior))>.1
    assert np.allclose(1/(1+np.exp(-logratio)),posterior/(posterior+q))
    scores=np.array([[-20.,20.],[.4,-.8],[1.1,.3]])
    def objective(v):return np.mean(losses(v)['BCE'])
    prob=losses(scores)['probability'];analytic=(prob-np.array([1.,0.]))/scores.size
    epsilon=1e-5;numerical=np.zeros_like(scores)
    for i in range(scores.size):
        step=np.zeros(scores.size);step[i]=epsilon;step=step.reshape(scores.shape)
        numerical.ravel()[i]=(objective(scores+step)-objective(scores-step))/(2*epsilon)
    gradient_diff=float(np.max(abs(analytic-numerical)));assert gradient_diff<1e-9
    assert np.isfinite(losses(np.array([[-1000.,1000.],[1000.,-1000.]]))['BCE']).all()
    tr,_,_=training_split(d,p,'final');counts,mass=proposal(d['pz'][tr],d['truth_E_GeV'][tr])
    np.testing.assert_allclose((mass/np.diff(LOG_EDGES)[None,:]*np.diff(LOG_EDGES)[None,:]).sum(1),1)
    zero=np.zeros((7,7));zero[:,1]=1.
    np.testing.assert_allclose(proposal_density(np.array([50.,75.,1000.]),np.log([50.,100.,6400.]),zero),[0.,1/np.log(2),0.],rtol=1e-14)
    pb,eb=bins(np.array([50.,75.,100.,1000.]),np.array([50.,100.,200.,3200.]))
    np.testing.assert_array_equal(pb,[0,1,2,6]);np.testing.assert_array_equal(eb,[0,1,2,6])
    # Deterministic independent proposal draw, no held labels in its API.
    rng=np.random.default_rng(p['seed']+3);neg=draw(d['pz'][tr],mass,rng)
    np.testing.assert_array_equal(neg,draw(d['pz'][tr],mass,np.random.default_rng(p['seed']+3)))
    idx=np.r_[np.flatnonzero(tr&~d['missing'])[:500],np.flatnonzero(tr&d['missing'])[:12]]
    x=d['x'][idx];t=np.log(d['truth_E_GeV'][idx]);n=draw(d['pz'][idx],mass,np.random.default_rng(p['seed']))
    xx,label=paired_matrix(x,t,n,'X');names=p['features']+[QUERY]
    dm=xgb.DMatrix(xx,label=label,feature_names=names,nthread=1)
    assert dm.get_weight().size==0 and label.sum()==len(x)
    fitstart=begin();model=xgb.train(dict(p['xgboost'],seed=p['seed']),dm,num_boost_round=2)
    # Query path sees reco and a proposed hypothesis, never a true-label dictionary.
    query=xgb.DMatrix(query_matrix(x,n,'X'),feature_names=names,nthread=1)
    margin=model.predict(query,output_margin=True)
    np.testing.assert_array_equal(margin,model.predict(dm,output_margin=True)[1::2])
    assert np.isfinite(margin).all()
    params=dict(p['xgboost'],seed=p['seed']);custom=xgb.Booster(params=params,cache=[dm])
    pred=custom.predict(dm,output_margin=True);sigmoid=1/(1+np.exp(-pred))
    custom.boost(dm,0,(sigmoid-dm.get_label()).astype('float32'),(sigmoid*(1-sigmoid)).astype('float32'))
    builtin=xgb.train(params,dm,num_boost_round=1)
    np.testing.assert_array_equal(custom.predict(query),builtin.predict(query))
    measure=resources(fitstart)
    np.testing.assert_array_equal(clean([-999,-1,0],dict(domain='signed')),[-999,-1,0])
    np.testing.assert_array_equal(clean([-999,-1,0],dict(domain='nonnegative')),[np.nan,np.nan,0])
    save(OUT/'pilot.json',dict(passed=True,conditional_independence_logratio_zero=True,
        known_ratio_and_q_recovery=True,wrong_unconditional_q_detected=True,proposal_normalized=True,
        zero_support_and_edges=True,BCE_gradient_max_abs_diff=gradient_diff,analytic_one_step_exact=True,
        query_only_reco_and_candidate=True,NaN_N=int(np.isnan(xx).sum()),real_X_N=len(x),pair_rows=len(label),
        pilot_trees=2,pilot_is_scientific_candidate=False,retained_pilot_models=0,
        resource_pilot=measure,xgboost_version=xgb.__version__,
        frozen_budget='4 jobs /8formal fits;1CPU/3000MB;CPUtotal3600s;wall/job1800s;retained20MB',**resources(start)))
    print((OUT/'pilot.json').read_text())


if __name__=='__main__':main()
