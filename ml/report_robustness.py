#!/usr/bin/env python3
"""Aggregate the preregistered stage14 development experiments and paired errors."""
import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import yaml

from train_bdt import metric_values, write_table


def group_bootstrap_losses(losses, y, groups, edges, replicates, seed):
    _, ids = np.unique(groups, return_inverse=True)
    ng = ids.max()+1
    masks = [(y>=a)&(y<b) for a,b in zip(edges[:-1],edges[1:])]
    counts = np.array([np.bincount(ids[m], minlength=ng) for m in masks]).T
    active = counts.sum(axis=0)>=100
    rng = np.random.default_rng(seed)
    draws = rng.multinomial(ng, np.full(ng,1/ng), size=replicates)
    denominators = draws@counts[:,active]
    valid = np.all(denominators>0,axis=1)
    boot, central = {}, {}
    for name,loss in losses.items():
        sums = np.array([np.bincount(ids[m], weights=loss[m], minlength=ng) for m in masks]).T[:,active]
        central[name] = float(np.sqrt(np.mean(sums.sum(axis=0)/counts[:,active].sum(axis=0))))
        boot[name] = np.sqrt(np.mean((draws@sums)[valid]/denominators[valid],axis=1))
    return central, boot


def svg(fig,path):
    fig.savefig(path)
    path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
    plt.close(fig)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--report-dir',type=Path,required=True)
    p.add_argument('--artifact-dir',type=Path,required=True)
    args = p.parse_args()
    cfg = yaml.safe_load((args.repo/'ml/configs/robustness.yaml').read_text())
    baseline = yaml.safe_load((args.repo/'ml/configs/baseline.yaml').read_text())
    reports, predictions, all_metrics, all_costs, traces = [], [], [], [], []
    for i,seed in enumerate(cfg['seeds']):
        folder = args.report_dir/f'seed_{i}'
        report = json.loads((folder/'summary.json').read_text())
        assert report['seed']==seed and not report['smoke'] and report['study']==cfg
        assert report['baseline']==baseline and not report['calibration_test_challenge_evaluated']
        reports.append(report)
        with np.load(args.artifact_dir/f'seed_{i}/predictions.npz') as data:
            predictions.append({k:data[k] for k in data.files})
        all_metrics.extend(list(csv.DictReader((folder/'metrics.tsv').open(),delimiter='\t')))
        all_costs.extend(list(csv.DictReader((folder/'costs.tsv').open(),delimiter='\t')))
        traces.append(json.loads((folder/'learning_traces.json').read_text()))
    for d in predictions[1:]:
        for k in ['run','eventID','truth_E_GeV','group']:
            np.testing.assert_array_equal(predictions[0][k],d[k])
    y = predictions[0]['truth_E_GeV']
    edges = np.array(baseline['energy_edges_GeV'])
    losses = {}
    models = []
    for cap in cfg['capacities']:
        for version in cfg['versions']:
            name = f'{cap}__{version}'
            errors = np.stack([np.log(d[name]/y)**2 for d in predictions])
            # Average losses across seeds: never average predictions to disguise an ensemble.
            losses[name] = errors.mean(axis=0)
            seed_macro = []
            for error in errors:
                seed_macro.append(np.sqrt(np.mean([error[(y>=a)&(y<b)].mean() for a,b in zip(edges[:-1],edges[1:])])) )
            models.append(dict(model=name,seeds=len(errors),macro_seed_mean=float(np.mean(seed_macro)),
                               macro_seed_min=float(np.min(seed_macro)),macro_seed_max=float(np.max(seed_macro))))
    special = [k for k in predictions[0] if k.startswith(('flat_prior__','learning_','shuffled_train_val__'))]
    for name in special:
        losses[name] = np.log(predictions[0][name]/y)**2
    permutation_rows = list(csv.DictReader((args.report_dir/'seed_0/permutation_controls.tsv').open(),delimiter='\t'))
    permutations = []
    for resolution in ['coarse','fine']:
        for version,groups in cfg['conditional_permutation']['targets'].items():
            for group in groups:
                prefix = f'permuted__{resolution}__{version}__{group}__'
                names = [k for k in predictions[0] if k.startswith(prefix)]
                assert len(names)==cfg['conditional_permutation']['repeats']
                name = prefix+'repeat_mean_loss'
                errors = np.stack([np.log(predictions[0][k]/y)**2 for k in names])
                losses[name] = errors.mean(axis=0)
                base = f'first_seed__d3_2400__{version}'
                losses[base] = np.log(predictions[0][f'd3_2400__{version}']/y)**2
                matching = [r for r in permutation_rows if r['model'] in names]
                permutations.append(dict(model=name,reference=base,resolution=resolution,group=group,
                                         movable_fraction=float(matching[0]['movable_events'])/len(y),
                                         mean_changed_donor_fraction=float(np.mean([float(r['changed_donor_events']) for r in matching]))/len(y),
                                         mean_abs_logp_change=float(np.mean([float(r['mean_abs_logp_change']) for r in matching])),
                                         mean_abs_theta_change_mrad=float(np.mean([float(r['mean_abs_theta_change_mrad']) for r in matching])),
                                         mean_abs_radius_change_mm=float(np.mean([float(r['mean_abs_radius_change_mm']) for r in matching]))))
    central,boot = group_bootstrap_losses(losses,y,predictions[0]['group'],edges,cfg['bootstrap_replicates'],baseline['seed'])
    for row in models:
        name = row['model'];ci=np.quantile(boot[name],[.025,.975])
        row.update(macro_RMS_over_seeds=central[name],CI025=ci[0],CI975=ci[1])
    comparisons = []
    def add(left,right,category):
        delta = boot[right]-boot[left]
        ci = np.quantile(delta,[.025,.975])
        comparisons.append(dict(category=category,reference=left,model=right,
                                delta_macro=central[right]-central[left],CI025=ci[0],CI975=ci[1],
                                bootstrap_replicates=len(delta)))
    for cap in cfg['capacities']:
        for left,right in [('F1','F2'),('F2','F3'),('F3','F5'),
                           ('F5_without_scintillator','F5'),('F5_without_calo','F5'),('F5_without_shape','F5')]:
            add(f'{cap}__{left}',f'{cap}__{right}','feature_ablation_mean_seed_loss')
    for version in cfg['versions']:
        for cap in ['d3_2400','d5_1600']:
            add(f'd3_600__{version}',f'{cap}__{version}','capacity_mean_seed_loss')
    for version in ['F1','F3','F5']:
        ref = f'first_seed__d3_2400__{version}'
        if ref not in losses:
            # Already bootstrapped F2,F3,F5; add F1 using an explicit second pass below.
            continue
        add(ref,f'flat_prior__{version}','training_prior_first_seed')
    for row in permutations:
        add(row['reference'],row['model'],'conditional_permutation_first_seed')
        entry = comparisons[-1]
        row.update(delta_macro=entry['delta_macro'],CI025=entry['CI025'],CI975=entry['CI975'])
    # Single-seed controls must be compared with the same single-seed unshuffled model.
    first_losses = {f'd3_2400__{v}':np.log(predictions[0][f'd3_2400__{v}']/y)**2 for v in ['F1','F2','F3','F5']}
    first_losses.update({name:losses[name] for name in special})
    first_c,first_b = group_bootstrap_losses(first_losses,y,predictions[0]['group'],edges,cfg['bootstrap_replicates'],baseline['seed'])
    controls = []
    pairs = [(f'd3_2400__{v}',f'flat_prior__{v}') for v in ['F1','F3','F5']]
    pairs += [(f'd3_2400__{v}',f'shuffled_train_val__{v}') for v in ['F2','F3']]
    pairs += [('d3_2400__F1','shuffled_train_val__F2'),('d3_2400__F2','shuffled_train_val__F3')]
    for left,right in pairs:
        ci = np.quantile(first_b[right]-first_b[left],[.025,.975])
        controls.append(dict(reference=left,model=right,macro_reference=first_c[left],macro_model=first_c[right],
                             delta_macro=first_c[right]-first_c[left],CI025=ci[0],CI975=ci[1]))
    energy_rows,strata = [],[]
    selected = ['d3_2400__F1','d3_2400__F2','d3_2400__F3','d3_2400__F5','flat_prior__F1','flat_prior__F3','flat_prior__F5']
    with np.load(args.repo/'ntuples/energy_ml_stage12/dataset/validation.npz') as data:
        charges=data['LeadTrack_charge']
        truth_z=data['truth_dec_z_nu']
    for name in selected:
        pred = predictions[0][name]
        for a,b in zip(edges[:-1],edges[1:]):
            mask = (y>=a)&(y<b)
            energy_rows.append(dict(model=name,low_GeV=a,high_GeV=b,**metric_values(y,pred,mask)))
        for run in np.unique(predictions[0]['run']):
            mask = predictions[0]['run']==run
            strata.append(dict(model=name,stratum='run',value=int(run),**metric_values(y,pred,mask)))
        for charge in [-1,1]:
            mask = charges==charge
            strata.append(dict(model=name,stratum='charge',value=charge,**metric_values(y,pred,mask)))
    # Quantify gains independently within each run and truth vertex region.
    strata_gain=[]
    strata_masks=[('run',str(int(run)),predictions[0]['run']==run) for run in np.unique(predictions[0]['run'])]
    strata_masks += [('truth_region','FASERnu_box',truth_z < -1950),('truth_region','lead_block',truth_z >= -1950)]
    for label,value,mask in strata_masks:
        for left,right in [('d3_2400__F1','d3_2400__F2'),('d3_2400__F2','d3_2400__F3')]:
            # Integrated log-RMSE within the stratum; same seeds and same events.
            subloss={left:losses[left][mask],right:losses[right][mask]}
            c,b=group_bootstrap_losses(subloss,y[mask],predictions[0]['group'][mask],np.array([100,6400]),cfg['bootstrap_replicates'],baseline['seed'])
            ci=np.quantile(b[right]-b[left],[.025,.975])
            strata_gain.append(dict(stratum=label,value=value,N=int(mask.sum()),reference=left,model=right,log_RMSE_reference=c[left],log_RMSE_model=c[right],delta= c[right]-c[left],CI025=ci[0],CI975=ci[1]))
    write_table(args.report_dir/'stratified_gains.tsv',strata_gain)
    write_table(args.report_dir/'capacity_seed_summary.tsv',models)
    write_table(args.report_dir/'paired_comparisons.tsv',comparisons)
    write_table(args.report_dir/'conditional_permutation.tsv',permutations)
    write_table(args.report_dir/'prior_and_shuffle_controls.tsv',controls)
    # Nonlinear bias/width/tail comparisons need event-weighted group resampling.
    # Compute for seed0 F3 versus F2; no event or source filtering by model score.
    _,gid=np.unique(predictions[0]['group'],return_inverse=True)
    ng=gid.max()+1
    rng=np.random.default_rng(baseline['seed'])
    draws=rng.multinomial(ng,np.full(ng,1/ng),size=cfg['bootstrap_replicates'])
    nonlinear=[]
    for a,b in zip(edges[:-1],edges[1:]):
        mask=(y>=a)&(y<b)
        local_groups=gid[mask]
        residuals={name:predictions[0][name][mask]/y[mask]-1 for name in ['d3_2400__F2','d3_2400__F3']}
        samples={name:{key:[] for key in ['median_bias','R68','tail_0p5']} for name in residuals}
        for name,residual in residuals.items():
            order=np.argsort(residual)
            ordered=residual[order]
            weights=draws[:,local_groups[order]]
            total=weights.sum(axis=1)
            cumulative=np.cumsum(weights,axis=1)
            # This uses weighted inverse-CDF bootstrap quantiles (explicitly reported).
            quantiles=[]
            for q in [.16,.5,.84]:
                indices=np.argmax(cumulative>=q*total[:,None],axis=1)
                quantiles.append(ordered[indices])
            samples[name]['median_bias']=quantiles[1]
            samples[name]['R68']=(quantiles[2]-quantiles[0])/2
            samples[name]['tail_0p5']=(weights@(np.abs(ordered)>.5))/total
        for key in ['median_bias','R68','tail_0p5']:
            delta=samples['d3_2400__F3'][key]-samples['d3_2400__F2'][key]
            ci=np.quantile(delta,[.025,.975])
            left=next(r for r in energy_rows if r['model']=='d3_2400__F2' and r['low_GeV']==a)
            right=next(r for r in energy_rows if r['model']=='d3_2400__F3' and r['low_GeV']==a)
            nonlinear.append(dict(low_GeV=a,high_GeV=b,N=int(mask.sum()),metric=key,reference='d3_2400__F2',model='d3_2400__F3',delta=right[key]-left[key],CI025=ci[0],CI975=ci[1],bootstrap_replicates=len(delta)))
    write_table(args.report_dir/'energy_gain_intervals.tsv',nonlinear)
    write_table(args.report_dir/'energy_bins.tsv',energy_rows)
    write_table(args.report_dir/'strata.tsv',strata)
    write_table(args.report_dir/'all_metrics.tsv',all_metrics)
    write_table(args.report_dir/'all_costs.tsv',all_costs)
    resources = [dict(seed=r['seed'],wall_s=r['wall_s'],cpu_s=r['cpu_s'],peak_rss_MiB=r['peak_rss_MiB']) for r in reports]
    write_table(args.report_dir/'resources.tsv',resources)
    fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    versions=['F1','F2','F3','F5']
    for cap in cfg['capacities']:
        chosen=[next(r for r in models if r['model']==f'{cap}__{v}') for v in versions]
        mean=np.array([r['macro_seed_mean'] for r in chosen])
        err=np.array([[r['macro_seed_mean']-r['macro_seed_min'] for r in chosen],
                      [r['macro_seed_max']-r['macro_seed_mean'] for r in chosen]])
        axes[0].errorbar(versions,mean,yerr=err,marker='o',capsize=4,label=cap)
    axes[0].set(ylabel='Macro log-RMSE',title='Mean and range of 3 seeds')
    axes[0].legend(fontsize=8);axes[0].grid(alpha=.2)
    for name in ['d3_2400__F5','flat_prior__F5']:
        chosen=[r for r in energy_rows if r['model']==name]
        axes[1].plot([np.sqrt(r['low_GeV']*r['high_GeV']) for r in chosen],
                     [100*r['median_bias'] for r in chosen],'.-',label=name)
    axes[1].set(xscale='log',xlabel='True energy [GeV]',ylabel='Median relative bias [%]',title='Training prior, same unit validation')
    axes[1].axhline(0,color='gray',lw=.8);axes[1].legend(fontsize=8);axes[1].grid(alpha=.2)
    fig.suptitle('Ordinary MC, frozen validation, unit evaluation; development results')
    svg(fig,args.report_dir/'capacity_and_prior.svg')
    learning = []
    for version in ['F1','F3']:
        for fraction in [.25,.5,1.]:
            name=f'learning_{fraction}__{version}' if fraction<1 else f'd3_2400__{version}'
            cost=next(r for r in all_costs if r['model']==name and int(r['seed'])==cfg['seeds'][0])
            learning.append(dict(version=version,fraction=fraction,train_events=cost['train_events'],
                                 macro_log_RMSE=first_c[name],best_iteration=cost['best_iteration']))
    write_table(args.report_dir/'learning_curve.tsv',learning)
    summary = dict(seeds=cfg['seeds'],capacity_models=3*3*7,extra_first_seed_models=len(special),
                   permutation_repeats=cfg['conditional_permutation']['repeats'],
                   permutation_models=sum(1 for k in predictions[0] if k.startswith('permuted__')),
                   train_events=reports[0]['train_events'],validation_events=len(y),
                   sum_wall_s=sum(r['wall_s'] for r in reports),sum_cpu_s=sum(r['cpu_s'] for r in reports),
                   peak_rss_MiB=max(r['peak_rss_MiB'] for r in reports),
                   uncertainty='source-group bootstrap conditional on fitted models; seed losses averaged, no prediction ensemble; no independent test/physical normalization',
                   baseline_600_best_iteration_max=max(int(r['best_iteration']) for r in all_costs if r['model'].startswith('d3_600')),
                   extended_2400_best_iteration_max=max(int(r['best_iteration']) for r in all_costs if r['model'].startswith('d3_2400')))
    (args.report_dir/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary),flush=True)


if __name__ == '__main__':
    main()
