#!/usr/bin/env python3
"""Reuse frozen validation predictions: precise mu momentum need not imply precise nu energy."""
import csv,json,time,resource
from pathlib import Path
import numpy as np,yaml
from train_bdt import write_table
from report_information_gap import quantile_bootstrap
from report_reference_audit import source_interval

def main():
    repo=Path(__file__).resolve().parents[1];out=repo/'workbook/stage33_energy_ml'
    cfg=yaml.safe_load((repo/'ml/configs/low_momentum_audit.yaml').read_text());tick=time.perf_counter();cpu=time.process_time()
    with np.load(repo/'ntuples/energy_ml_stage15/validation_truth.npz') as z:
        t={k:z[k] for k in ['run','eventID','truth_E_GeV','primary_p_GeV','y_lepton','vertex_z_mm','lead_primary_parent_confirmed','reco_p_GeV']}
    pred={k:[] for k in ['nu_F5','nu_F6','mu_F5','mu_F6']};groups=None
    for si in range(3):
        with np.load(repo/f'ml/artifacts/stage30/main/seed_{si}/predictions.npz') as z:
            for k in ['run','eventID']:np.testing.assert_array_equal(t[k],z[k])
            pred['nu_F5'].append(z['A0'])
            if groups is None:groups=z['group']
            else:np.testing.assert_array_equal(groups,z['group'])
        with np.load(repo/f'ml/artifacts/stage31/seed_{si}/predictions.npz') as z:
            for k in ['run','eventID']:np.testing.assert_array_equal(t[k],z[k])
            np.testing.assert_array_equal(groups,z['group'])
            for k in ['nu_F6','mu_F5','mu_F6']:pred[k].append(z[k])
    pred={k:np.stack(v) for k,v in pred.items()}
    pred['mu_reco']=np.tile(t['reco_p_GeV'],(3,1));pred['nu_pmu_over0p8']=pred['mu_reco']/0.8
    _,gid=np.unique(groups,return_inverse=True);ng=int(gid.max()+1)
    draws=np.random.default_rng(cfg['seed']).multinomial(ng,np.full(ng,1/ng),size=cfg['bootstrap_replicates'])
    p=t['primary_p_GeV'];confirmed=t['lead_primary_parent_confirmed'];masks=[]
    for lo,hi in [(25,100),(100,175),(175,250),(100,250),(250,1000),(1000,np.inf)]:
        mask=(p>=lo)&(p<hi);label=f'{lo:g}_{hi:g}'
        masks += [('primary_p_GeV',label,mask),('primary_p_confirmed',label,mask&confirmed),('primary_p_unconfirmed',label,mask&~confirmed)]
    focus=(p>=100)&(p<250)&confirmed
    for lo,hi in zip(cfg['y_edges'][:-1],cfg['y_edges'][1:]):
        masks.append(('focus_y_confirmed',f'{lo:g}_{hi:g}',focus&(t['y_lepton']>=lo)&(t['y_lepton']<hi)))
    masks.append(('reco_p_GeV','100_250',(t['reco_p_GeV']>=100)&(t['reco_p_GeV']<250)))
    metrics=[];paired=[];gains=[]
    for stratum,value,mask in masks:
        if not mask.any():continue
        gg=gid[mask];counts=np.bincount(gg,minlength=ng);den=draws@counts;valid=den>0
        centers={};boots={};n_groups=int((counts>0).sum())
        for model,pr in pred.items():
            target=t['truth_E_GeV'] if model.startswith('nu_') else p
            ratio=pr[:,mask]/target[mask];rr=ratio-1;point={};bs={}
            for key,v in [('log_RMSE',np.mean(np.log(ratio)**2,axis=0)),('mean_bias',rr.mean(0)),('tail_gt0p2',(abs(rr)>.2).mean(0)),('tail_gt0p5',(abs(rr)>.5).mean(0))]:
                point[key]=np.sqrt(np.mean(v)) if key=='log_RMSE' else np.mean(v)
                avg=draws[valid]@np.bincount(gg,weights=v,minlength=ng)/den[valid]
                bs[key]=np.sqrt(avg) if key=='log_RMSE' else avg
            qq=np.quantile(rr,[.16,.5,.84],axis=1)
            qs=np.mean([quantile_bootstrap(r,gg,draws[valid]) for r in rr],axis=0)
            point.update(median_bias=np.mean(qq[1]),R68=np.mean((qq[2]-qq[0])/2))
            bs.update(median_bias=qs[0],R68=qs[1]);centers[model]=point;boots[model]=bs
            for metric,v in point.items():
                lo,hi,status=source_interval(bs[metric],n_groups)
                metrics.append(dict(stratum=stratum,value=value,model=model,N=int(mask.sum()),groups=n_groups,metric=metric,point=v,CI025=lo,CI975=hi,bootstrap_valid=int(valid.sum()),interval_status=status))
        for left,right in [('nu_F5','nu_F6'),('mu_reco','mu_F5'),('mu_reco','mu_F6'),('mu_F5','mu_F6'),('nu_pmu_over0p8','nu_F5')]:
            gain=1-boots[right]['log_RMSE']/boots[left]['log_RMSE']
            lo,hi,status=source_interval(gain,n_groups)
            gains.append(dict(stratum=stratum,value=value,reference=left,model=right,N=int(mask.sum()),groups=n_groups,relative_log_RMSE_gain=1-centers[right]['log_RMSE']/centers[left]['log_RMSE'],CI025=lo,CI975=hi,interval_status=status))
            for metric in centers[left]:
                lo,hi,status=source_interval(boots[right][metric]-boots[left][metric],n_groups)
                paired.append(dict(stratum=stratum,value=value,reference=left,model=right,N=int(mask.sum()),groups=n_groups,metric=metric,delta=centers[right][metric]-centers[left][metric],CI025=lo,CI975=hi,interval_status=status))
    write_table(out/'cached_validation_metrics.tsv',metrics);write_table(out/'cached_validation_paired.tsv',paired);write_table(out/'cached_validation_log_gains.tsv',gains)
    summary=dict(validation_events=len(p),groups=ng,focus_confirmed_events=int(focus.sum()),focus_confirmed_highy_events=int((focus&(t['y_lepton']>=.8)).sum()),existing_seeds_reused=3,new_fits=0,calibration_test_challenge_evaluated=False,wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    (out/'cached_validation_resources.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
    for r in metrics:
        if r['stratum']=='primary_p_confirmed' and r['value'] in ['100_250','1000_inf'] and r['metric'] in ['log_RMSE','R68','median_bias']:print(r)

if __name__=='__main__':main()
