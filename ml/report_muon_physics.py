#!/usr/bin/env python3
"""Paired physics diagnostics of the fixed development sample and truth oracles."""
import argparse
import csv
import json
import resource
import time
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import yaml

from report_robustness import group_bootstrap_losses, svg
from train_bdt import metric_values, write_table


def read_npz(path):
    with np.load(path) as d:return {k:d[k] for k in d.files if not k.endswith('_json')}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
    args=p.parse_args(); repo=args.repo; tick=time.perf_counter(); cpu=time.process_time()
    out=repo/'workbook/stage15_energy_ml'; art=repo/'ml/artifacts'
    cfg=yaml.safe_load((repo/'ml/configs/physics_decomposition.yaml').read_text())
    baseline=yaml.safe_load((repo/'ml/configs/baseline.yaml').read_text())
    truth=read_npz(repo/'ntuples/energy_ml_stage15/validation_truth.npz')
    y=truth['truth_E_GeV']; enu_edges=np.array(cfg['energy_edges_GeV']); n=len(y)
    predictions=[]; costs=[]; seed_summaries=[]
    for i,seed in enumerate(cfg['seeds']):
        summary=json.loads((out/f'seed_{i}/summary.json').read_text())
        configuration=(json.loads((out/f'seed_{i}'/summary['configuration_file']).read_text())
                       if 'configuration_file' in summary else summary)
        if configuration['study']!=cfg or configuration['baseline']!=baseline or summary['seed']!=seed or summary['smoke'] or summary['calibration_test_challenge_evaluated']:
            raise RuntimeError('Oracle provenance mismatch')
        seed_summaries.append(summary)
        oracle=read_npz(art/f'stage15/seed_{i}/predictions.npz')
        deploy=read_npz(art/f'stage14/seed_{i}/predictions.npz')
        # All primary candidates are unique in this production: common support is full.
        # Fail if that changes instead of silently reporting a subset as the original.
        for d in [oracle,deploy]:
            for k in ['run','eventID','truth_E_GeV']:np.testing.assert_array_equal(d[k],truth[k])
        np.testing.assert_array_equal(oracle['group'],deploy['group'])
        if i:np.testing.assert_array_equal(groups,oracle['group'])
        groups=oracle['group']
        predictions.append({**{k:oracle[k] for k in ['O0','O1','O2']},
                            **{k:deploy[f'd5_1600__{k}'] for k in ['F2','F3']}})
        costs+=list(csv.DictReader((out/f'seed_{i}/costs.tsv').open(),delimiter='\t'))
    write_table(out/'costs.tsv',costs)
    names=list(predictions[0]); losses={k:np.mean([np.log(d[k]/y)**2 for d in predictions],axis=0) for k in names}
    macro,macro_boot=group_bootstrap_losses(losses,y,groups,enu_edges,cfg['bootstrap_replicates'],cfg['seeds'][0])
    all_metrics=[]; overview=[]
    for name in names:
        macros=[]
        for i,d in enumerate(predictions):
            error=np.log(d[name]/y)**2
            score=float(np.sqrt(np.mean([error[(y>=a)&(y<b)].mean() for a,b in zip(enu_edges[:-1],enu_edges[1:])])))
            macros.append(score)
            all_metrics.append(dict(model=name,seed=cfg['seeds'][i],stratum='all',value='all',macro_log_RMSE=score,
                                    **metric_values(y,d[name],np.ones(n,dtype=bool))))
        ci=np.quantile(macro_boot[name],[.025,.975])
        overview.append(dict(model=name,macro_seed_mean=float(np.mean(macros)),macro_seed_min=min(macros),macro_seed_max=max(macros),
                             macro_RMS_over_seeds=macro[name],macro_CI025=ci[0],macro_CI975=ci[1],
                             integrated_RMS_over_seeds=float(np.sqrt(losses[name].mean()))))
    pairs=[('O0','O1'),('O1','O2'),('O0','O2'),('F2','F3')]
    macro_gains=[]
    for left,right in pairs:
        ci=np.quantile(macro_boot[right]-macro_boot[left],[.025,.975])
        macro_gains.append(dict(reference=left,model=right,reference_score=macro[left],model_score=macro[right],
                                delta=macro[right]-macro[left],CI025=ci[0],CI975=ci[1]))
    masks=[('all','all',np.ones(n,dtype=bool)),
           ('matching','primary_confirmed',truth['lead_primary_parent_confirmed']),
           ('matching','other_leading',~truth['lead_primary_parent_confirmed']),
           ('truth_region','FASERnu_box',truth['vertex_z_mm'] < -1950),
           ('truth_region','lead_block',truth['vertex_z_mm'] >= -1950)]
    # Exploratory response subgroup thresholds; diagnostics only, never a new cut.
    response=truth['reco_p_GeV']/truth['primary_p_GeV']
    matched=truth['lead_primary_parent_confirmed']
    masks += [('response','primary_abs_p_ratio_minus_1_le_0p1',matched&(abs(response-1)<=.1)),
              ('response','primary_abs_p_ratio_minus_1_gt_0p1',matched&(abs(response-1)>.1))]
    masks += [('y_primary_confirmed',f'ge_{a:g}',matched&(truth['y_lepton']>=a)) for a in [.6,.8]]
    masks += [('y_lepton',f'{a:g}_{b:g}',(truth['y_lepton']>=a)&(truth['y_lepton']<b))
              for a,b in zip(cfg['y_edges'][:-1],cfg['y_edges'][1:])]
    masks += [('energy_GeV',f'{a:g}_{b:g}',(y>=a)&(y<b)) for a,b in zip(enu_edges[:-1],enu_edges[1:])]
    masks += [('run',str(int(run)),truth['run']==run) for run in np.unique(truth['run'])]
    # Same full-source resamples for every stratum and model. Mean losses over seeds
    # describe single-model repetition, not an ensemble of averaged predictions.
    _,gid=np.unique(groups,return_inverse=True); ng=gid.max()+1
    rng=np.random.default_rng(cfg['seeds'][0]); draws=rng.multinomial(ng,np.full(ng,1/ng),size=cfg['bootstrap_replicates'])
    gains=[]; audits=[]; ymetrics=[]
    for label,value,m in masks:
        counts=np.bincount(gid[m],minlength=ng); den=draws@counts; valid=den>0
        boot={}; centers={}
        for name in names:
            sums=np.bincount(gid[m],weights=losses[name][m],minlength=ng)
            centers[name]=float(np.sqrt(losses[name][m].mean()))
            boot[name]=np.sqrt((draws@sums)[valid]/den[valid])
            if label!='all':
                for i,d in enumerate(predictions):
                    all_metrics.append(dict(model=name,seed=cfg['seeds'][i],stratum=label,value=value,macro_log_RMSE='',
                                            **metric_values(y,d[name],m)))
        for left,right in pairs:
            ci=np.quantile(boot[right]-boot[left],[.025,.975])
            gains.append(dict(stratum=label,value=value,N=int(m.sum()),source_groups=int((counts>0).sum()),
                              reference=left,model=right,log_RMSE_reference=centers[left],log_RMSE_model=centers[right],
                              delta=centers[right]-centers[left],CI025=ci[0],CI975=ci[1],bootstrap_valid=int(valid.sum())))
        q=np.quantile(response[m],[.025,.16,.5,.84,.975]); qy=np.quantile(truth['y_lepton'][m],[.16,.5,.84])
        audits.append(dict(stratum=label,value=value,N=int(m.sum()),primary_confirmed=int(matched[m].sum()),
                           station1_available=int(truth['primary_st1_valid'][m].sum()),
                           y_q16=qy[0],y_median=qy[1],y_q84=qy[2],p_response_q025=q[0],p_response_q16=q[1],
                           p_response_median=q[2],p_response_q84=q[3],p_response_q975=q[4],
                           p_response_outside_0p5_1p5=int((abs(response[m]-1)>.5).sum()),
                           median_transfer_energy_GeV=float(np.median(truth['transfer_energy_GeV'][m]))))
        for name in ['O0','O1','O2']:
            ym=[1-truth['primary_E_GeV']/d[name] for d in predictions]
            ymetrics.append(dict(stratum=label,value=value,model=name,N=int(m.sum()),
                                MAE_seed_mean=float(np.mean([np.mean(abs(a[m]-truth['y_lepton'][m])) for a in ym])),
                                RMSE_over_seeds=float(np.sqrt(np.mean([(a[m]-truth['y_lepton'][m])**2 for a in ym]))),
                                negative_yhat_fraction_seed_mean=float(np.mean([np.mean(a[m]<0) for a in ym]))))
    write_table(out/'macro_summary.tsv',overview);write_table(out/'macro_gains.tsv',macro_gains)
    write_table(out/'stratified_gains.tsv',gains);write_table(out/'metrics.tsv',all_metrics)
    write_table(out/'response_and_y.tsv',audits);write_table(out/'y_reconstruction.tsv',ymetrics)
    # Exact log identity, retaining covariance. These are not causal variance fractions.
    variance=[]
    for label,value,m in masks[:5]:
        a=np.log(y[m]/truth['primary_p_GeV'][m]); b=np.log(response[m]); residual=np.log(y[m]/truth['reco_p_GeV'][m])
        cov=float(np.mean((a-a.mean())*(b-b.mean())))
        variance.append(dict(stratum=label,value=value,N=int(m.sum()),mean_log_Enu_pvertex=float(a.mean()),
                             mean_log_preco_pvertex=float(b.mean()),var_log_Enu_pvertex=float(a.var()),
                             var_log_preco_pvertex=float(b.var()),covariance=cov,var_log_Enu_preco=float(residual.var()),
                             variance_closure_residual=float(residual.var()-(a.var()+b.var()-2*cov)),
                             max_identity_abs_error=float(np.max(abs(residual-(a-b))))))
    write_table(out/'log_variance_identity.tsv',variance)
    ordering=[];types=[];station=[]
    for part in cfg['partitions']:
        d=read_npz(repo/f'ntuples/energy_ml_stage15/{part}_truth.npz')
        for field in ['primary_index','primary_barcode','lead_t_pdg']:
            values,counts=np.unique(d[field],return_counts=True)
            for v,c in zip(values,counts):ordering.append(dict(partition=part,field=field,value=v,N=int(c)))
        other=~d['lead_primary_parent_confirmed']; v,c=np.unique(d['lead_t_pdg'][other],return_counts=True)
        for a,b in zip(v,c):types.append(dict(partition=part,leading_pdg=a,N=int(b)))
        m=d['primary_st1_valid']; r=d['primary_st1_p_GeV'][m]/d['primary_p_GeV'][m]
        station.append(dict(partition=part,N=len(r),missing=int((~m).sum()),median_ratio=float(np.median(r)),
                            min_ratio=float(r.min()),max_ratio=float(r.max()),
                            max_abs_ratio_minus_1=float(np.max(abs(r-1))),
                            material_energy_loss_measured=False))
    write_table(out/'truth_order_and_species.tsv',ordering);write_table(out/'other_leading_species.tsv',types)
    write_table(out/'station_reference_audit.tsv',station)
    # Scientific export figures; seed errors are averaged, not predictions.
    fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    colors={'O0':'#777777','O1':'#377eb8','O2':'#e41a1c','F2':'#4daf4a','F3':'#984ea3'}
    for name in names:
        values=[next(r['log_RMSE_model'] if r['model']==name else r['log_RMSE_reference'] for r in gains
                     if r['stratum']=='y_lepton' and r['value']==f'{a:g}_{b:g}' and name in [r['model'],r['reference']])
                for a,b in zip(cfg['y_edges'][:-1],cfg['y_edges'][1:])]
        centers=(np.array(cfg['y_edges'][:-1])+np.array(cfg['y_edges'][1:]))/2
        axes[0].plot(centers,values,'o-',label=name,color=colors[name])
    axes[0].set(xlabel=r'Leptonic $y=1-E_\mu/E_\nu$',ylabel='Integrated log-RMSE',title='Fixed development selection; unit weights')
    axes[0].legend(ncol=2)
    gain_y=[r for r in gains if r['stratum']=='y_lepton' and (r['reference'],r['model']) in [('O1','O2'),('F2','F3')]]
    for left,right,shift in [('O1','O2',-.008),('F2','F3',.008)]:
        rs=[r for r in gain_y if r['model']==right];v=np.array([r['delta'] for r in rs])
        axes[1].errorbar(centers+shift,v,yerr=[v-np.array([r['CI025'] for r in rs]),np.array([r['CI975'] for r in rs])-v],
                         fmt='o',capsize=3,label=f'{right} minus {left}',color=colors[right])
    axes[1].axhline(0,color='gray',lw=1);axes[1].legend()
    axes[1].set(xlabel='Leptonic y',ylabel='Change in log-RMSE (95% group bootstrap)',title='Charge increment: 3-seed mean squared losses')
    svg(fig,out/'y_dependence.svg')
    fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    for name in ['O0','O1','O2']:
        rms=[np.sqrt(losses[name][(y>=a)&(y<b)].mean()) for a,b in zip(enu_edges[:-1],enu_edges[1:])]
        axes[0].plot(np.sqrt(enu_edges[:-1]*enu_edges[1:]),rms,'o-',label=name,color=colors[name])
    axes[0].set(xscale='log',xlabel=r'True $E_\nu$ [GeV]',ylabel='Log-RMSE',title='Truth-muon oracle, not deployable');axes[0].legend()
    for label,m in [('Primary confirmed',matched),('Other leading',~matched)]:
        axes[1].hist(np.log(response[m]),bins=np.linspace(-2,2,81),histtype='step',
                     weights=np.full(m.sum(),1/(m.sum()*.05)),label=f'{label}: N={m.sum()}')
    axes[1].set(yscale='log',xlabel=r'$\log(p_{reco}/p_{\mu,vertex})$',ylabel='Density',title='All outliers retained in numerical tables');axes[1].legend()
    svg(fig,out/'energy_and_response.svg')
    summary=dict(seeds=cfg['seeds'],validation_events=n,validation_groups=int(ng),
                 oracle_support_full_validation=True,calibration_test_challenge_evaluated=False,
                 oracle_total_wall_s=sum(s['wall_s'] for s in seed_summaries),oracle_total_cpu_s=sum(s['cpu_s'] for s in seed_summaries),
                 oracle_peak_rss_MiB=max(s['peak_rss_MiB'] for s in seed_summaries),
                 report_wall_s=time.perf_counter()-tick,report_cpu_s=time.process_time()-cpu,
                 report_peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    # Condor emits independent provenance; consolidate identical configuration once.
    (out/'training_config.json').write_text(json.dumps(dict(study=cfg,baseline=baseline),indent=2)+'\n')
    for i,run in enumerate(seed_summaries):
        compact={k:v for k,v in run.items() if k not in ['study','baseline']}
        compact['configuration_file']='../training_config.json'
        (out/f'seed_{i}/summary.json').write_text(json.dumps(compact,indent=2)+'\n')
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
