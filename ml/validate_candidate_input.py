"""Independent saved-cache geometry checks and fixed40 checkpoint replay."""
import argparse
import json

import numpy as np

from prepare_candidate_ablation import REPO,OUT,CACHE,arrays,save


def inputs():
    c=arrays(CACHE/'candidates.npz')
    with np.load(REPO/'ntuples/energy_ml_stage94/evaluation_input.npz') as d:
        np.testing.assert_array_equal(c['row'],d['row']);pz=d['pz'].copy()
    n=np.diff(c['offsets']);ec=np.diff(c['edge_offsets']);a=c['available']
    assert len(c['row'])==71376 and c['nodes'].shape[1]==22 and c['edges'].shape[1]==5
    assert np.all(n[~a]==0) and np.all(n[a]>0) and np.all(ec==np.maximum(n-1,0))
    assert c['offsets'][-1]==len(c['nodes']) and c['edge_offsets'][-1]==len(c['edges'])
    assert not np.isinf(c['nodes']).any() and not np.isinf(c['edges']).any()
    lead=c['nodes'][c['offsets'][:-1][a],0].astype(float)
    np.testing.assert_allclose(lead,pz[a],rtol=2e-7,atol=2e-4)
    lp=np.repeat(c['offsets'][:-1],ec);op=np.concatenate([np.arange(c['offsets'][i]+1,c['offsets'][i+1]) for i in np.flatnonzero(ec)])
    left=c['nodes'][lp].astype(float);right=c['nodes'][op].astype(float)
    expected=[]
    for x,y in [(7,8),(20,21),(16,17)]:expected.append(np.hypot(left[:,x]-right[:,x],left[:,y]-right[:,y]))
    expected.append(np.hypot(left[:,1]/left[:,0]-right[:,1]/right[:,0],left[:,2]/left[:,0]-right[:,2]/right[:,0]))
    expected.append(np.where(np.isfinite(left[:,3])&np.isfinite(right[:,3]),left[:,3]==right[:,3],np.nan))
    expected=np.column_stack(expected)
    np.testing.assert_allclose(expected,c['edges'],rtol=2e-6,atol=2e-4,equal_nan=True)
    maximum=np.nanmax(abs(expected-c['edges']),axis=0)
    # Check canonical order without imposing a new candidate quality cut.
    ordered=True
    for i in np.flatnonzero(a):
        v=c['nodes'][c['offsets'][i]:c['offsets'][i+1],0];v=v[np.isfinite(v)]
        if np.any(np.diff(v)>0):ordered=False;break
    assert ordered
    save('input_validation.json',dict(passed=True,records=len(n),available_N=int(a.sum()),unavailable_N=int((~a).sum()),
         node_rows=len(c['nodes']),leading_edges=len(c['edges']),max_candidates=int(n.max()),max_edges=int(ec.max()),
         max_float32_cache_leading_difference_GeV=float(abs(lead-pz[a]).max()),
         max_float32_cache_leading_relative_difference=float((abs(lead-pz[a])/pz[a]).max()),
         native_extraction_leading_difference_GeV=max(p['max_leading_pz_difference_GeV'] for p in json.loads((OUT/'performance.json').read_text())),
         independent_geometry_comparisons=int(expected.size),max_cache_recomputed_edge_delta=maximum.tolist(),
         edge_check_tolerance='rtol2e-6/atol2e-4 in saved edge units; native->float32 quantization, not source identity tolerance',
         canonical_order=True,missing_source_not_empty=True,new_PHYS_reads=0,new_fits=0))
    print((OUT/'input_validation.json').read_text(),flush=True)


def replay():
    import torch
    from train_candidate_ablation import input_arrays,subset,constant_branch,tensors,CandidateModel
    from retrain_accurate_posterior import reconstruct
    torch.set_num_threads(1);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    q=arrays(CACHE/'QA_candidates.npz');c=arrays(CACHE/'candidates.npz');d=reconstruct(q['row']);assert len(d['row'])==40
    state=json.loads((OUT/'preprocessing.json').read_text());x,_=input_arrays(d,subset(c,d['row']),state)
    p=arrays(REPO/'ml/artifacts/stage96/predictions.npz');ix=np.searchsorted(p['row'],d['row']);np.testing.assert_array_equal(p['row'][ix],d['row'])
    checks=[]
    for cell in ['A','B']:
        saved=torch.load(REPO/f'ml/artifacts/stage96/{cell}.pt',map_location='cpu',weights_only=True)
        model=CandidateModel(saved['center']).cuda();model.load_state_dict(saved['state_dict']);model.eval()
        with torch.no_grad():prediction=model(**tensors(constant_branch(x) if cell=='A' else x,'cuda')).cpu().numpy()
        delta=float(abs(prediction-p[cell+'_raw'][ix]).max());assert delta<3e-6
        checks.append(dict(cell=cell,max_checkpoint_replay_logE_difference=delta))
    save('checkpoint_QA.json',dict(passed=True,identities=40,original_train_cal_only=True,new_test_predictions=0,new_fits=0,checks=checks))
    print((OUT/'checkpoint_QA.json').read_text(),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['inputs','replay']);a=p.parse_args()
    {'inputs':inputs,'replay':replay}[a.action]()
