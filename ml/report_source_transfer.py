#!/usr/bin/env python3
"""Paired fixed-model source replication, proper scores and empirical spectrum diagnostics."""
import json
import resource
import time
import numpy as np
from source_transfer import CACHE,OUT,configuration
from report_calonu_information import strata,source_draws
from probability_information import probability_metrics,score_information
from train_bdt import metric_values,write_table


def finite_quantile(values,q):
    v=np.asarray(values);v=v[np.isfinite(v)]
    return float(np.quantile(v,q)) if len(v) else None


cfg=configuration();tick,cpu=time.perf_counter(),time.process_time()
with np.load(CACHE/'predictions.npz') as z:d={k:z[k] for k in z.files}
md=json.loads(str(d.pop('metadata_json')));assert md['config']==cfg and md['energy_fits']==md['target_calibration_fits']==0
(OUT/'inference_resources.json').write_text(json.dumps({k:v for k,v in md.items() if k!='config'},indent=2)+'\n')
y=d['truth_E_GeV'];lab=np.searchsorted(cfg['energy_edges_GeV'],y,side='right')-1
assert ((lab>=0)&(lab<6)).all()
unique,gid,draws=source_draws(d,cfg['bootstrap_replicates'],cfg['seed']);ng=len(unique)
metrics=[];paired=[];spectra=[];spectral_pairs=[]
for label,mask in strata(d).items():
    if not mask.any():continue
    count=np.bincount(gid,weights=mask,minlength=ng);den=draws@count;ok=den>0;risks={};bscores={}
    for name in cfg['models']:
        metrics.append(dict(stratum=label,model=name,sources=int(np.count_nonzero(count)),**metric_values(y,d[name],mask),
                            **{'prob_'+k:v for k,v in probability_metrics(d['q_'+name][mask],lab[mask]).items()}))
        error=np.log(d[name]/y);risks[name]=np.sqrt((draws[ok]@np.bincount(gid,weights=mask*error**2,minlength=ng))/den[ok])
    gain=1-risks['oracle_z']/risks['local']
    r=dict(stratum=label,N=int(mask.sum()),sources=int(np.count_nonzero(count)),reference='local',model='oracle_z',
           relative_gain=float(1-np.sqrt(np.mean(np.log(d['oracle_z'][mask]/y[mask])**2)/np.mean(np.log(d['local'][mask]/y[mask])**2))),
           log_RMSE_delta=float(np.sqrt(np.mean(np.log(d['oracle_z'][mask]/y[mask])**2))-np.sqrt(np.mean(np.log(d['local'][mask]/y[mask])**2))),
           CI025=float(np.quantile(gain,.025)),CI975=float(np.quantile(gain,.975)),valid_bootstrap=int(ok.sum()))
    for key,values in [('mean_bias',d['oracle_z']/y-d['local']/y),('tail_0p5',(abs(d['oracle_z']/y-1)>.5).astype(float)-(abs(d['local']/y-1)>.5)),
                       ('tail_1',(abs(d['oracle_z']/y-1)>1).astype(float)-(abs(d['local']/y-1)>1))]:
        bs=(draws[ok]@np.bincount(gid,weights=mask*values,minlength=ng))/den[ok]
        r.update({key+'_delta':float(values[mask].mean()),key+'_CI025':float(np.quantile(bs,.025)),key+'_CI975':float(np.quantile(bs,.975))})
    paired.append(r)
    if label not in ['all','focus']:continue
    sigma={}
    for name in cfg['models']:
        q=d['q_'+name][mask];ratio=q/d['prior'][mask];truth=lab[mask]
        info,_=score_information(ratio,truth,np.ones(mask.sum()));bs=[]
        for draw in draws:
            v,_=score_information(ratio,truth,draw[gid[mask]].astype(float));bs.append(v.get('relative_sigma_RMS',np.nan))
        sigma[name]=np.array(bs)
        loss=-np.log(q[np.arange(len(truth)),truth]);bscores[name]=(draws@np.bincount(gid[mask],weights=loss,minlength=ng))/(draws@count)
        spectra.append(dict(stratum=label,model=name,N=int(mask.sum()),**probability_metrics(q,truth),
                            true_bin_counts=np.bincount(truth,minlength=6).tolist(),score_valid=info['valid'],
                            score_relative_sigma_RMS=info.get('relative_sigma_RMS'),score_condition=info.get('condition'),
                            score_bootstrap_valid=int(np.isfinite(bs).sum()),score_CI025=finite_quantile(bs,.025),score_CI975=finite_quantile(bs,.975)))
    score_delta=bscores['oracle_z']-bscores['local'];sigma_gain=1-sigma['oracle_z']/sigma['local']
    point=-np.log(d['q_oracle_z'][mask][np.arange(mask.sum()),lab[mask]])+np.log(d['q_local'][mask][np.arange(mask.sum()),lab[mask]])
    spectral_pairs.append(dict(stratum=label,reference='local',model='oracle_z',log_score_delta=float(point.mean()),
                               CI025=float(np.quantile(score_delta,.025)),CI975=float(np.quantile(score_delta,.975)),
                               score_sigma_gain_CI025=finite_quantile(sigma_gain,.025),score_sigma_gain_CI975=finite_quantile(sigma_gain,.975),
                               score_sigma_valid_bootstrap=int(np.isfinite(sigma_gain).sum())))
write_table(OUT/'metrics.tsv',metrics);write_table(OUT/'paired.tsv',paired);write_table(OUT/'spectrum_paired.tsv',spectral_pairs)
(OUT/'spectrum.json').write_text(json.dumps(spectra,indent=2)+'\n')
focus=next(r for r in paired if r['stratum']=='focus')
summary=dict(events=len(y),focus_events=focus['N'],sources=ng,support_level=cfg['support_level'],energy_fits=0,target_calibration_fits=0,
             main=focus,source_migration_gate_passed=bool(focus['relative_gain']>=cfg['gate']['minimum_relative_log_RMSE_gain'] and focus['CI025']>0),
             independent_production_confirmation=False,retraining_and_detector_systematics_propagated=False,
             wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
(OUT/'evaluation.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)
