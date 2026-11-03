#!/usr/bin/env python3
"""Audit failed stage75 convergence without energy-risk evaluation or extra queries."""
import csv
from conditional_decision import *


def main():
    start=begin();p=json.loads((OUT/'protocol.json').read_text())
    pilot=json.loads((OUT/'pilot.json').read_text());assert not pilot['passed']
    rows=list(csv.DictReader((OUT/'numerical_QA.tsv').open(),delimiter='\t'))
    sources=list(csv.DictReader((OUT/'numerical_source_QA.tsv').open(),delimiter='\t'))
    ids=list(csv.DictReader((OUT/'numerical_QA_identities.tsv').open(),delimiter='\t'))
    assert len(ids)==256 and len(set(int(v['row']) for v in ids))==256
    expected={(v['job'],v['role'],v['row'],v['group'],arm) for v in ids for arm in ARMS}
    assert {(v['job'],v['role'],v['row'],v['group'],v['arm']) for v in rows}==expected
    assert len(rows)==512
    summary=[];inventory=[];all_errors=[]
    for job in JOBS:
        for arm in ARMS:
            selected=[v for v in rows if v['job']==job and v['arm']==arm]
            coarse=np.array([float(v['log_mean_257']) for v in selected])
            fine=np.array([float(v['log_mean_513']) for v in selected])
            error=abs(coarse-fine);all_errors.extend(error)
            np.testing.assert_array_equal(error,np.array([float(v['abs_difference']) for v in selected]))
            sg=[v for v in sources if v['job']==job and v['arm']==arm]
            for v in sg:
                measured=[float(r['abs_difference']) for r in selected if r['group']==v['group']]
                assert len(measured)==int(v['N']) and float(np.median(measured))==float(v['median_abs_difference'])
            med=np.array([float(v['median_abs_difference']) for v in sg])
            maximum=int(error.argmax());r=selected[maximum]
            summary.append(dict(job=job,arm=arm,N=len(error),max_abs_log_difference=float(error.max()),
                median_abs_log_difference=float(np.median(error)),q95_abs_log_difference=float(np.quantile(error,.95)),
                above_max_limit_N=int((error>p['numerical_max_abs_log_mean_difference']).sum()),
                source_N=len(sg),source_median_failed_N=int((med>p['numerical_source_median_limit']).sum()),
                source_median_max=float(med.max()),max_difference_row=int(r['row']),max_difference_group=r['group'],
                max_difference_role=r['role']))
            booster=model(job,arm,p['features']);raw=json.loads(booster.save_raw(raw_format='json'))
            trees=raw['learner']['gradient_booster']['model']['trees'];query_feature=1 if arm=='M' else 62
            cuts=[];query_trees=0
            for tree in trees:
                take=(np.array(tree['left_children'])>=0)&(np.array(tree['split_indices'])==query_feature)
                assert not np.any(np.array(tree['split_type'])[take])
                query_trees+=bool(take.any());cuts.extend(np.array(tree['split_conditions'])[take])
            unique=np.unique(np.array(cuts,dtype='float32'));inside=unique[(unique>LOG_EDGES[0])&(unique<LOG_EDGES[-1])]
            # Actual t->float32 transition can differ from the stored float threshold.
            transition=(inside.astype(float)+np.nextafter(inside,np.float32(-np.inf)).astype(float))/2
            nodes=grid(257);near=np.min(abs(transition[:,None]-nodes),axis=1)
            inventory.append(dict(job=job,arm=arm,trees=len(trees),trees_with_query_splits=int(query_trees),
                query_split_nodes=len(cuts),unique_float32_query_cuts=len(unique),interior_query_transitions=len(inside),
                min_query_cut_logGeV=float(unique.min()),max_query_cut_logGeV=float(unique.max()),
                nearest_main_grid_distance_max=float(near.max()),nearest_main_grid_distance_median=float(np.median(near)),
                proposed_exact_partition_intervals=len(np.unique(np.r_[LOG_EDGES,transition]))-1,
                additional_query_predictions=0))
    table(OUT/'numerical_summary.tsv',summary);table(OUT/'query_threshold_inventory.tsv',inventory)
    maximum=max(all_errors);median_max=max(float(v['median_abs_difference']) for v in sources)
    assert maximum==pilot['max_abs_log_mean_difference'] and median_max==pilot['max_source_median_abs_difference']
    failed_rows=[v for v in rows if float(v['abs_difference'])>p['numerical_max_abs_log_mean_difference']]
    failed_sources=[v for v in sources if float(v['median_abs_difference'])>p['numerical_source_median_limit']]
    result=dict(passed=True,QA_selection_exact=True,real_X_N=256,arm_rows=512,
        max_abs_log_mean_difference=maximum,max_source_median_abs_difference=median_max,
        max_limit_failed_arm_rows=len(failed_rows),max_limit_failed_unique_X=len(set(v['row'] for v in failed_rows)),
        source_median_failed_job_arm_groups=len(failed_sources),source_job_arm_groups=len(sources),
        all_persisted_differences_and_source_medians_exact=True,formal_fits=0,Condor_submissions=0,
        new_point_risk_or_calibration_evaluation=False,additional_model_queries=0,
        failure='frozen numerical grid convergence gates failed; not an energy-model risk result',
        next_contract='exact piecewise-constant score integration on stored model query split transitions plus original q edges; zero new training; independent traversal and numerical/resource QA before point risks',
        **resources(start))
    save(OUT/'validation.json',result)
    save(OUT/'decisions.json',dict(deployment='retain F7',numerical_gate_passed=False,
        formal_point_jobs=0,new_fits=0,energy_point_risk_measured=False,
        energy_posterior_calibration_measured=False,stage74_information_result_unchanged=True,
        interpretation='grid underresolution on fixed tree scores; no inference on energy-model superiority or information limit',
        next_stage=76,next_stage_executed=False))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    labels=[v['job']+' '+v['arm'] for v in summary];x=np.arange(len(summary))
    axes[0].plot(x,[v['max_abs_log_difference'] for v in summary],'o-',label='maximum')
    axes[0].plot(x,[v['q95_abs_log_difference'] for v in summary],'o-',label='95th percentile')
    axes[0].axhline(.005,color='k',ls='--',label='max gate .005')
    axes[1].plot(x,[v['source_median_max'] for v in summary],'o-')
    axes[1].axhline(.001,color='k',ls='--',label='source median gate .001')
    for ax in axes:
        ax.set_xticks(x,labels,rotation=40,ha='right');ax.set_ylabel('Absolute log-mean difference');ax.grid(alpha=.2);ax.legend(fontsize=8)
    axes[0].set_title('257 versus 513 base nodes');axes[1].set_title('Maximum source median')
    fig.tight_layout();fig.savefig(OUT/'numerical_convergence.png',dpi=150);plt.close(fig)
    save(OUT/'report_resources.json',dict(**resources(start),scope='validation, structural model inventory and plot; no extra model query',physical_EOS_IO='未测量'))
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
