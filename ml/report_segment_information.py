#!/usr/bin/env python3
"""Paired risks and geometry-control evidence, full support and all predefined strata."""
import json
import resource
import time
import numpy as np
from segment_information import REPO,OUT,CACHE,configuration,formal_output
from learning_capacity import load_inputs
from report_calonu_information import strata,source_draws
from train_bdt import metric_values,write_table


def analyze(d,pred,counts,support,cfg):
    labels=strata(d);focus=(d['reco_p_GeV']>=100)&(d['reco_p_GeV']<1000)
    labels.update(focus_IFT=focus&(counts[:,0]>0),focus_no_IFT=focus&(counts[:,0]==0),focus_local_multipair=focus&(counts>=2).any(axis=1))
    truth=d['truth_E_GeV'];errors={k:np.log(p/truth)**2 for k,p in pred.items()};unique,gid,draws=source_draws(d,500,cfg['seed']);ng=len(unique)
    metrics=[];paired=[]
    for label,mask in labels.items():
        if not mask.any():continue
        n=np.bincount(gid,weights=mask,minlength=ng);den=draws@n;valid=den>0;boot={};risk={}
        for name,p in pred.items():
            risk[name]=float(errors[name][mask].mean());boot[name]=(draws[valid]@np.bincount(gid,weights=mask*errors[name],minlength=ng))/den[valid]
            metrics.append(dict(support=support,stratum=label,model=name,sources=int(np.count_nonzero(n)),log_MSE=risk[name],**metric_values(truth,p,mask)))
        for ref,name in [('F6','angles'),('F6','convergence'),('F6','shuffle'),('angles','convergence'),('shuffle','convergence')]:
            g=1-np.sqrt(boot[name]/boot[ref]);delta=np.sqrt(boot[name])-np.sqrt(boot[ref]);mse=boot[name]-boot[ref]
            record=dict(support=support,stratum=label,reference=ref,model=name,N=int(mask.sum()),sources=int(np.count_nonzero(n)),
                relative_gain=float(1-np.sqrt(risk[name]/risk[ref])),CI025=float(np.quantile(g,.025)),CI975=float(np.quantile(g,.975)),
                log_RMSE_delta=float(np.sqrt(risk[name])-np.sqrt(risk[ref])),delta_CI025=float(np.quantile(delta,.025)),delta_CI975=float(np.quantile(delta,.975)),
                log_MSE_delta=risk[name]-risk[ref],MSE_delta_CI025=float(np.quantile(mse,.025)),MSE_delta_CI975=float(np.quantile(mse,.975)),valid_bootstrap=int(valid.sum()))
            for key,values in [('mean_bias',pred[name]/truth-pred[ref]/truth),('tail_0p5',(abs(pred[name]/truth-1)>.5).astype(float)-(abs(pred[ref]/truth-1)>.5)),('tail_1',(abs(pred[name]/truth-1)>1).astype(float)-(abs(pred[ref]/truth-1)>1))]:
                b=(draws[valid]@np.bincount(gid,weights=mask*values,minlength=ng))/den[valid]
                record.update({key+'_delta':float(values[mask].mean()),key+'_CI025':float(np.quantile(b,.025)),key+'_CI975':float(np.quantile(b,.975))})
            paired.append(record)
    return metrics,paired


cfg=configuration();tick,cp=time.perf_counter(),time.process_time();d,x=load_inputs()
with np.load(REPO/'ntuples/energy_ml_stage50/predictions.npz') as z:pred={'F6':z['L5_F6']}
with np.load(CACHE/'features.npz') as z:counts=z['valid_unique_counts']
sets=[];training=[];process=[]
for f in range(3):
    p=formal_output(f,d)
    md=json.loads(str(p['metadata_json']));assert md['config']==cfg and md['fold']==f and not md['smoke'];training+=md['records'];sets.append(p)
    process.append({k:md[k] for k in ['fold','wall_s','cpu_s','peak_rss_MiB','xgboost_version','numpy_version']})
rows=np.concatenate([p['cache_row'] for p in sets]);order=np.argsort(rows);np.testing.assert_array_equal(rows[order],np.arange(len(x)))
for name in cfg['candidates']:pred[name]=np.concatenate([p[name] for p in sets])[order]
metrics=[];paired=[]
for support,mask in [('A_full',np.ones(len(x),bool)),('A_B_sources',d['selected']),('A_remaining_sources',~d['selected'])]:
    m,p=analyze({k:v[mask] for k,v in d.items()},{k:v[mask] for k,v in pred.items()},counts[mask],support,cfg);metrics+=m;paired+=p
write_table(OUT/'metrics.tsv',metrics);write_table(OUT/'paired.tsv',paired);write_table(OUT/'training_resources.tsv',training)
(OUT/'process_resources.json').write_text(json.dumps(process,indent=2)+'\n')
np.savez_compressed(CACHE/'predictions.npz',cache_row=np.arange(len(x)),**pred)
main=[r for r in paired if r['support']=='A_full' and r['stratum']=='focus']
md=dict(events=len(x),sources=len(set(d['group'])),focus_events=int(((d['reco_p_GeV']>=100)&(d['reco_p_GeV']<1000)).sum()),formal_fits=len(training),baseline_fits=0,focus_comparisons=main,
    practical_gate_passed={r['model']:bool(r['relative_gain']>=.02 and r['CI025']>0) for r in main if r['reference']=='F6'},
    relation_gate_passed=bool(next(r for r in main if r['reference']=='shuffle')['CI025']>0),
    independent_confirmation=False,probability_mapping_fits=0,wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cp,peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
(OUT/'evaluation.json').write_text(json.dumps(md,indent=2)+'\n');print(json.dumps(md))
