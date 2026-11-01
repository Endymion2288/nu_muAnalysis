#!/usr/bin/env python3
"""Run held-out nonparametric response-MC bootstrap LR calibration."""
import argparse,json,platform,resource,time
from pathlib import Path
import numpy as np
import scipy

from closure import load_data
from independent_response import population_checks
from mc_bootstrap import (aggregate,basis,bootstrap_indices,config,counts_from_uniform,
                          observed_uniform,pseudo_uniform,source_sample_indices)
from profile_response import Inference,Response,synthetic_checks


def packed(x): return np.r_[x['f'],x['alpha']]


def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--model',required=True);p.add_argument('--seed-index',type=int,required=True);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--smoke',action='store_true');a=p.parse_args()
    tick=time.perf_counter();cpu=time.process_time();cfg=config(a.repo);seed=a.seed_index;cfg['models'][a.model]['seeds']=[seed]
    assert seed in cfg['models'][a.model]['seeds'];checks=synthetic_checks(cfg)
    y,bins,gi,groups,fold,pred=load_data(a.repo,cfg,a.model,False);powers,index,logs,reco=basis(y,bins,pred[0],cfg)
    pool=aggregate(powers,index,np.ones(len(y)));population=Response(pool);truth=np.bincount(bins,minlength=6)/len(y);sizes=np.bincount(bins,minlength=6)//2
    checks.update(population_checks(population,bins,reco,logs));nt=4 if a.smoke else cfg['trials'];nb=3 if a.smoke else cfg['bootstrap_replicates'];cal=min(cfg['calibration_trials'],nt//2)
    out=a.output_dir;out.mkdir(parents=True,exist_ok=True);stats=dict(solver_calls=0,solver_failures=0,iterations=0)
    actual=np.full((nt,7),np.nan);bootstrap_lr=np.full((nt,nb,7),np.nan);bootfits=np.full((nt,nb,7),np.nan);bootloss=np.full((nt,nb),np.nan);bootcounts=np.zeros((nt,nb,10),dtype=np.int16);actualloss=np.full(nt,np.nan);fits=np.full((nt,7),np.nan);counts=np.zeros((nt,10),dtype=np.int16);thresholds=np.full(2,np.nan);widths=[];failures=[];max_kkt=0.;negclip=0
    for ti in range(nt):
        source=source_sample_indices(bins,sizes,ti,cfg,seed);weights=np.bincount(np.concatenate(source),minlength=len(bins));response=Response(aggregate(powers,index,weights));q=population.at(0.)[0]@truth
        u=observed_uniform(seed,ti,cfg);obs=counts_from_uniform(q,u);counts[ti]=obs;inf=Inference(response,cfg,stats);best=inf.fit(obs)
        if best['status']!='ok': failures.append(dict(trial=ti,kind='observed',status=best['status']));continue
        fits[ti]=packed(best);actualloss[ti]=best['nll'];max_kkt=max(max_kkt,best['kkt']);
        for par in range(7):
            target=truth[par] if par<6 else 0.
            partial=inf.conditional(obs,best,par,target);lr,raw=inf.lr(partial,best);actual[ti,par]=lr
            if np.isfinite(raw) and raw<0 and np.isfinite(lr):negclip+=1

            if not np.isfinite(lr):failures.append(dict(trial=ti,kind='observed_lr',parameter=par,status='profile_or_negative_lr'))
        for ri in range(nb):
            boot=bootstrap_indices(source,ti,ri,cfg,seed);bw=np.bincount(np.concatenate(boot),minlength=len(bins));rb=Response(aggregate(powers,index,bw));prob=response.at(best['alpha'])[0]@best['f'];pseudo=counts_from_uniform(prob,pseudo_uniform(seed,ti,ri,cfg));ib=Inference(rb,cfg,stats);bb=ib.fit(pseudo)
            bootcounts[ti,ri]=pseudo
            if bb['status']!='ok': failures.append(dict(trial=ti,replicate=ri,kind='bootstrap',status=bb['status']));continue
            bootfits[ti,ri]=packed(bb);bootloss[ti,ri]=bb['nll']
            for par in range(7):
                target=best['f'][par] if par<6 else best['alpha'];partial=ib.conditional(pseudo,bb,par,target);lr,raw=ib.lr(partial,bb);bootstrap_lr[ti,ri,par]=lr
                if np.isfinite(raw) and raw<0 and np.isfinite(lr):negclip+=1
                if not np.isfinite(lr):failures.append(dict(trial=ti,replicate=ri,kind='bootstrap_lr',parameter=par,status='profile_or_negative_lr'))
        if (ti+1)%10==0 or ti+1==nt: print(f'{a.model} seed={seed} trial={ti+1}/{nt}',flush=True)
    if nt>=2:
        flat=bootstrap_lr[:cal,:, :6][np.isfinite(bootstrap_lr[:cal,:, :6])];thresholds[0]=float(np.quantile(flat,cfg['threshold_quantile']))
        flat=bootstrap_lr[:cal,:,6][np.isfinite(bootstrap_lr[:cal,:,6])];thresholds[1]=float(np.quantile(flat,cfg['threshold_quantile']))
    for ti in range(cal,nt):
        if not np.isfinite(actual[ti]).all():continue
        if ti<cal+cfg['interval_width_trials']:
            source=source_sample_indices(bins,sizes,ti,cfg,seed);weights=np.bincount(np.concatenate(source),minlength=len(bins));response=Response(aggregate(powers,index,weights));inf=Inference(response,cfg,stats);best=inf.fit(counts[ti]);
            if best['status']=='ok':
                for par,thr in zip([5,6],[1.,1.]):
                    fixed=inf.interval(counts[ti],best,par);cfg2={**cfg,'likelihood_ratio_threshold':float(thresholds[0] if par==5 else thresholds[1])};inf2=Inference(response,cfg2,stats);calibrated=inf2.interval(counts[ti],best,par)
                    widths.append(dict(trial=ti,parameter=par,fixed_low=fixed['low'],fixed_high=fixed['high'],calibrated_low=calibrated['low'],calibrated_high=calibrated['high'],fixed_status=fixed['interval_status'],calibrated_status=calibrated['interval_status'],fixed_reentry=fixed['scan_reentry'],calibrated_reentry=calibrated['scan_reentry'],fixed_width=fixed['high']-fixed['low'],calibrated_width=calibrated['high']-calibrated['low'],fixed_low_limited=fixed['low_limited'],fixed_high_limited=fixed['high_limited'],calibrated_low_limited=calibrated['low_limited'],calibrated_high_limited=calibrated['high_limited']))
    np.savez_compressed(out/'mc_bootstrap.npz',pool=pool,truth=truth,sizes=sizes,counts=counts,fits=fits,actual_lrs=actual,actual_loss=actualloss,bootstrap_lrs=bootstrap_lr,bootstrap_fits=bootfits,bootstrap_loss=bootloss,bootstrap_counts=bootcounts,thresholds=thresholds)
    from closure import write_table
    write_table(out/'widths.tsv',widths)
    (out/'failures.json').write_text(json.dumps(failures,indent=2)+'\n');summary=dict(model=a.model,seed=seed,smoke=a.smoke,events=len(y),trials=nt,calibration_trials=cal,bootstrap_replicates=nb,truth_counts=np.bincount(bins,minlength=6).tolist(),mc_counts=sizes.tolist(),thresholds=thresholds.tolist(),widths=len(widths),failures=len(failures),numerical_stats=stats,maximum_kkt=max_kkt,negative_lr_clipped=negclip,checks=checks,wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,max_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,host=platform.node(),numpy=np.__version__,scipy=scipy.__version__)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
