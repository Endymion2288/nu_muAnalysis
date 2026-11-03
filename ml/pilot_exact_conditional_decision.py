#!/usr/bin/env python3
"""Exact-integral synthetic, float32 boundary, traversal and fixed-identity QA."""
import csv
from scipy.special import logsumexp
from exact_conditional_decision import *


def independent(edges, logits, pz, mass):
    """Separate scalar float64 reference; no production integral helper."""
    result=[]
    for i,p in enumerate(pz):
        pb=next(j for j in range(7) if PZ_EDGES[j]<=p<PZ_EDGES[j+1])
        lm=[];centers=[]
        for j,(a,b) in enumerate(zip(edges[:-1],edges[1:])):
            t=(a+b)/2;eb=next(k for k in range(7) if LOG_EDGES[k]<=t<LOG_EDGES[k+1])
            if mass[pb,eb]>0:
                lm.append(float(logits[i,j])+np.log(float(mass[pb,eb]))-np.log(LOG_EDGES[eb+1]-LOG_EDGES[eb])+np.log(b-a))
                centers.append(t)
        lm=np.array(lm);result.append(float(np.sum(np.exp(lm-logsumexp(lm))*centers)))
    return np.array(result)


def synthetic():
    edges=LOG_EDGES.copy();pz=np.array([60.,110.]);mass=np.zeros((7,7));mass[:,0]=.3;mass[:,3]=.7
    logits=np.zeros((2,7));a=constant_integral(edges,logits,pz,mass)
    expected=.3*(edges[0]+edges[1])/2+.7*(edges[3]+edges[4])/2
    np.testing.assert_allclose(a['raw_log'],expected,rtol=0,atol=2e-15)
    shifted=constant_integral(edges,logits+1000,pz,mass)['raw_log']
    np.testing.assert_allclose(a['raw_log'],shifted,rtol=0,atol=1e-12)
    mass[:,0]=0;mass[:,3]=1
    b=constant_integral(edges,logits,pz,mass);np.testing.assert_allclose(b['raw_log'],(edges[3]+edges[4])/2,rtol=0,atol=2e-15)
    score=np.tile(np.arange(7)*.4,(2,1));mass[:]=1/7
    c=constant_integral(edges,score,pz,mass)
    reference=independent(edges,score,pz,mass)
    np.testing.assert_allclose(c['raw_log'],reference,rtol=0,atol=2e-15)
    cut=np.float32(5.);prev=np.nextafter(cut,np.float32(-np.inf));boundary=(float(prev)+float(cut))/2
    assert np.float32(np.nextafter(boundary,-np.inf))==prev
    assert np.float32(np.nextafter(boundary,np.inf))==cut
    # A hand-written stump independently checks missing/default and strict cut.
    tree=dict(left_children=[1,-1,-1],right_children=[2,-1,-1],split_indices=[0,0,0],
        split_conditions=[float(cut),-.7,.8],default_left=[True,False,False],tree_param={'num_nodes':3})
    raw={'learner':{'learner_model_param':{'base_score':'.5'},'gradient_booster':{'model':{'trees':[tree]}}}}
    x=np.array([[prev],[cut],[np.nextafter(cut,np.float32(np.inf))],[np.nan]],dtype='float32')
    np.testing.assert_array_equal(traverse(raw,x),np.array([-.7,.8,.8,-.7],dtype='float32'))
    return dict(passed=True,known_mean_zero_support_and_single_bin=True,score_shift1000_abs_diff=float(max(abs(a['raw_log']-shifted))),
        scalar_logsumexp_reference_max_abs_diff=float(max(abs(c['raw_log']-reference))),
        float32_boundary_strict_cut_and_missing_default=True)


def main():
    start=begin();assert not (OUT/'pilot.json').exists()
    p=json.loads((OUT/'protocol.json').read_text());assert xgb.__version__==p['xgboost_version']
    synth=synthetic();d=arrays(CACHE/'input.npz');proposals=json.loads((OUT/'proposals.json').read_text())
    ids=list(csv.DictReader((OUT/'numerical_QA_identities.tsv').open(),delimiter='\t'))
    assert len(ids)==256 and len(set(v['row'] for v in ids))==256
    old=list(csv.DictReader((REPO/'workbook/stage75_energy_ml/numerical_QA.tsv').open(),delimiter='\t'))
    records=[];perf=[];traversal=[];constancy=[]
    for job in JOBS:
        chosen=[v for v in ids if v['job']==job];row=np.array([int(v['row']) for v in chosen]);idx=np.searchsorted(d['row'],row)
        np.testing.assert_array_equal(d['row'][idx],row)
        small=[]
        for role in sorted(set(v['role'] for v in chosen)):
            ii=np.array([i for i,v in enumerate(chosen) if v['role']==role]);n=8 if role=='held' else 4
            small.extend(ii[fixed_indices(row[ii],n)])
        mass=np.array(proposals[job]['mass'])
        for arm in ARMS:
            booster=model(job,arm,p['features']);edges,cuts=partition(booster);center=(edges[:-1]+edges[1:])/2
            measure=begin();logits=scores(booster,d['x'][idx],center,arm)
            value=constant_integral(edges,logits,d['pz'][idx],mass);cost=resources(measure)
            ref=independent(edges,logits,d['pz'][idx],mass)
            diffs=abs(value['raw_log']-ref)
            assert diffs.max()<=p['numeric_log_mean_tolerance']
            assert value['normalization_error'].max()<=p['numeric_normalization_tolerance']
            perf.append(dict(job=job,arm=arm,real_X_N=len(idx),intervals=len(center),query_rows=len(idx)*len(center),
                query_rows_per_CPU_s=len(idx)*len(center)/cost['CPU_s'],**cost))
            for i,v in enumerate(chosen):
                previous=next(r for r in old if r['job']==job and r['arm']==arm and r['row']==v['row'])
                records.append(dict(job=job,arm=arm,role=v['role'],row=int(v['row']),group=v['group'],
                    exact_log_mean=float(value['raw_log'][i]),scalar_log_mean=float(ref[i]),abs_difference=float(diffs[i]),
                    normalization_error=float(value['normalization_error'][i]),
                    old257_abs_error=float(abs(value['raw_log'][i]-float(previous['log_mean_257']))),
                    old513_abs_error=float(abs(value['raw_log'][i]-float(previous['log_mean_513'])))))
            # Exactly 32 fixed real identities overall; all intervals and three interior positions.
            sample=d['x'][idx[small]];positions=np.array([.25,.5,.75])
            query=(edges[:-1,None]+np.diff(edges)[:,None]*positions).ravel()
            xx=query_matrix(np.repeat(sample,len(query),axis=0),np.tile(query,len(sample)),arm)
            actual=booster.inplace_predict(xx,predict_type='margin')
            independent_score=traverse(serialized(booster),xx)
            np.testing.assert_array_equal(actual,independent_score)
            cube=actual.reshape(len(sample),len(center),3)
            np.testing.assert_array_equal(cube[:,:,0],cube[:,:,1]);np.testing.assert_array_equal(cube[:,:,2],cube[:,:,1])
            traversal.append(dict(job=job,arm=arm,real_X_N=len(sample),query_rows=len(xx),
                missing_reco_values=int(np.isnan(sample).sum()),serialized_traversal_max_abs_diff=0.,interior_score_constancy_max_abs_diff=0.))
            # Test all actual cuts at predecessor/cut/successor, on an already selected identity.
            q=np.column_stack([np.nextafter(cuts,np.float32(-np.inf)),cuts,np.nextafter(cuts,np.float32(np.inf))]).ravel()
            bx=query_matrix(np.repeat(sample[:1],len(q),axis=0),q,arm)
            np.testing.assert_array_equal(booster.inplace_predict(bx,predict_type='margin'),traverse(serialized(booster),bx))
            constancy.append(dict(job=job,arm=arm,query_cuts=len(cuts),boundary_query_rows=len(q),strict_cut_and_float32_neighbors_exact=True))
    table(OUT/'numerical_QA.tsv',records);save(OUT/'traversal_QA.json',dict(interior=traversal,cut_boundaries=constancy))
    save(OUT/'pilot.json',dict(passed=True,synthetic=synth,real_X_N=256,arm_rows=512,interior_real_X_N=32,
        max_log_mean_reference_diff=max(v['abs_difference'] for v in records),
        max_normalization_error=max(v['normalization_error'] for v in records),
        old257_max_abs_error=max(v['old257_abs_error'] for v in records),old513_max_abs_error=max(v['old513_abs_error'] for v in records),
        exact_serialized_traversal=True,all_interval_quarter_mid_threequarter_constant=True,all_actual_cut_neighbor_checks=True,
        energy_point_risk_evaluated=False,new_fits=0,full_grids_retained=False,performance=perf,**resources(start)))
    print((OUT/'pilot.json').read_text())


if __name__=='__main__':main()
