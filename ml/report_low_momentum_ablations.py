#!/usr/bin/env python3
"""Matched historical controls; no attribution from a fixed p/0.8 baseline alone."""
import json,time,resource
from pathlib import Path
import numpy as np,yaml
from train_bdt import write_table
from report_information_gap import quantile_bootstrap
from report_reference_audit import source_interval

def main():
    repo=Path(__file__).resolve().parents[1];out=repo/'workbook/stage33_energy_ml';tick=time.perf_counter();cpu=time.process_time()
    cfg=yaml.safe_load((repo/'ml/configs/low_momentum_audit.yaml').read_text())
    with np.load(repo/'ntuples/energy_ml_stage15/validation_truth.npz') as z:
        t={k:z[k] for k in ['run','eventID','truth_E_GeV','primary_p_GeV','y_lepton','lead_primary_parent_confirmed']}
    families={}
    with np.load(repo/'ml/artifacts/stage13/validation_predictions.npz') as z:
        for k in ['run','eventID']:np.testing.assert_array_equal(t[k],z[k])
        families['legacy_d3_600']=(z['group'],{k:z[k][None,:] for k in ['F0_direct','F1_direct','F2_direct','F3_direct','F5_direct','F5_without_counts_direct','F5_without_scintillator_direct','F5_without_calo_direct','F5_without_shape_direct']})
    names=['F1','F2','F3','F5','F5_without_scintillator','F5_without_calo','F5_without_shape'];pr={k:[] for k in names};groups=None
    for si in range(3):
        with np.load(repo/f'ml/artifacts/stage14/seed_{si}/predictions.npz') as z:
            for k in ['run','eventID']:np.testing.assert_array_equal(t[k],z[k])
            if groups is None:groups=z['group']
            else:np.testing.assert_array_equal(groups,z['group'])
            for k in names:pr[k].append(z['d5_1600__'+k])
    families['robust_d5_1600']=(groups,{k:np.stack(v) for k,v in pr.items()})
    p=t['primary_p_GeV'];conf=t['lead_primary_parent_confirmed'];focus=(p>=100)&(p<250)&conf
    masks=[('focus_confirmed',focus),('focus_highy_confirmed',focus&(t['y_lepton']>=.8)),('highp_confirmed',(p>=1000)&conf)]
    rows=[];metric_rows=[]
    for family,(groups,pred) in families.items():
        _,gid=np.unique(groups,return_inverse=True);ng=int(gid.max()+1);draws=np.random.default_rng(cfg['seed']).multinomial(ng,np.full(ng,1/ng),size=cfg['bootstrap_replicates'])
        for stratum,mask in masks:
            gg=gid[mask];counts=np.bincount(gg,minlength=ng);den=draws@counts;valid=den>0;ns=int((counts>0).sum());centers={};boots={}
            for model,pr in pred.items():
                rr=pr[:,mask]/t['truth_E_GeV'][mask]-1;loss=np.mean(np.log1p(rr)**2,axis=0)
                point=np.sqrt(loss.mean());bs=np.sqrt(draws[valid]@np.bincount(gg,weights=loss,minlength=ng)/den[valid])
                centers[model]=point;boots[model]=bs;lo,hi,status=source_interval(bs,ns)
                metric_rows.append(dict(family=family,stratum=stratum,model=model,seeds=len(pr),N=int(mask.sum()),groups=ns,log_RMSE=point,CI025=lo,CI975=hi,interval_status=status))
            if family=='legacy_d3_600':
                pairs=[('F0_direct','F5_direct'),('F1_direct','F2_direct'),('F2_direct','F3_direct')]+[(f'F5_without_{g}_direct','F5_direct') for g in ['counts','scintillator','calo','shape']]
            else:
                pairs=[('F1','F2'),('F2','F3')]+[(f'F5_without_{g}','F5') for g in ['scintillator','calo','shape']]
            for left,right in pairs:
                gain=1-boots[right]/boots[left];lo,hi,status=source_interval(gain,ns)
                dl,dh,_=source_interval(boots[right]-boots[left],ns)
                rows.append(dict(family=family,stratum=stratum,reference=left,model=right,N=int(mask.sum()),groups=ns,relative_gain=1-centers[right]/centers[left],CI025=lo,CI975=hi,delta_log_RMSE=centers[right]-centers[left],delta_CI025=dl,delta_CI975=dh,interval_status=status))
    write_table(out/'historical_ablation_metrics.tsv',metric_rows);write_table(out/'historical_ablation_paired.tsv',rows)
    summary=dict(new_fits=0,families=['legacy stage13 d3/600 one seed','stage14 fixed d5/1600 three seeds'],purpose='exploratory matched controls; do not mix with stage30/31 capacity/split as one controlled comparison',wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    (out/'historical_ablation_resources.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
    for row in rows:
        if row['stratum']=='focus_confirmed':print(row)

if __name__=='__main__':main()
