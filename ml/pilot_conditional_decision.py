#!/usr/bin/env python3
"""Synthetic integral QA and frozen 257/513 real-identity convergence gate."""
import csv
from conditional_decision import *


def synthetic():
    nodes=grid(257); pz=np.array([60.,110.,600.])
    mass=np.zeros((7,7));mass[:,0]=.3;mass[:,3]=.7
    constant=np.zeros((3,len(nodes)))
    expect=.3*(LOG_EDGES[0]+LOG_EDGES[1])/2+.7*(LOG_EDGES[3]+LOG_EDGES[4])/2
    a=integrate(nodes,constant,pz,mass)
    np.testing.assert_allclose(a['raw_log'],expect,atol=2e-15,rtol=0)
    np.testing.assert_allclose(a['low_bin_mass'],.3,atol=2e-15,rtol=0)
    np.testing.assert_allclose(a['logZ'],0,atol=2e-15,rtol=0)
    shifted=integrate(nodes,constant+1000,pz,mass)
    np.testing.assert_array_equal(a['raw_log'],shifted['raw_log'])
    np.testing.assert_allclose(shifted['logZ'],1000,atol=1e-12,rtol=0)
    # Single supported bin, no interpolation leakage through zero-q intervals.
    single=np.zeros((7,7));single[:,2]=1
    b=integrate(nodes,constant,pz,single)
    np.testing.assert_allclose(b['raw_log'],(LOG_EDGES[2]+LOG_EDGES[3])/2,atol=2e-15,rtol=0)
    # Independent analytic truncated exponential mean, with known integration error.
    uniform=np.tile(np.diff(LOG_EDGES)/(LOG_EDGES[-1]-LOG_EDGES[0]),(7,1))
    score=np.tile(.7*nodes,(3,1));c=integrate(nodes,score,pz,uniform)
    lo,hi=LOG_EDGES[[0,-1]];k=.7
    exact=(hi*np.exp(k*hi)-lo*np.exp(k*lo))/(np.exp(k*hi)-np.exp(k*lo))-1/k
    analytic_diff=float(np.max(abs(c['raw_log']-exact)))
    assert analytic_diff<1e-4
    # Independent interval quadrature on the declared linear-density interpolant.
    mid=(nodes[:-1]+nodes[1:])/2;h=np.diff(nodes);u=1/np.sqrt(3)
    xx=np.array([mid-u*h/2,mid+u*h/2]);ff=np.exp(.7*nodes)
    frac=(xx-nodes[:-1])/h
    values=ff[:-1]+frac*(ff[1:]-ff[:-1])
    independent=(np.sum(h*np.sum(xx*values,axis=0)/2)/np.sum(h*np.sum(values,axis=0)/2))
    reference_diff=float(abs(independent-c['raw_log'][0]));assert reference_diff<2e-15
    return dict(passed=True,piecewise_q_and_zero_support=True,stable_shift1000_exact=True,
        known_constant_mean_exact=True,single_bin_no_leakage=True,
        analytic_exponential_mean_abs_error=analytic_diff,independent_quadrature_abs_diff=reference_diff)


def main():
    start=begin();assert not (OUT/'pilot.json').exists()
    p=json.loads((OUT/'protocol.json').read_text());assert xgb.__version__==p['xgboost_version']
    synth=synthetic();d=arrays(CACHE/'input.npz')
    ids=list(csv.DictReader((OUT/'numerical_QA_identities.tsv').open(),delimiter='\t'))
    records=[];perf=[];source=[]
    for job in JOBS:
        chosen=[v for v in ids if v['job']==job];row=np.array([int(v['row']) for v in chosen])
        idx=np.searchsorted(d['row'],row);np.testing.assert_array_equal(d['row'][idx],row)
        a=arrays(MODEL_ART/job/'predictions.npz');mass=a['proposal_mass']
        for arm in ARMS:
            booster=model(job,arm,p['features']);measure=begin()
            coarse=predict(booster,d['x'][idx],d['pz'][idx],mass,arm,257)
            coarse_cost=resources(measure);measure=begin()
            fine=predict(booster,d['x'][idx],d['pz'][idx],mass,arm,513)
            fine_cost=resources(measure)
            # Independent DMatrix API at prescribed query nodes; no new fit.
            nodes=grid(257);x=query_matrix(np.repeat(d['x'][idx[:2]],len(nodes),axis=0),np.tile(nodes,2),arm)
            direct=booster.predict(xgb.DMatrix(x,feature_names=booster.feature_names,nthread=1),output_margin=True).reshape(2,-1).astype(float)
            np.testing.assert_array_equal(integrate(nodes,direct,d['pz'][idx[:2]],mass)['raw_log'],coarse['raw_log'][:2])
            diff=abs(coarse['raw_log']-fine['raw_log'])
            for i,v in enumerate(chosen):records.append(dict(job=job,arm=arm,role=v['role'],row=int(v['row']),group=v['group'],
                log_mean_257=float(coarse['raw_log'][i]),log_mean_513=float(fine['raw_log'][i]),abs_difference=float(diff[i])))
            groups=np.array([v['group'] for v in chosen])
            for g in np.unique(groups):source.append(dict(job=job,arm=arm,group=g,N=int((groups==g).sum()),median_abs_difference=float(np.median(diff[groups==g]))))
            perf.append(dict(job=job,arm=arm,real_X_N=len(row),main_query_rows=len(row)*len(grid(257)),
                main=coarse_cost,QA=fine_cost,main_query_rows_per_CPU_s=len(row)*len(grid(257))/coarse_cost['CPU_s'],
                normalization_error_max=float(coarse['normalization_error'].max()),independent_DMatrix_exact=True))
    table(OUT/'numerical_QA.tsv',records);table(OUT/'numerical_source_QA.tsv',source)
    maximum=max(v['abs_difference'] for v in records);median_max=max(v['median_abs_difference'] for v in source)
    passed=maximum<=p['numerical_max_abs_log_mean_difference'] and median_max<=p['numerical_source_median_limit']
    save(OUT/'pilot.json',dict(passed=passed,synthetic=synth,unique_real_X_N=len(ids),arm_rows=len(records),
        max_abs_log_mean_difference=maximum,max_source_median_abs_difference=median_max,
        main_grid_nodes=len(grid(257)),QA_grid_nodes=len(grid(513)),performance=perf,
        formal_fits=0,formal_point_jobs=0,truth_not_used_for_mapping_or_identity_selection=True,
        energy_point_risks_measured=False,full_grids_retained=False,**resources(start)))
    print((OUT/'pilot.json').read_text())


if __name__=='__main__':main()
