#!/usr/bin/env python3
"""Source-paired physics diagnostics for additional track information."""
import argparse,csv,json,time,resource
from pathlib import Path
import numpy as np
from track_response import configuration
from information_gap import configuration as reference_config,training_summary
from report_information_gap import quantile_bootstrap
from train_bdt import metric_values,write_table


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1]);a=p.parse_args()
    repo=a.repo;cfg=configuration(repo);ref=reference_config(repo);out=repo/'workbook/stage31_energy_ml';tick=time.perf_counter();cpu=time.process_time()
    with np.load(repo/'ntuples/energy_ml_stage15/validation_truth.npz') as z:
        truth={k:z[k] for k in ['run','eventID','truth_E_GeV','primary_p_GeV','primary_pdg','y_lepton','vertex_z_mm','lead_primary_parent_confirmed','reco_p_GeV']}
    with np.load(repo/'ntuples/energy_ml_stage31/validation_tracks.npz') as z:
        track={k:z[k] for k in z.files if k!='config_json'}
    for k in ['run','eventID']:np.testing.assert_array_equal(truth[k],track[k])
    pred={'nu_F5':[],'nu_F6':[],'mu_F5':[],'mu_F6':[]};groups=None;costs=[]
    for si in range(3):
        folder=out/f'seed_{si}';meta=training_summary(folder)
        assert meta['cfg']==cfg and meta['reference_cfg']==ref and not meta['smoke'] and not meta['calibration_test_challenge_evaluated']
        reference=training_summary(repo/f'workbook/stage30_energy_ml/main/seed_{si}')
        assert meta['source_assignment']==reference['source_assignment'] and meta['seed']==reference['seed']
        with np.load(repo/f'ml/artifacts/stage30/main/seed_{si}/predictions.npz') as z:
            for k in ['run','eventID']:np.testing.assert_array_equal(truth[k],z[k])
            pred['nu_F5'].append(z['A0'])
            if groups is None:groups=z['group']
            else:np.testing.assert_array_equal(groups,z['group'])
        with np.load(repo/f'ml/artifacts/stage31/seed_{si}/predictions.npz') as z:
            for k in ['run','eventID']:np.testing.assert_array_equal(truth[k],z[k])
            np.testing.assert_array_equal(groups,z['group'])
            for k in ['nu_F6','mu_F5','mu_F6']:pred[k].append(z[k])
        costs+=list(csv.DictReader((folder/'costs.tsv').open(),delimiter='\t'))
    pred={k:np.stack(v) for k,v in pred.items()};pred['mu_reco']=np.tile(truth['reco_p_GeV'],(3,1))
    y=truth['truth_E_GeV'];n=len(y);_,gid=np.unique(groups,return_inverse=True);ng=gid.max()+1
    draws=np.random.default_rng(ref['split_seed']).multinomial(ng,np.full(ng,1/ng),size=cfg['bootstrap_replicates'])
    masks=[('all','all',np.ones(n,bool))]
    def intervals(label,x,edges):return [(label,f'{lo:g}_{hi:g}',(x>=lo)&(x<hi)) for lo,hi in zip(edges[:-1],edges[1:])]
    masks+=intervals('energy_GeV',y,ref['energy_edges_GeV'])
    masks+=intervals('y_lepton',truth['y_lepton'],ref['y_edges'])
    masks+=intervals('primary_p_GeV',truth['primary_p_GeV'],cfg['truth_p_edges_GeV'])
    masks+=intervals('vertex_z_mm',truth['vertex_z_mm'],ref['vertex_z_edges_mm'])
    confirmed=truth['lead_primary_parent_confirmed'];forward=track['lead_isForward'];q=-np.sign(truth['primary_pdg'])
    masks += [('primary','confirmed',confirmed),('primary','unconfirmed',~confirmed),
              ('forward','yes',forward),('forward','no',~forward),('charge_truth','negative',q<0),('charge_truth','positive',q>0),
              ('y_confirmed','ge0.8',confirmed&(truth['y_lepton']>=.8))]
    # Same confirmed support checks separate response tails from primary misassignment.
    confirmed_masks=[]
    for label,value,mask in masks:
        if label in ['energy_GeV','primary_p_GeV','y_lepton','vertex_z_mm','charge_truth','forward']:
            confirmed_masks.append((label+'_confirmed',value,mask&confirmed))
    masks+=confirmed_masks
    pairs=[('nu_F5','nu_F6'),('mu_F5','mu_F6'),('mu_reco','mu_F5'),('mu_reco','mu_F6')]
    metrics=[];paired=[];per_seed=[];all_scores={};curvature=[]
    for label,value,mask in masks:
        if not mask.any():continue
        counts=np.bincount(gid[mask],minlength=ng);den=draws@counts;valid=den>0;centers={};boots={}
        for model,pr in pred.items():
            target=y if model.startswith('nu') else truth['primary_p_GeV']
            rr=pr[:,mask]/target[mask]-1;logloss=np.mean(np.log(pr[:,mask]/target[mask])**2,axis=0)
            c={};bs={}
            for key,v in dict(log_RMSE=logloss,mean_bias=rr.mean(0),tail_0p5=(abs(rr)>.5).mean(0),tail_1=(abs(rr)>1).mean(0)).items():
                mean=v.mean();c[key]=np.sqrt(mean) if key=='log_RMSE' else mean
                s=np.bincount(gid[mask],weights=v,minlength=ng);b=draws[valid]@s/den[valid];bs[key]=np.sqrt(b) if key=='log_RMSE' else b
            qs=np.mean([quantile_bootstrap(r,gid[mask],draws[valid]) for r in rr],axis=0)
            qq=np.quantile(rr,[.16,.5,.84],axis=1)
            for i,key in enumerate(['median_bias','R68']):
                c[key]=np.mean(qq[1] if i==0 else (qq[2]-qq[0])/2);bs[key]=qs[i]
            centers[model]=c;boots[model]=bs
            for si,prseed in enumerate(pr):per_seed.append(dict(model=model,seed=cfg['seeds'][si],stratum=label,value=value,**metric_values(target,prseed,mask)))
            for key in c:
                lo,hi=np.quantile(bs[key],[.025,.975]);metrics.append(dict(model=model,stratum=label,value=value,N=int(mask.sum()),groups=int((counts>0).sum()),metric=key,point=c[key],CI025=lo,CI975=hi,bootstrap_valid=int(valid.sum())))
        for left,right in pairs:
            for key in centers[left]:
                delta=boots[right][key]-boots[left][key];lo,hi=np.quantile(delta,[.025,.975])
                paired.append(dict(reference=left,model=right,stratum=label,value=value,N=int(mask.sum()),metric=key,delta=centers[right][key]-centers[left][key],CI025=lo,CI975=hi))
        all_scores[(label,value)]=(centers,boots)
        # The truth momentum is at production. These are NOT same-surface fit pulls.
        pt=truth['primary_p_GeV'][mask];qr=track['reco_charge'][mask];qt=q[mask]
        delta=qr/truth['reco_p_GeV'][mask]-qt/pt
        normalized=pt*delta
        row=dict(stratum=label,value=value,N=int(mask.sum()),groups=int((counts>0).sum()),
                 mean_delta_kappa_GeVinv=delta.mean(),median_delta_kappa_GeVinv=np.median(delta),
                 R68_delta_kappa_GeVinv=np.diff(np.quantile(delta,[.16,.84]))[0]/2,
                 mean_normalized_delta=normalized.mean(),median_normalized_delta=np.median(normalized),
                 R68_normalized_delta=np.diff(np.quantile(normalized,[.16,.84]))[0]/2,
                 normalized_tail_gt0p5=(abs(normalized)>.5).mean(),normalized_tail_gt1=(abs(normalized)>1).mean(),
                 signflip_N=int((qr!=qt).sum()),signflip_fraction=(qr!=qt).mean(),median_p1_over_p0=np.median(np.exp(track['ML_track_log_p1_over_p0'][mask])))
        for key,v in [('mean_delta_kappa_GeVinv',delta),('normalized_tail_gt0p5',(abs(normalized)>.5).astype(float)),('signflip_fraction',(qr!=qt).astype(float))]:
            bs=draws[valid]@np.bincount(gid[mask],weights=v,minlength=ng)/den[valid];row[key+'_CI025'],row[key+'_CI975']=np.quantile(bs,[.025,.975])
        for residual,keynames in [(delta,['median_delta_kappa_GeVinv','R68_delta_kappa_GeVinv']),(normalized,['median_normalized_delta','R68_normalized_delta'])]:
            bs=quantile_bootstrap(residual,gid[mask],draws[valid])
            for i,key in enumerate(keynames):row[key+'_CI025'],row[key+'_CI975']=np.quantile(bs[i],[.025,.975])
        curvature.append(row)
    macro=[];gains=[];macro_boot={};macro_center={}
    for model in pred:
        c=[];bs=[]
        for lo,hi in zip(ref['energy_edges_GeV'][:-1],ref['energy_edges_GeV'][1:]):
            center,boot=all_scores[('energy_GeV',f'{lo:g}_{hi:g}')]
            assert len(boot[model]['log_RMSE'])==len(draws)
            c.append(center[model]['log_RMSE']**2);bs.append(boot[model]['log_RMSE']**2)
        point=np.sqrt(np.mean(c));b=np.sqrt(np.mean(bs,axis=0));macro_center[model]=point;macro_boot[model]=b
        lo,hi=np.quantile(b,[.025,.975]);macro.append(dict(model=model,macro_log_RMSE=point,CI025=lo,CI975=hi))
    for left,right in pairs:
        b=1-macro_boot[right]/macro_boot[left];lo,hi=np.quantile(b,[.025,.975])
        point=1-macro_center[right]/macro_center[left]
        dl,dh=np.quantile(macro_boot[right]-macro_boot[left],[.025,.975])
        gains.append(dict(reference=left,model=right,delta=macro_center[right]-macro_center[left],delta_CI025=dl,delta_CI975=dh,relative_gain=point,CI025=lo,CI975=hi,
                          passes_expansion_gate=bool(point>=cfg['minimum_relative_gain'] and lo>0),
                          excludes_5percent_gain=bool(hi<cfg['minimum_relative_gain'])))
    seed_macro=[]
    for model in pred:
        for si,seed in enumerate(cfg['seeds']):
            rows=[r for r in per_seed if r['model']==model and r['seed']==seed and r['stratum']=='energy_GeV']
            assert len(rows)==6
            seed_macro.append(dict(model=model,seed=seed,macro_log_RMSE=np.sqrt(np.mean([r['log_RMSE']**2 for r in rows]))))
    write_table(out/'seed_macro.tsv',seed_macro)
    endpoint=[]
    for part in cfg['partitions']:
        with np.load(repo/f'ntuples/energy_ml_stage31/{part}_tracks.npz') as z:
            ratio=z['ML_track_log_p1_over_p0'];forward=z['lead_isForward']
            for label,mask in [('all',np.ones(len(ratio),bool)),('forward',forward),('backward',~forward)]:
                r=ratio[mask]
                endpoint.append(dict(partition=part,stratum=label,N=len(r),median_log_ratio=np.median(r),
                    q16=np.quantile(r,.16),q84=np.quantile(r,.84),min=r.min(),max=r.max(),
                    abslog_gt0p001=(abs(r)>.001).mean(),abslog_gt0p01=(abs(r)>.01).mean(),abslog_gt0p1=(abs(r)>.1).mean()))
    write_table(out/'endpoint_consistency.tsv',endpoint)
    for filename,rows in [('metrics.tsv',metrics),('paired.tsv',paired),('seed_metrics.tsv',per_seed),('macro.tsv',macro),('gains.tsv',gains),('curvature.tsv',curvature),('costs.tsv',costs)]:write_table(out/filename,rows)
    with np.load(repo/'ntuples/energy_ml_stage31/data_control.npz') as z:
        meta=json.loads(str(z['metadata_json']));assert meta.pop('cfg')==cfg
        meta['config_file']='ml/configs/track_response.yaml'
        write_table(out/'data_feature_profile.tsv',meta.pop('profile'))
        report=meta['reports'][0];report.pop('profile');(out/'data_control.json').write_text(json.dumps(meta,indent=2)+'\n')
    with np.load(repo/'ntuples/energy_ml_stage31/tracker_data_control.npz') as z:
        meta=json.loads(str(z['metadata_json']));assert meta.pop('cfg')==cfg
        meta['config_file']='ml/configs/track_response.yaml'
        write_table(out/'tracker_data_feature_profile.tsv',meta.pop('profile'))
        report=meta['reports'][0];report.pop('profile');write_table(out/'tracker_data_calo_profile.tsv',report.pop('calo_profile'))
        (out/'tracker_data_control.json').write_text(json.dumps(meta,indent=2)+'\n')
    summary=dict(validation_events=n,groups=int(ng),bootstrap_replicates=len(draws),
                 wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                 same_ids_support_p_charge_and_splits_verified=True,calibration_test_challenge_evaluated=False)
    (out/'report_resources.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(dict(macro=macro,gains=gains,resources=summary),indent=2))

if __name__=='__main__':main()
