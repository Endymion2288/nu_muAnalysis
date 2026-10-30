#!/usr/bin/env python3
"""Supplement stage26 with fixed trial positions 200..999, point fits only."""
import argparse
import json
import platform
import resource
import time
from pathlib import Path

import numpy as np

from closure import DIRECTIONS, write_table
from profile_response import Inference, METHODS
from run_source_response import packed
from source_response import (ALPHAS, CASES, NULLS, aggregate, config, event_basis,
                             load_events, make_response, random_partition, target_mix)


def main():
    parser=argparse.ArgumentParser(__doc__);parser.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--model',required=True);parser.add_argument('--seed-index',type=int,default=0)
    parser.add_argument('--output-dir',type=Path,required=True);parser.add_argument('--smoke',action='store_true');args=parser.parse_args();tick,cpu=time.perf_counter(),time.process_time()
    cfg=config(args.repo);seed=args.seed_index;assert seed in cfg['models'][args.model]['seeds'];cfg['models'][args.model]['seeds']=[seed]
    start=cfg['permutation_coverage_replicates'];stop=cfg['permutations'];npart=stop-start
    assert (start,stop)==(200,1000)
    if args.smoke:stop=start+2;npart=2
    y,bins,gi,groups,fold,predictions,runs,ri=load_events(args.repo,cfg,args.model,args.smoke)
    basis,index,_,_=event_basis(y,bins,ri,predictions[0],len(runs),cfg)
    pool=aggregate(basis,index,np.ones(len(y)),len(runs));target=target_mix(pool)
    point=np.full((2,npart,2,3,2,2,7),np.nan);loss=np.full((2,npart,2,3,2,2),np.nan)
    truth=np.full((2,npart,2,6),np.nan);counts=np.zeros((2,npart,2,len(runs),6),dtype=np.int16)
    support=np.zeros((2,npart,2,2),dtype=bool);failures=[]
    stats=dict(solver_calls=0,solver_failures=0,iterations=0);kkt=0.;spread=0.
    def log(kind,ni,trial,di,ai,ci,method,status):
        failures.append(dict(model=args.model,seed=seed,kind=kind,null_index=ni,trial=trial,direction=DIRECTIONS[di],
                             alpha_injected=ALPHAS[ai],case=CASES[ci],method=method,parameter=-1,status=status))
    for ni in range(2):
        for local,trial in enumerate(range(start,stop)):
            assigned=random_partition(ni,trial,ri,bins,gi,groups,fold,cfg)
            ac=aggregate(basis,index,assigned,len(runs));split=[ac,pool-ac]
            for di in range(2):
                src,pseudo=split[di],split[1-di];counts[ni,local,di]=src[0].sum(axis=-1).astype(int)
                ftrue=pseudo[0].sum(axis=(0,2));ftrue/=ftrue.sum();truth[ni,local,di]=ftrue
                for ci in range(2):
                    try:response=make_response(src,target,ci);other=make_response(pseudo,target,ci)
                    except ValueError as err:log('unsupported',ni,trial,di,1,ci,'all',str(err));continue
                    support[ni,local,di,ci]=True;inference=Inference(response,cfg,stats)
                    for ai,alpha in enumerate(ALPHAS):
                        q=other.at(alpha)[0]@ftrue;bests=[inference.fit(q,alpha),inference.fit(q)]
                        for mi,best in enumerate(bests):
                            point[ni,local,di,ai,ci,mi]=packed(best);loss[ni,local,di,ai,ci,mi]=best['nll']
                            if best['status']!='ok':log('null_point',ni,trial,di,ai,ci,METHODS[mi],best['status'])
                            else:kkt=max(kkt,best['kkt']);spread=max(spread,best['start_spread'])
            if (trial+1)%100==0:print(f'{args.model} seed={seed} {NULLS[ni]} {trial+1}/{stop}',flush=True)
    out=args.output_dir;out.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(out/'source_extension.npz',null_point=point,null_nll=loss,null_truth=truth,null_counts=counts,null_support=support)
    write_table(out/'extension_failures.tsv',failures)
    summary=dict(model=args.model,seed=seed,smoke=args.smoke,trial_start=start,trial_stop=stop,events=len(y),numerical_stats=stats,
                 failure_cells=sum(r['kind']!='unsupported' for r in failures),unsupported_cases=sum(r['kind']=='unsupported' for r in failures),
                 maximum_kkt=kkt,maximum_start_spread=spread,wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,
                 max_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,host=platform.node(),calibration_test_challenge_evaluated=False)
    (out/'extension_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
