#!/usr/bin/env python3
"""Same-event training-support and fixed-capacity comparisons on the full development population."""
import json
import resource
import time
import numpy as np
from learning_capacity import REPO,CACHE,OUT,configuration,load_inputs,formal_output
from report_calonu_information import strata,source_draws
from train_bdt import metric_values,write_table


def analyze(d,pred,support,pairs,cfg):
    y=d['truth_E_GeV'];unique,gid,draws=source_draws(d,cfg['bootstrap_replicates'],cfg['seed']);ng=len(unique)
    metrics=[];paired=[];interactions=[];errors={k:np.log(p/y) for k,p in pred.items()}
    for label,mask in strata(d).items():
        if not mask.any():continue
        counts=np.bincount(gid,weights=mask,minlength=ng);den=draws@counts;valid=den>0;boot={};mse={}
        for name in pred:
            mse[name]=float(np.mean(errors[name][mask]**2));boot[name]=(draws[valid]@np.bincount(gid,weights=mask*errors[name]**2,minlength=ng))/den[valid]
            metrics.append(dict(support=support,stratum=label,model=name,sources=int(np.count_nonzero(counts)),log_MSE=mse[name],**metric_values(y,pred[name],mask)))
        for left,right in pairs:
            gain=1-np.sqrt(boot[right]/boot[left]);delta=np.sqrt(boot[right])-np.sqrt(boot[left])
            record=dict(support=support,stratum=label,reference=left,model=right,N=int(mask.sum()),sources=int(np.count_nonzero(counts)),
                        relative_gain=float(1-np.sqrt(mse[right]/mse[left])),CI025=float(np.quantile(gain,.025)),CI975=float(np.quantile(gain,.975)),
                        log_RMSE_delta=float(np.sqrt(mse[right])-np.sqrt(mse[left])),delta_CI025=float(np.quantile(delta,.025)),delta_CI975=float(np.quantile(delta,.975)),
                        log_MSE_delta=mse[right]-mse[left],MSE_delta_CI025=float(np.quantile(boot[right]-boot[left],.025)),MSE_delta_CI975=float(np.quantile(boot[right]-boot[left],.975)),
                        valid_bootstrap=int(valid.sum()))
            for key,values in [('mean_bias',pred[right]/y-pred[left]/y),('tail_0p5',(abs(pred[right]/y-1)>.5).astype(float)-(abs(pred[left]/y-1)>.5)),
                               ('tail_1',(abs(pred[right]/y-1)>1).astype(float)-(abs(pred[left]/y-1)>1))]:
                b=(draws[valid]@np.bincount(gid,weights=mask*values,minlength=ng))/den[valid]
                record.update({key+'_delta':float(values[mask].mean()),key+'_CI025':float(np.quantile(b,.025)),key+'_CI975':float(np.quantile(b,.975))})
            paired.append(record)
        if support.startswith('A'):
            g3=boot['L3_F6']-boot['L3_F6z'];g5=boot['L5_F6']-boot['L5_F6z'];interaction=g3-g5
            interactions.append(dict(support=support,stratum=label,N=int(mask.sum()),sources=int(np.count_nonzero(counts)),
                                     G_L3=mse['L3_F6']-mse['L3_F6z'],G_L3_CI025=float(np.quantile(g3,.025)),G_L3_CI975=float(np.quantile(g3,.975)),
                                     G_L5=mse['L5_F6']-mse['L5_F6z'],G_L5_CI025=float(np.quantile(g5,.025)),G_L5_CI975=float(np.quantile(g5,.975)),
                                     G_L3_minus_G_L5=mse['L3_F6']-mse['L3_F6z']-mse['L5_F6']+mse['L5_F6z'],
                                     interaction_CI025=float(np.quantile(interaction,.025)),interaction_CI975=float(np.quantile(interaction,.975))))
    return metrics,paired,interactions


cfg=configuration();tick,cpu=time.perf_counter(),time.process_time();d,x=load_inputs()
with np.load(REPO/'ntuples/energy_ml_stage42/A_predictions.npz') as z:
    np.testing.assert_array_equal(z['cache_row'],np.arange(len(x)));pred={'L3_F6':z['A0']}
sets=[];training=[];process=[]
for f in range(3):
    part=formal_output(f,d)
    md=json.loads(str(part['metadata_json']));assert md['config']==cfg and md['fold']==f and not md['smoke'];training+=md['records']
    process.append({k:md[k] for k in ['fold','wall_s','cpu_s','peak_rss_MiB','xgboost_version','numpy_version']});sets.append(part)
order=np.argsort(np.concatenate([s['cache_row'] for s in sets]));rows=np.concatenate([s['cache_row'] for s in sets])[order]
np.testing.assert_array_equal(rows,np.arange(len(x)))
for name in cfg['candidates']:pred[name]=np.concatenate([s[name] for s in sets])[order]
pairs=[('L3_F6','L5_F6'),('L3_F6','L3_F6z'),('L5_F6','L5_F6z'),('L3_F6z','L5_F6z')]
metrics=[];paired=[];interactions=[]
for support,mask in [('A_full',np.ones(len(x),bool)),('A_B_sources',d['selected']),('A_remaining_sources',~d['selected'])]:
    m,p,i=analyze({k:v[mask] for k,v in d.items()},{k:v[mask] for k,v in pred.items()},support,pairs,cfg);metrics+=m;paired+=p;interactions+=i
with np.load(CACHE/'support_controls.npz') as z:controls={k:z[k] for k in z.files}
sel=controls.pop('cache_row');np.testing.assert_array_equal(sel,np.flatnonzero(d['selected']))
m,p,i=analyze({k:v[sel] for k,v in d.items()},controls,'B_training_support',[('I0','A0'),('I0','A0_common_B')],cfg)
metrics+=m;paired+=p
write_table(OUT/'metrics.tsv',metrics);write_table(OUT/'paired.tsv',paired);write_table(OUT/'interaction.tsv',interactions);write_table(OUT/'training_resources.tsv',training)
(OUT/'process_resources.json').write_text(json.dumps(process,indent=2)+'\n')
np.savez_compressed(CACHE/'predictions.npz',cache_row=rows,**pred)
focus=[r for r in paired if r['support']=='A_full' and r['stratum']=='focus']
main=next(r for r in focus if (r['reference'],r['model'])==('L3_F6','L5_F6'))
z5=next(r for r in focus if (r['reference'],r['model'])==('L5_F6','L5_F6z'))
gate=lambda r:r['relative_gain']>=cfg['gate']['minimum_relative_log_RMSE_gain'] and r['CI025']>0
summary=dict(events=len(x),sources=len(set(d['group'])),focus_events=int(((d['reco_p_GeV']>=100)&(d['reco_p_GeV']<1000)).sum()),new_formal_fits=len(training),
             baseline_fits_repeated=0,focus_contrasts=focus,capacity_candidate_gate_passed=bool(gate(main)),depth5_oracle_gate_passed=bool(gate(z5)),
             focus_interaction=next(r for r in interactions if r['support']=='A_full' and r['stratum']=='focus'),
             B_focus_contrasts=[r for r in paired if r['support']=='B_training_support' and r['stratum']=='focus'],
             support_level=cfg['support_level'],independent_confirmation=False,probability_mapping_fits=0,
             wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
(OUT/'evaluation.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)
