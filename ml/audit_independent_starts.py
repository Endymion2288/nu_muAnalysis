#!/usr/bin/env python3
"""Replay unchanged stage27 jobs to explain transient SLSQP start failures."""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

import profile_response
import run_independent_response as worker
from check_profile_response import convex, scan_profile
from independent_response import config


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--repo',type=Path,required=True)
    parser.add_argument('--model',required=True);parser.add_argument('--seed-index',type=int,required=True)
    parser.add_argument('--alpha-index',type=int,required=True);parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args();cfg=config(args.repo);state={};records=[]
    old_sample=worker.sample_weights
    def sample(*a,**kw):
        state['trial']=a[3];return old_sample(*a,**kw)
    worker.sample_weights=sample
    old_minimize=profile_response.minimize
    def minimize(*a,**kw):
        result=old_minimize(*a,**kw)
        state['scipy']=dict(success=bool(result.success),status=int(result.status),message=str(result.message),
                            iterations=int(result.nit),x=result.x.tolist(),fun=float(result.fun))
        return result
    profile_response.minimize=minimize
    old_solve=profile_response.Inference._solve
    def solve(self,q,start,fixed_bin=None,value=None,known_alpha=None):
        result=old_solve(self,q,start,fixed_bin,value,known_alpha)
        if result['status']!='ok':
            record=dict(trial=state['trial'],fixed_bin=fixed_bin,value=value,known_alpha=known_alpha,
                        start=np.asarray(start).tolist(),candidate={k:(v.tolist() if isinstance(v,np.ndarray) else v) for k,v in result.items()},
                        scipy=state['scipy'].copy())
            if known_alpha is None: loss=scan_profile(q,self.response,cfg,fixed_bin,value)
            else: loss=convex(q,self.response.at(known_alpha)[0],cfg,fixed_bin,value)
            record['independent_best_nll']=loss;records.append(record)
        return result
    profile_response.Inference._solve=solve
    worker.main()
    original=args.repo/f'ml/artifacts/stage27/{args.model}/seed_{args.seed_index}/alpha_{args.alpha_index}/independent_inference.npz'
    current=args.output_dir/'independent_inference.npz';differences={}
    with np.load(original) as left,np.load(current) as right:
        assert left.files==right.files
        for key in left.files:
            a,b=left[key],right[key]
            differences[key]=float(np.max(abs(a.astype(float)-b.astype(float))))
            np.testing.assert_allclose(a,b,atol=1e-8,rtol=1e-7)
    result=dict(model=args.model,seed=args.seed_index,alpha_index=args.alpha_index,failed_starts=records,
                original_arrays_unchanged=True,replay_maximum_array_differences=differences)
    (args.output_dir/'start_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    # The original production arrays remain authoritative; discard the replay.
    for p in args.output_dir.iterdir():
        if p.name!='start_audit.json':p.unlink()
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
